"""Small process lifecycle primitives shared by launchers and supervision."""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class WaitableProcess(Protocol):
    def wait(self, timeout: float | None = None) -> int: ...


def wait_for_process_exit(process: WaitableProcess, *, timeout_s: float) -> bool:
    try:
        process.wait(timeout=max(0.0, timeout_s))
        return True
    except subprocess.TimeoutExpired:
        return False


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=3,
        )
        return f'"{pid}"' in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Linux zombies are no longer running; waiting on kill(pid, 0) cannot reap them.
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        stat = stat_path.read_text()
    except FileNotFoundError:
        return not Path("/proc").is_dir()
    except PermissionError as exc:
        logger.debug("Cannot inspect process state pid=%s", pid, exc_info=exc)
        return True
    return stat.rsplit(")", 1)[-1].strip().split()[0] != "Z"


def terminate_pid(pid: int, *, timeout_s: float = 2.0) -> bool:
    if not is_pid_running(pid):
        return True
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=max(0.1, timeout_s))
        if result.returncode != 0:
            logger.warning("taskkill failed pid=%s: %s", pid, result.stderr.decode(errors="replace"))
        return not is_pid_running(pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + max(0.1, timeout_s)
        while time.monotonic() < deadline:
            if not is_pid_running(pid):
                return True
            time.sleep(0.05)
    return not is_pid_running(pid)
