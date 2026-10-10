import subprocess
import sys

from f8pysdk.process_control import is_pid_running, terminate_pid, wait_for_process_exit


def test_terminate_and_reap_child() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert is_pid_running(child.pid)
        assert not wait_for_process_exit(child, timeout_s=0.01)
        assert terminate_pid(child.pid, timeout_s=1)
        assert wait_for_process_exit(child, timeout_s=2)
        assert not is_pid_running(child.pid)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_invalid_pid_is_already_stopped() -> None:
    assert not is_pid_running(0)
    assert terminate_pid(0)
