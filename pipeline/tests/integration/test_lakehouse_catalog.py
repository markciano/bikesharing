"""The lakehouse catalog has one entry per pipeline table.

``docs/lakehouse.md`` explains each table's settings, which live in ``settings.py``;
this test keeps the two in step, so a table added or removed without its entry fails
CI (d010, Table settings and catalog).
"""

import re
from pathlib import Path

from bikesharing.core.settings import TABLE_PATHS

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "docs" / "lakehouse.md"
ENTRY_PARTS = ["Partitions", "Readers", "Compaction", "Retention", "Log and vacuum"]


def _entries(markdown: str) -> dict[str, str]:
    """Return each ``###`` entry under ``## Tables``, by name without backticks."""
    section = re.search(
        r"^## Tables\n(.*?)(?=^## |\Z)", markdown, re.MULTILINE | re.DOTALL
    )
    assert section, "docs/lakehouse.md has no '## Tables' section"
    parts = re.split(r"^### (.+)$", section[1], flags=re.MULTILINE)[1:]
    return {
        name.strip().strip("`"): body for name, body in zip(parts[::2], parts[1::2])
    }


def test_catalog_tables_are_the_table_paths_keys() -> None:
    entries = _entries(CATALOG.read_text())

    assert sorted(entries) == sorted(TABLE_PATHS)


def test_catalog_entries_have_their_five_parts_in_order() -> None:
    entries = _entries(CATALOG.read_text())

    for name, body in entries.items():
        parts = re.findall(r"^- \*\*(.+?):\*\*", body, re.MULTILINE)
        assert parts == ENTRY_PARTS, name
