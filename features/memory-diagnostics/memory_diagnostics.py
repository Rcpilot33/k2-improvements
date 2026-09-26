# Low-overhead memory and fragmentation recorder for constrained K2 hosts.

import os
import queue
import threading
import time


MEMINFO_KEYS = (
    "MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached",
    "SReclaimable", "Shmem", "SwapTotal", "SwapFree",
)


def read_key_values(path, wanted):
    values = {}
    with open(path, "r") as handle:
        for raw_line in handle:
            name, separator, remainder = raw_line.partition(":")
            if separator and name in wanted:
                fields = remainder.split()
                if fields:
                    try:
                        values[name] = int(fields[0])
                    except ValueError:
                        pass
    return values


def read_buddyinfo(path="/proc/buddyinfo"):
    zones = []
    with open(path, "r") as handle:
        for raw_line in handle:
            fields = raw_line.replace(",", "").split()
            if "zone" not in fields:
                continue
            index = fields.index("zone")
            if len(fields) <= index + 2:
                continue
            zone = fields[index + 1]
            counts = fields[index + 2:]
            if counts and all(value.isdigit() for value in counts):
                zones.append("%s:%s" % (zone, ",".join(counts)))
    return ";".join(zones) or "unavailable"


def read_pagetypeinfo(path="/proc/pagetypeinfo", zone_name="Normal"):
    types = []
    try:
        handle = open(path, "r")
    except OSError:
        return "unavailable"
    with handle:
        for raw_line in handle:
            fields = raw_line.replace(",", "").split()
            if "zone" not in fields or "type" not in fields:
                continue
            zone_index = fields.index("zone")
            type_index = fields.index("type")
            if len(fields) <= type_index + 2 or fields[zone_index + 1] != zone_name:
                continue
            migrate_type = fields[type_index + 1]
            counts = fields[type_index + 2:]
            if counts and all(value.isdigit() for value in counts):
                types.append("%s:%s" % (migrate_type, ",".join(counts)))
    return ";".join(types) or "unavailable"


def read_process_rss(proc_root="/proc", limit=10):
    processes = []
    for entry in os.listdir(proc_root):
        if not entry.isdigit():
            continue
        name = None
        rss = None
        try:
            with open(os.path.join(proc_root, entry, "status"), "r") as handle:
                for raw_line in handle:
                    if raw_line.startswith("Name:"):
                        name = raw_line.split(":", 1)[1].strip()
                    elif raw_line.startswith("VmRSS:"):
                        fields = raw_line.split()
                        if len(fields) >= 2:
                            rss = int(fields[1])
                    if name is not None and rss is not None:
                        break
        except (OSError, ValueError):
            continue
        if name is not None and rss is not None:
            processes.append((rss, int(entry), name.replace(" ", "_")))
    processes.sort(reverse=True)
    return processes[:limit]


def format_processes(processes):
    return ",".join(
        "%s[%d]:%dkB" % (name, pid, rss)
        for rss, pid, name in processes
    ) or "none"


class MemoryDiagnostics:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.interval = config.getfloat("interval", 10.0, minval=5.0)
        self.process_interval = config.getfloat(
            "process_interval", 60.0, minval=self.interval)
        self.log_path = config.get(
            "log_path",
            "/mnt/UDISK/printer_data/logs/memory-diagnostics.log",
        )
        self.max_bytes = config.getint(
            "max_bytes", 2 * 1024 * 1024, minval=64 * 1024)
        self.backups = config.getint("backups", 3, minval=1, maxval=10)
        self.process_limit = config.getint(
            "process_limit", 10, minval=1, maxval=50)
        self.last_process_sample = -self.process_interval
        self.last_print_state = None
        self.last_status = {}
        self.failure_reported = False
        self.pending_samples = queue.Queue(maxsize=1)
        self.worker = threading.Thread(
            target=self._worker_loop,
            name="k2-memory-diagnostics",
            daemon=True,
        )
        self.worker.start()
        self.reactor.register_timer(self._sample, self.reactor.NOW)

    def get_status(self, eventtime):
        return dict(self.last_status)

    def _rotate(self):
        try:
            if os.path.getsize(self.log_path) < self.max_bytes:
                return
        except OSError:
            return
        oldest = "%s.%d" % (self.log_path, self.backups)
        try:
            os.unlink(oldest)
        except OSError:
            pass
        for number in range(self.backups - 1, 0, -1):
            source = "%s.%d" % (self.log_path, number)
            destination = "%s.%d" % (self.log_path, number + 1)
            try:
                os.replace(source, destination)
            except OSError:
                pass
        try:
            os.replace(self.log_path, self.log_path + ".1")
        except OSError:
            pass

    def _print_state(self, eventtime):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return "unavailable"
        try:
            return str(print_stats.get_status(eventtime).get("state", "unknown"))
        except Exception:
            return "error"

    def _write(self, line):
        directory = os.path.dirname(self.log_path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        self._rotate()
        with open(self.log_path, "a") as handle:
            handle.write(line + "\n")

    def _collect_sample(self, eventtime, print_state):
        try:
            memory = read_key_values("/proc/meminfo", MEMINFO_KEYS)
            self_rss = read_key_values("/proc/self/status", ("VmRSS",)).get(
                "VmRSS", -1)
            state_changed = self.last_print_state is not None and \
                print_state != self.last_print_state
            reason = "state:%s>%s" % (self.last_print_state, print_state) \
                if state_changed else "periodic"
            fields = [
                time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "uptime=%.1f" % eventtime,
                "reason=%s" % reason,
                "print=%s" % print_state.replace(" ", "_"),
            ]
            for key in MEMINFO_KEYS:
                fields.append("%s=%d" % (key.lower(), memory.get(key, -1)))
            fields.extend((
                "klippy_rss=%d" % self_rss,
                "buddy=%s" % read_buddyinfo(),
            ))
            include_processes = state_changed or \
                eventtime - self.last_process_sample >= self.process_interval
            if include_processes:
                fields.append("pagetype=%s" % read_pagetypeinfo())
                fields.append(
                    "top=%s" % format_processes(
                        read_process_rss(limit=self.process_limit)))
                self.last_process_sample = eventtime
            self._write(" ".join(fields))
            self.last_status = {
                "mem_available_kb": memory.get("MemAvailable", -1),
                "klippy_rss_kb": self_rss,
                "print_state": print_state,
                "last_sample_uptime": eventtime,
                "log_path": self.log_path,
            }
            self.last_print_state = print_state
            self.failure_reported = False
        except Exception as err:
            if not self.failure_reported:
                try:
                    self._write(
                        "%s uptime=%.1f reason=recorder_error error=%s" % (
                            time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            eventtime,
                            str(err).replace("\n", " "),
                        ))
                except Exception:
                    pass
                self.failure_reported = True

    def _worker_loop(self):
        while True:
            eventtime, print_state = self.pending_samples.get()
            try:
                self._collect_sample(eventtime, print_state)
            finally:
                self.pending_samples.task_done()

    def _sample(self, eventtime):
        # Klipper timer callbacks execute on the motion reactor. Keep this path
        # bounded: capture only the in-memory print state and let the worker do
        # all procfs traversal, flash writes, rotation, and formatting.
        print_state = self._print_state(eventtime)
        try:
            self.pending_samples.put_nowait((eventtime, print_state))
        except queue.Full:
            pass
        return eventtime + self.interval


def load_config(config):
    return MemoryDiagnostics(config)
