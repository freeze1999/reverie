"""The Runner: fire-once-per-gap and re-arm, end to end against tmp state."""
from datetime import datetime, timedelta, timezone

from reverie import (
    ContextBuilder,
    GatePolicy,
    MockBackend,
    ReverieEngine,
    Runner,
    static_source,
)

KL = timezone(timedelta(hours=8))


def _runner(tmp_path, last_input_box):
    cb = ContextBuilder(sources=[static_source(mood="quiet")], tools="write_file")
    eng = ReverieEngine(
        llm=MockBackend(
            {
                "look outward": "content",
                "come back down": "nothing this time",
            }
        ),
        context_builder=cb,
        persona="test",
    )
    return Runner(
        engine=eng,
        state_dir=tmp_path,
        last_input_ts=lambda: last_input_box[0],
        is_available=lambda: True,
        policy=GatePolicy(),
    )


def test_fires_once_then_holds_until_new_input(tmp_path):
    base = datetime(2026, 6, 21, 14, 0, tzinfo=KL)
    last_input = [base.timestamp() - 70 * 60]  # 70 min ago
    runner = _runner(tmp_path, last_input)

    d1, out1 = runner.tick(base)
    assert d1.fire and out1 is not None

    # Next tick, no new input -> must NOT fire again.
    d2, out2 = runner.tick(base + timedelta(minutes=10))
    assert not d2.fire and out2 is None and "already fired" in d2.reason

    # A new input arrives -> re-arm and fire again.
    later = base + timedelta(minutes=90)
    last_input[0] = (later - timedelta(minutes=70)).timestamp()
    d3, out3 = runner.tick(later)
    assert d3.fire and out3 is not None


def test_fire_writes_a_report(tmp_path):
    base = datetime(2026, 6, 21, 14, 0, tzinfo=KL)
    runner = _runner(tmp_path, [base.timestamp() - 70 * 60])
    runner.tick(base)
    reports = list((tmp_path / "fires").glob("*.json"))
    assert len(reports) == 1
