from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from __package_name__.main import greeting, main

if TYPE_CHECKING:
    import pytest


def test_greeting_returns_app_greeting() -> None:
    expected = "Hello from __project_name__!"
    assert greeting() == expected


def test_main_logs_greeting(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        main()
    assert greeting() in caplog.messages
