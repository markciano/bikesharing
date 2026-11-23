"""Contract tests of the log events registry, the pipeline's side.

The registry is reference data that capture and the pipeline both read, so it has a
schema and no vectors (d009, Event registry schema). The events the pipeline writes are
enumerated from the Event values that ``core/events.py`` builds.
"""

import ast
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from bikesharing.core import events

REPO = Path(__file__).resolve().parents[3]
CONTRACTS = REPO / "contracts"
SCHEMA = json.loads((CONTRACTS / "log-events.schema.json").read_text())
REGISTRY = json.loads((CONTRACTS / "log-events.registry.json").read_text())
PIPELINE_EVENTS: list[dict[str, Any]] = [
    e for e in REGISTRY["events"] if e["component"] == "pipeline"
]


def _levels_of(node: ast.expr) -> set[str]:
    """Return the levels an ``Event`` call can carry in its level argument."""
    if isinstance(node, ast.Constant):
        return {str(node.value)}
    if isinstance(node, ast.IfExp):
        return _levels_of(node.body) | _levels_of(node.orelse)
    if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "_RULE_LEVELS":
        return set(events._RULE_LEVELS.values())
    raise AssertionError(f"unsupported level expression: {ast.unparse(node)}")


def _written_events() -> dict[str, set[str]]:
    """Return each event ``core/events.py`` builds, with the levels it uses."""
    tree = ast.parse(Path(events.__file__).read_text())
    written: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        is_event = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Event"
        )
        if is_event:
            assert isinstance(node, ast.Call)
            name = node.args[2]
            assert isinstance(name, ast.Constant), ast.unparse(node)
            written.setdefault(str(name.value), set()).update(_levels_of(node.args[1]))
    return written


# Verifies d009 R25
def test_registry_is_valid_against_its_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)

    errors = list(Draft202012Validator(SCHEMA).iter_errors(REGISTRY))

    assert errors == []


# Verifies d009 R25
def test_registry_lists_each_pair_of_component_and_event_once() -> None:
    pairs = [f"{e['component']}/{e['event']}" for e in REGISTRY["events"]]

    assert [p for i, p in enumerate(pairs) if p in pairs[:i]] == []


# Verifies d009 R25
def test_registry_holds_exactly_the_events_the_pipeline_writes() -> None:
    assert {e["event"] for e in PIPELINE_EVENTS} == set(_written_events())


# Verifies d009 R27
def test_registry_registers_each_pipeline_event_at_the_levels_it_uses() -> None:
    registered = {e["event"]: set(e["levels"]) for e in PIPELINE_EVENTS}

    for event, levels in _written_events().items():
        assert levels <= registered[event], f"levels of {event}"
