from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

from zodiac_core.schemas import UtcDatetime, ensure_utc


class UtcDatetimeModel(BaseModel):
    value: UtcDatetime


class TestEnsureUtc:
    """Test ensure_utc used by UtcDatetime."""

    def test_naive_datetime_gets_utc(self):
        """Naive datetime should get tzinfo=UTC."""
        naive = datetime(2026, 2, 25, 12, 0, 0)
        result = ensure_utc(naive)
        assert result.tzinfo == timezone.utc
        assert result.year == 2026 and result.month == 2 and result.day == 25

    def test_aware_datetime_converted_to_utc(self):
        """Aware datetime should be converted to UTC."""
        # UTC+8
        aware = datetime(2026, 2, 25, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        result = ensure_utc(aware)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # 20 - 8

    def test_non_datetime_returned_unchanged(self):
        """Non-datetime value should be returned as-is (covers L18)."""
        assert ensure_utc(None) is None
        assert ensure_utc(42) == 42
        assert ensure_utc("hello") == "hello"


class TestUtcDatetime:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-08-03T12:00:00+09:00", datetime(2026, 8, 3, 3, tzinfo=timezone.utc)),
            ("2026-08-03T12:00:00", datetime(2026, 8, 3, 12, tzinfo=timezone.utc)),
        ],
    )
    def test_string_input_is_normalized_to_aware_utc(self, value, expected):
        result = UtcDatetimeModel(value=value).value

        assert result.tzinfo == timezone.utc
        assert result == expected
