"""Unit tests for the Jira defect sync: parsing and payload building, no network."""
from tools.jira_sync import DEFECTS_DOC, build_issue, parse_defects

SAMPLE = """## Sample defects

### DEF-900 (S2 / P1) API: something `breaks` badly

- **Found by:** TC-1
- **Resolution:** fixed. Verified, closed.

### DEF-901 (S4 / P3) UI: cosmetic thing

- **Status:** open, under review.

## Another section
- not part of any defect
"""


def test_parses_id_severity_priority_and_title():
    d = parse_defects(SAMPLE)[0]
    assert (d.key, d.severity, d.priority, d.title) == ("DEF-900", "S2", "P1", "API: something `breaks` badly")


def test_body_stops_at_next_heading():
    defects = parse_defects(SAMPLE)
    assert len(defects) == 2
    assert all("not part of any defect" not in l for l in defects[1].lines)


def test_closed_state_is_detected():
    first, second = parse_defects(SAMPLE)
    assert first.closed is True
    assert second.closed is False


def test_issue_payload_has_idempotency_label_and_mapped_priority():
    fields = build_issue(parse_defects(SAMPLE)[0], "QA")["fields"]
    assert fields["project"] == {"key": "QA"}
    assert fields["summary"] == "[DEF-900] API: something `breaks` badly"
    assert "DEF-900" in fields["labels"] and "severity-S2" in fields["labels"]
    assert fields["priority"] == {"name": "Highest"}
    assert fields["description"]["type"] == "doc"


def test_priority_can_be_omitted_for_projects_without_the_field():
    assert "priority" not in build_issue(parse_defects(SAMPLE)[0], "QA", with_priority=False)["fields"]


def test_real_defect_document_parses():
    keys = [d.key for d in parse_defects(DEFECTS_DOC.read_text())]
    assert {"DEF-101", "DEF-104", "DEF-105", "DEF-106"} <= set(keys)
    assert len(keys) == len(set(keys)), "duplicate defect ids in the document"
