import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.scheduler import _parse_trigger


class TestParseTrigger:
    def test_cron_five_parts(self):
        trigger = _parse_trigger("0 6 * * *")
        assert isinstance(trigger, CronTrigger)

    def test_cron_every_minute(self):
        trigger = _parse_trigger("* * * * *")
        assert isinstance(trigger, CronTrigger)

    def test_interval_minutes(self):
        trigger = _parse_trigger("interval:minutes=30")
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_hours(self):
        trigger = _parse_trigger("interval:hours=1")
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_multi_param(self):
        trigger = _parse_trigger("interval:hours=1,minutes=30")
        assert isinstance(trigger, IntervalTrigger)

    def test_invalid_cron_raises(self):
        with pytest.raises(ValueError):
            _parse_trigger("not a valid schedule")

    def test_cron_midnight(self):
        trigger = _parse_trigger("0 0 * * *")
        assert isinstance(trigger, CronTrigger)
