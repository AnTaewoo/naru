"""T6.1 고침 — systemd 가 워커를 멈출 때(SIGTERM) 0 으로 끝난다.

태우 2026-11-09: 재시작 때 이전 프로세스가 "status=1/FAILURE" 로 찍혔다(uv 가 시그널로 죽은 자식을
1 로 돌려준다). 실제 시그널을 이 프로세스에 보내 본다.
"""

import signal

import pytest

from naru_ai.worker import exit_on_sigterm


def test_sigterm_exits_zero() -> None:
    before = signal.getsignal(signal.SIGTERM)
    try:
        exit_on_sigterm()
        with pytest.raises(SystemExit) as stop:
            signal.raise_signal(signal.SIGTERM)
        assert stop.value.code == 0
    finally:
        signal.signal(signal.SIGTERM, before)
