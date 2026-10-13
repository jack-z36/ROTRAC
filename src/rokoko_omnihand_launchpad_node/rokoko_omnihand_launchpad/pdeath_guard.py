"""Parent-death guard: extend PDEATHSIG coverage to grandchildren.

``spawn_managed_process`` arms PR_SET_PDEATHSIG on its direct child only.
Business nodes are started through ``ros2 run`` / wrapper scripts that spawn
the real process as their own child, so when the orchestrator dies the direct
child is SIGKILLed and the real node process is orphaned (it stays in the ROS
graph and blocks later starts).  The guard runs as the direct child instead:
on parent death it receives SIGTERM, forwards it to the whole process group,
escalates to SIGKILL after a bounded wait, and only then exits.

The SIGTERM handler only records a flag; killpg/exit happen in the main loop.
Doing process work inside the handler raced against ``Popen``'s fork/exec
(the handler ran with the child still unborn, set SIGTERM to ``SIG_IGN``, and
never completed), which leaked both the guard and its child forever.
"""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time


PR_SET_PDEATHSIG = 1
ESCALATION_TIMEOUT_SEC = 5.0

_child: subprocess.Popen[bytes] | None = None
_term_signal: int | None = None


def _arm_pdeathsig() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")


def _mark_stopped(signum: int, _frame: object) -> None:
    """Record the stop request; all cleanup happens in the main loop."""
    global _term_signal
    if _term_signal is None:
        _term_signal = signum


def _shutdown_group() -> None:
    try:
        os.killpg(0, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + ESCALATION_TIMEOUT_SEC
    while _child is not None and _child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if _child is not None and _child.poll() is None:
        try:
            os.killpg(0, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[2:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: pdeath_guard -- COMMAND [ARGS...]")
    _arm_pdeathsig()
    signal.signal(signal.SIGTERM, _mark_stopped)
    if os.getppid() == 1:
        # 父进程在 prctl 之前已经退出：内核无法补发信号，自行触发清理。
        _mark_stopped(signal.SIGTERM)
    global _child
    _child = subprocess.Popen(args)
    while _term_signal is None and _child.poll() is None:
        time.sleep(0.05)
    if _term_signal is None:
        sys.exit(_child.wait())
    _shutdown_group()
    sys.exit(128 + _term_signal)


if __name__ == "__main__":
    main()
