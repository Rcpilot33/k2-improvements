"""K2 native device cards, exposed through Moonraker's authenticated API.

Protocol reference: Creality Print's Device Manager (SetFanSpeed,
GetBoxsInfo, feedInOrOutMaterial). No arbitrary native commands are accepted.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import time

from tornado.websocket import websocket_connect
from ..common import RequestType

FANS = {"model": ("modelFanPct", 0), "case": ("caseFanPct", 1),
        "side": ("auxiliaryFanPct", 2)}
QUERY = {"boxsInfo": 1, "boxConfig": 1, "state": 1, "feedState": 1,
         "modelFanPct": 1, "caseFanPct": 1, "auxiliaryFanPct": 1}


def percentage(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value) if math.isfinite(value) and 0 <= value <= 100 else None


def slots_from_info(info):
    """Treat each boxsInfo response as a snapshot; never retain removed slots."""
    slots = []
    boxes = info.get("materialBoxs", []) if isinstance(info, dict) else []
    if not isinstance(boxes, list):
        return slots
    seen = set()
    for box in boxes:
        if not isinstance(box, dict):
            continue
        box_id, box_type = box.get("id"), box.get("type")
        if type(box_id) is not int or type(box_type) is not int:
            continue
        external = box_type == 1
        if not ((external and box_id == 0) or
                (box_type == 0 and 1 <= box_id <= 4 and box.get("state"))):
            continue
        materials = box.get("materials", [])
        if not isinstance(materials, list):
            continue
        for material in materials:
            if not isinstance(material, dict):
                continue
            slot_id = material.get("id")
            if type(slot_id) is not int or not 0 <= slot_id < (1 if external else 4):
                continue
            key = (box_id, slot_id)
            if key in seen:
                continue
            seen.add(key)
            color = str(material.get("color", "")).lstrip("#")
            if len(color) == 7 and color.startswith('0'):
                color = color[1:]
            if len(color) == 8:
                color = color[2:]
            color = "#" + color if len(color) == 6 and all(
                c in "0123456789abcdefABCDEF" for c in color) else "#777777"
            material_type = material.get("type", "")
            occupied = material.get("state") in (1, 2) and bool(material_type)
            slots.append({
                "box_id": box_id, "slot_id": slot_id, "external": external,
                "label": "Spool Holder" if external else f"{box_id}{chr(65 + slot_id)}",
                "material": str(material_type)[:80],
                "name": str(material.get("name", ""))[:120],
                "color": color, "occupied": occupied,
                "percent": percentage(material.get("percent")) if occupied else None,
                "humidity": percentage(box.get("humidity")),
            })
    return slots


class K2Device:
    def __init__(self, config):
        self.server = config.get_server()
        self.ws = None
        self.task = None
        self.closing = False
        self.raw = {}
        self.seen = {}
        self.last_message = 0.
        self.pending_until = 0.
        self.command_lock = asyncio.Lock()
        self.server.register_endpoint("/server/k2_device/status", RequestType.GET,
                                      self._status_request)
        self.server.register_endpoint("/server/k2_device/fan", RequestType.POST,
                                      self._fan_request)
        self.server.register_endpoint("/server/k2_device/filament", RequestType.POST,
                                      self._filament_request)
        self.server.register_notification("k2_device:status_changed", "k2_device_status_changed")

    async def component_init(self):
        self.task = asyncio.create_task(self._connect())

    def _fresh(self, key):
        # Native status is a full snapshot on connect followed by deltas.
        # Unchanged fan speeds and idle flags remain valid while messages
        # arrive on this connection. CFS snapshots still expire independently.
        updated = self.seen.get(key) if key in ('boxsInfo', 'boxConfig') else self.last_message
        return (self.ws is not None and key in self.seen and updated is not None
                and time.monotonic() - updated < 10.)

    def status(self):
        fresh = self._fresh("state") and self._fresh("feedState")
        idle = fresh and self.raw.get("state") in (0, 2, 3, 4)
        idle = idle and self.raw.get("feedState") in (0, 3, 14)
        pending = time.monotonic() < self.pending_until
        return {
            "connected": self.ws is not None,
            "fans": {name: percentage(self.raw.get(key)) if self._fresh(key) else None
                     for name, (key, _) in FANS.items()},
            "slots": slots_from_info(self.raw.get("boxsInfo")) if self._fresh("boxsInfo") else [],
            "can_feed": bool(idle and not pending and self._fresh("boxsInfo")),
            "pending": pending,
            "feed_state": self.raw.get("feedState") if fresh else None,
            "auto_refill": self.raw.get("boxConfig", {}).get("autoRefill") == 1
                           if self._fresh("boxConfig") else None,
        }

    def _notify(self):
        self.server.send_event("k2_device:status_changed", self.status())

    async def _status_request(self, request):
        return self.status()

    def _require_ready(self):
        connection = self.server.lookup_component("klippy_connection")
        if not connection.is_ready():
            raise self.server.error("Klipper is not ready", 409)
        if self.ws is None or not self._fresh("state"):
            raise self.server.error("Creality device service is disconnected or stale", 503)

    async def _fan_request(self, request):
        async with self.command_lock:
            self._require_ready()
            name = request.get_str("fan")
            speed = request.get_int("speed")
            if name not in FANS or not 0 <= speed <= 100:
                raise self.server.error("Invalid fan or speed", 400)
            key, index = FANS[name]
            if not self._fresh(key):
                raise self.server.error("Fan status is unavailable", 409)
            # Same P mapping and rounding as Creality Print. Use Moonraker for
            # G-code so existing Klipper errors/permissions remain in effect.
            api = self.server.lookup_component("klippy_apis")
            await api.run_gcode(f"M106 P{index} S{int(speed * 255 / 100 + .5)}")
            return {"sent": True}

    async def _filament_request(self, request):
        async with self.command_lock:
            self._require_ready()
            box_id = request.get_int("box_id")
            slot_id = request.get_int("slot_id")
            action = request.get_str("action")
            state = self.status()
            if action not in ("feed", "retract"):
                raise self.server.error("Invalid filament action", 400)
            if not state["can_feed"]:
                raise self.server.error("Printer is busy or filament status is unavailable", 409)
            # Query Klipper as well as the native state: never accept a stale
            # native idle flag during a print, pause or startup.
            api = self.server.lookup_component("klippy_apis")
            socket = self.ws
            objects = await api.query_objects({"print_stats": None})
            if objects.get("print_stats", {}).get("state") not in ("standby", "complete", "cancelled", "error"):
                raise self.server.error("Filament controls require an idle printer", 409)
            slot = next((s for s in state["slots"]
                         if s["box_id"] == box_id and s["slot_id"] == slot_id), None)
            if slot is None or not slot["occupied"]:
                raise self.server.error("Select an occupied slot with a known material", 400)
            # The awaited Klipper query may have allowed a disconnect or update.
            latest = self.status()
            if (self.ws is not socket or not latest["can_feed"] or not any(
                    s["box_id"] == box_id and s["slot_id"] == slot_id and s["occupied"]
                    for s in latest["slots"])):
                raise self.server.error("Device state changed; refresh and retry", 409)
            self.pending_until = time.monotonic() + 15.
            self._notify()
            await self.ws.write_message(json.dumps({"method": "set", "params": {
                "feedInOrOut": {"boxId": box_id, "materialId": slot_id,
                                "isFeed": int(action == "feed")}}}))
            # Native transport has no correlated completion response. Never
            # report physical success or retry a movement automatically.
            return {"sent": True}

    async def _poll(self):
        while self.ws is not None:
            await self.ws.write_message(json.dumps({"method": "get", "params": QUERY}))
            self._notify()  # Also expires stale fields if only some keys arrive.
            await asyncio.sleep(3.)

    async def _connect(self):
        while not self.closing:
            poll = None
            try:
                # Fixed loopback destination: follows the selected Moonraker
                # printer and works with HTTPS and remote Fluidd connections.
                self.ws = await websocket_connect("ws://127.0.0.1:9999", connect_timeout=5.,
                                                  max_message_size=1024 * 1024)
                self.raw, self.seen = {}, {}
                self.last_message = 0.
                poll = asyncio.create_task(self._poll())
                while True:
                    message = await asyncio.wait_for(self.ws.read_message(), 12.)
                    if message is None:
                        break
                    try:
                        data = json.loads(message)
                        if not isinstance(data, dict):
                            continue
                        data = data.get("params", data)
                        if not isinstance(data, dict):
                            continue
                        self.last_message = time.monotonic()
                        for key in QUERY:
                            if key in data and (key != "boxConfig" or isinstance(data[key], dict)):
                                self.raw[key] = data[key]
                                self.seen[key] = time.monotonic()
                        self._notify()
                    except (ValueError, TypeError):
                        continue
            except asyncio.CancelledError:
                raise
            except Exception:
                # Service may be absent during boot. Reconnect without flooding logs.
                pass
            finally:
                if poll is not None:
                    poll.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await poll
                if self.ws is not None:
                    self.ws.close()
                self.ws = None
                self.raw, self.seen = {}, {}
                self.last_message = 0.
                self._notify()
            if not self.closing:
                await asyncio.sleep(5.)

    async def close(self):
        self.closing = True
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task


def load_component(config):
    return K2Device(config)
