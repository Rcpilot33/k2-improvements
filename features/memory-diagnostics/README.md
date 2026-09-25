# Memory diagnostics

This temporary diagnostic component records the evidence needed to distinguish
a userspace memory leak from the K2 Plus kernel's physical-memory
fragmentation. It does not alter memory policy, add swap, reclaim cache, or
change printer motion.

The recorder runs inside Klippy without subprocesses and samples every 10
seconds. Procfs reads, process enumeration, and log writes run on a dedicated
daemon worker so slow kernel or UDISK operations cannot block Klipper's motion
reactor. Once per minute and whenever the print state changes, it also records
the largest resident processes and the kernel's Normal-zone allocation blocks
by migration type.

Logs are stored outside the RAM-backed filesystem at:

```text
/mnt/UDISK/printer_data/logs/memory-diagnostics.log
```

The active log is limited to 2 MiB with three retained backups. The maximum
disk use is therefore approximately 8 MiB. Installation requires a protected
Klippy code restart. Uninstallation retains existing logs for analysis.

After another disconnect or before a power cycle, copy the active log and its
numbered backups along with `klippy.log`, `moonraker.log`, and the OOM section
from `dmesg`.
