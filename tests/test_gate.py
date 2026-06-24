"""Exhaustive tests for the gate, the safety-critical pure function."""
from datetime import datetime, timedelta, timezone

from reverie import GatePolicy, GateState, decide

KL = timezone(timedelta(hours=8))


def at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=KL)


def ago(ref, minutes):
    return ref.timestamp() - minutes * 60


BASE = at(2026, 6, 21, 14, 0)  # 14:00, inside the default 12:00-02:00 window


def test_fires_when_idle_armed_and_in_window():
    d = decide(BASE, ago(BASE, 70), available=True, state=GateState())
    assert d.fire


def test_not_idle_enough():
    d = decide(BASE, ago(BASE, 30), available=True, state=GateState())
    assert not d.fire and "not idle enough" in d.reason


def test_unavailable_blocks_everything():
    d = decide(BASE, ago(BASE, 70), available=False, state=GateState())
    assert not d.fire and "unavailable" in d.reason


def test_outside_window_morning():
    morning = at(2026, 6, 21, 10, 0)  # slept in; 10:00 is outside 12:00-02:00
    d = decide(morning, ago(morning, 70), available=True, state=GateState())
    assert not d.fire and "window" in d.reason


def test_outside_window_afternoon_gap():
    three_am = at(2026, 6, 21, 3, 0)
    d = decide(three_am, ago(three_am, 70), available=True, state=GateState())
    assert not d.fire


def test_no_input_on_record():
    d = decide(BASE, 0.0, available=True, state=GateState())
    assert not d.fire and "no external input" in d.reason


def test_fire_once_per_gap():
    # Already fired against this exact input timestamp -> must not fire again.
    last = ago(BASE, 70)
    state = GateState(last_fired_input_ts=last)
    d = decide(BASE, last, available=True, state=state)
    assert not d.fire and "already fired" in d.reason


def test_rearms_on_newer_input():
    # Fired against an older input; a newer input has since arrived -> re-arm.
    state = GateState(last_fired_input_ts=ago(BASE, 200))
    d = decide(BASE, ago(BASE, 70), available=True, state=state)
    assert d.fire


def test_window_edges():
    # 01:00 is inside the wrapped window; 12:00 is the inclusive start.
    one_am = at(2026, 6, 21, 1, 0)
    noon = at(2026, 6, 21, 12, 0)
    assert decide(one_am, ago(one_am, 70), True, GateState()).fire
    assert decide(noon, ago(noon, 70), True, GateState()).fire


def test_non_wrapping_window():
    # A window that does not cross midnight (09:00-17:00).
    pol = GatePolicy(window_start_hour=9, window_end_hour=17)
    assert pol.in_window(at(2026, 6, 21, 9, 0))
    assert pol.in_window(at(2026, 6, 21, 16, 59))
    assert not pol.in_window(at(2026, 6, 21, 17, 0))
    assert not pol.in_window(at(2026, 6, 21, 3, 0))
