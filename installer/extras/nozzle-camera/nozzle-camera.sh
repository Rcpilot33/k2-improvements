#!/bin/sh
# Stream the K2 Plus factory nozzle/AI camera as MJPEG.
set -eu

PORT="${NOZZLE_CAM_PORT:-8081}"
WIDTH="${NOZZLE_CAM_WIDTH:-1280}"
HEIGHT="${NOZZLE_CAM_HEIGHT:-720}"
FPS="${NOZZLE_CAM_FPS:-5}"
DEVICE="${NOZZLE_CAM_DEVICE:-/dev/video2}"
PIDFILE=/var/run/k2-nozzle-camera.pid
PIDFILE="${NOZZLE_CAM_PIDFILE:-$PIDFILE}"
LOGFILE=/tmp/k2-nozzle-camera.log
POWER=/usr/bin/nozzle_cam_power.sh
FFMPEG=/opt/bin/ffmpeg

valid_pid() {
    case "${1:-}" in
        ''|*[!0-9]*) return 1 ;;
        *) kill -0 "$1" 2>/dev/null ;;
    esac
}

stream_pid() {
    [ -f "$PIDFILE" ] || return 1
    pid=$(sed -n '1p' "$PIDFILE" 2>/dev/null)
    valid_pid "$pid" || return 1
    printf '%s\n' "$pid"
}

stop_stream() {
    pid=$(stream_pid 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null || true
        i=0
        while valid_pid "$pid" && [ "$i" -lt 20 ]; do
            sleep 0.1
            i=$((i + 1))
        done
        valid_pid "$pid" && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
}

wait_for_stock_camera() {
    i=0
    while [ "$i" -lt 12 ]; do
        [ -e "$DEVICE" ] && return 0
        sleep 1
        i=$((i + 1))
    done
    return 1
}

case "${1:-}" in
    on)
        SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
        . "$SCRIPT_DIR/../../../scripts/stock_nozzle_camera.sh"
        stock_nozzle_camera_require_available
        [ -x "$POWER" ] || { echo "ERROR: stock camera power control is missing"; exit 1; }
        [ -x "$FFMPEG" ] || { echo "ERROR: ffmpeg is not installed"; exit 1; }
        stop_stream
        "$POWER" on
        if ! wait_for_stock_camera; then
            echo "ERROR: factory nozzle camera did not appear at $DEVICE within 12 seconds"
            "$POWER" off || true
            exit 1
        fi

        # Creality starts cam_sub_app when the factory camera enumerates. It
        # must release the nozzle camera before ffmpeg can open that device.
        # Retry because the udev-started process can appear just after the
        # first release attempt.
        attempt=1
        while [ "$attempt" -le 3 ]; do
            sleep 3
            killall cam_sub_app 2>/dev/null || true
            rm -f /var/run/sub-video*.pid
            sleep 1

            "$FFMPEG" -nostdin -hide_banner -loglevel warning \
                -f v4l2 -input_format mjpeg \
                -video_size "${WIDTH}x${HEIGHT}" -framerate "$FPS" \
                -i "$DEVICE" -c:v copy -f mpjpeg \
                -content_type 'multipart/x-mixed-replace;boundary=ffmpeg' \
                -headers 'Access-Control-Allow-Origin: *' \
                -listen 1 "http://0.0.0.0:$PORT" \
                >"$LOGFILE" 2>&1 &
            pid=$!
            sleep 2
            if valid_pid "$pid"; then
                printf '%s\n' "$pid" >"$PIDFILE"
                echo "ON pid=$pid port=$PORT (automatic shutoff after 10 minutes)"
                exit 0
            fi
            echo "ffmpeg attempt $attempt failed; retrying"
            attempt=$((attempt + 1))
        done

        echo "ERROR: ffmpeg could not open the factory nozzle camera"
        tail -n 8 "$LOGFILE" 2>/dev/null || true
        "$POWER" off || true
        exit 1
        ;;
    off)
        stop_stream
        SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
        . "$SCRIPT_DIR/../../../scripts/stock_nozzle_camera.sh"
        # Stale macros/timers must never cut power to a JimmyV USB probe.
        stock_nozzle_camera_require_available
        "$POWER" off
        echo "OFF"
        ;;
    stop)
        stop_stream
        echo "STOPPED (USB rail power unchanged)"
        ;;
    status)
        pid=$(stream_pid 2>/dev/null || true)
        if [ -n "$pid" ]; then
            echo "ON pid=$pid port=$PORT"
        else
            echo "OFF"
        fi
        ;;
    *)
        echo "Usage: $0 {on|off|stop|status}" >&2
        exit 2
        ;;
esac
