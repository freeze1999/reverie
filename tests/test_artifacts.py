"""Envelope parsing and the sandbox path-guard."""
from datetime import datetime

from reverie import ArtifactWriter, parse_envelope

SAMPLE = """Here is what I did.
<<JOURNAL>>Read the notes and tidied the draft.<<END>>
<<MEMORY>>The draft on X now has a clean intro.<<END>>
<<KEEP:intro-draft>>Once, in the quiet hours, the engine woke.<<END>>
<<ACTIVITY>>tidied a draft<<END>>
<<NOTE>>left you a cleaner intro on X<<END>>
"""


def test_parse_full_envelope():
    art = parse_envelope(SAMPLE)
    assert art.journal.startswith("Read the notes")
    assert "clean intro" in art.memory
    assert art.activity == "tidied a draft"
    assert art.note.startswith("left you")
    assert art.keep == ("intro-draft", "Once, in the quiet hours, the engine woke.")


def test_parse_partial_envelope():
    art = parse_envelope("<<JOURNAL>>only this<<END>>")
    assert art.journal == "only this"
    assert art.memory == "" and art.keep is None


def test_parse_garbage_does_not_raise():
    art = parse_envelope("no tags here at all")
    assert art.journal == "" and art.keep is None


def test_keep_is_written_inside_box(tmp_path):
    w = ArtifactWriter(tmp_path)
    art = parse_envelope("<<KEEP:poem>>a small poem<<END>>")
    errors = w.write(art, raw="", action_class="TEXT_ONLY", now=datetime.now())
    assert errors == []
    written = (tmp_path / "box" / "poem.md").read_text()
    assert written == "a small poem"


def test_keep_path_traversal_is_blocked(tmp_path):
    w = ArtifactWriter(tmp_path)
    # Attempt to escape the box via a traversal filename.
    art = parse_envelope("<<KEEP:../../etc/evil>>nope<<END>>")
    errors = w.write(art, raw="", action_class="TEXT_ONLY", now=datetime.now())
    # The traversal is stripped to a basename, so it lands safely inside box/.
    assert not (tmp_path.parent.parent / "etc" / "evil").exists()
    assert (tmp_path / "box" / "evil.md").exists()


def test_empty_keep_filename_is_skipped(tmp_path):
    w = ArtifactWriter(tmp_path)
    art = parse_envelope("<<KEEP:>>body with no name<<END>>")
    errors = w.write(art, raw="", action_class="TEXT_ONLY", now=datetime.now())
    assert any("empty name" in e for e in errors)
    assert not (tmp_path / "box").exists() or not any((tmp_path / "box").iterdir())


def test_journal_always_written(tmp_path):
    w = ArtifactWriter(tmp_path)
    art = parse_envelope("<<JOURNAL>>entry<<END>>")
    w.write(art, raw="fallback", action_class="TEXT_ONLY", now=datetime(2026, 6, 21, 14, 30))
    files = list((tmp_path / "journal").glob("*.md"))
    assert len(files) == 1 and "entry" in files[0].read_text()
