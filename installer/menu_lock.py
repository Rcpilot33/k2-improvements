"""Hold the installer lock across menu execs. Linux releases it on process exit."""
import errno
import fcntl
import os
from pathlib import Path
import stat
import sys
import tempfile


def launch(lock, command):
    # This inode is permanent. Removing it would let a second menu lock a
    # different inode while the first menu is still running.
    fd = os.open(str(lock) + ".guard", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    # Keep the menu lock away from low descriptors used by shell redirections.
    guard_fd = fcntl.fcntl(fd, fcntl.F_DUPFD, 32)
    os.close(fd)
    fd = guard_fd
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("unsafe installer lock file")
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno not in (errno.EACCES, errno.EAGAIN):
            raise
        raise ValueError("another K2 installer is running") from exc

    # Older checkouts and an in-place update from their menu use this PID.
    lock.mkdir(mode=0o700, exist_ok=True)
    info = lock.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("unsafe installer lock directory")
    marker = lock / "pid"
    if marker.exists():
        owner = marker.read_text().strip()
        if owner.isdecimal() and int(owner) != os.getpid():
            try:
                argv = (Path("/proc") / owner / "cmdline").read_bytes().split(b"\0")
            except (FileNotFoundError, ProcessLookupError):
                argv = []
            if any(os.path.basename(arg) == b"menu.sh" for arg in argv):
                raise ValueError("another K2 installer is running (PID %s)" % owner)
    with tempfile.NamedTemporaryFile(mode="w", dir=str(lock), delete=False) as tmp:
        tmp.write("%d\n" % os.getpid())
    os.replace(tmp.name, str(marker))
    os.set_inheritable(fd, True)
    os.environ["K2_MENU_LOCK_PID"] = str(os.getpid())
    os.execvp(command[0], command)


if __name__ == "__main__":
    try:
        launch(Path(sys.argv[1]), sys.argv[2:])
    except (OSError, ValueError) as exc:
        sys.exit("ERROR: %s" % exc)
