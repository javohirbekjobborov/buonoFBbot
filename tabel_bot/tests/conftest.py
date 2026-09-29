import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tabel.shifts import TZ  # noqa: E402
from tabel.storage import Storage  # noqa: E402


def at(day: str, clock: str, second: int = 0) -> datetime:
    """at('29.09', '08:36') -> 2026-09-29 08:36 Toshkent vaqti."""
    dd, mm = day.split(".")
    hh, mi = clock.split(":")
    return datetime(2026, int(mm), int(dd), int(hh), int(mi), second, tzinfo=TZ)


@pytest.fixture
def db():
    storage = Storage(":memory:")
    yield storage
    storage.close()
