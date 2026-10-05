"""Log the defects in docs/04_defect_management.md to Jira Cloud.

Each "### DEF-nnn (Sx / Py) title" section becomes one Bug. The DEF id is added as a label,
and the script searches for that label first, so running it twice never creates duplicates.
Defects the document marks as closed are moved to Done when the workflow allows it.

    python -m tools.jira_sync --dry-run      # show what would be created, no network
    python -m tools.jira_sync                # create or skip
    python -m tools.jira_sync --only DEF-106

Needs JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY (see .env.example).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFECTS_DOC = Path(__file__).resolve().parent.parent / "docs" / "04_defect_management.md"
HEADING = re.compile(r"^### (DEF-\d+) \((S\d) / (P\d)\) (.+)$")
# Our P1-P3 mapped to Jira's default priority names.
PRIORITY = {"P1": "Highest", "P2": "High", "P3": "Medium"}
CLOSED_WORDS = ("closed", "won't fix")


@dataclass
class Defect:
    key: str
    severity: str
    priority: str
    title: str
    lines: list[str] = field(default_factory=list)

    @property
    def closed(self) -> bool:
        return any(w in " ".join(self.lines).lower() for w in CLOSED_WORDS)

    @property
    def summary(self) -> str:
        return f"[{self.key}] {self.title}"[:255]


def parse_defects(markdown: str) -> list[Defect]:
    defects: list[Defect] = []
    current: Defect | None = None
    for line in markdown.splitlines():
        m = HEADING.match(line)
        if m:
            current = Defect(*m.groups())
            defects.append(current)
        elif line.startswith("#"):
            current = None
        elif current is not None and line.strip():
            current.lines.append(line.strip())
    return defects


def _adf_text(text: str) -> list[dict]:
    """Convert **bold** and `code` spans to Atlassian Document Format text nodes."""
    nodes = []
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            nodes.append({"type": "text", "text": part[2:-2], "marks": [{"type": "strong"}]})
        elif part.startswith("`"):
            nodes.append({"type": "text", "text": part[1:-1], "marks": [{"type": "code"}]})
        else:
            nodes.append({"type": "text", "text": part})
    return nodes


def build_description(defect: Defect) -> dict:
    bullets = [l[2:] for l in defect.lines if l.startswith("- ")]
    paragraphs = [l for l in defect.lines if not l.startswith("- ")]
    content: list[dict] = [
        {"type": "paragraph", "content": _adf_text(f"**Severity:** {defect.severity}   **Priority:** {defect.priority}")}
    ]
    if bullets:
        content.append(
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": _adf_text(b)}]} for b in bullets
                ],
            }
        )
    content += [{"type": "paragraph", "content": _adf_text(p)} for p in paragraphs]
    return {"type": "doc", "version": 1, "content": content}


def build_issue(defect: Defect, project_key: str, issue_type: str = "Bug", with_priority: bool = True) -> dict:
    fields = {
        "project": {"key": project_key},
        "issuetype": {"name": issue_type},
        "summary": defect.summary,
        "description": build_description(defect),
        "labels": ["qa-portfolio", defect.key, f"severity-{defect.severity}"],
    }
    if with_priority:
        fields["priority"] = {"name": PRIORITY.get(defect.priority, "Medium")}
    return {"fields": fields}


class Jira:
    def __init__(self, base_url: str, email: str, token: str):
        import requests

        self.base = base_url.rstrip("/")
        self.http = requests.Session()
        self.http.auth = (email, token)
        self.http.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _call(self, method: str, path: str, **kwargs):
        resp = self.http.request(method, f"{self.base}{path}", timeout=30, **kwargs)
        if resp.status_code == 401:
            raise SystemExit("Jira rejected the credentials. Check JIRA_EMAIL and JIRA_API_TOKEN.")
        if resp.status_code == 404 and "/rest/api/3/myself" in path:
            raise SystemExit("JIRA_BASE_URL does not look like a Jira Cloud site.")
        return resp

    def whoami(self) -> str:
        resp = self._call("GET", "/rest/api/3/myself")
        resp.raise_for_status()
        return resp.json().get("displayName", "?")

    def find_by_label(self, project_key: str, label: str) -> str | None:
        jql = f'project = "{project_key}" AND labels = "{label}"'
        resp = self._call("GET", "/rest/api/3/search/jql", params={"jql": jql, "maxResults": 1, "fields": "key"})
        if resp.status_code == 400:
            raise SystemExit(f"Jira could not search project {project_key}. Check JIRA_PROJECT_KEY. {resp.text[:200]}")
        resp.raise_for_status()
        issues = resp.json().get("issues", [])
        return issues[0]["key"] if issues else None

    def create(self, defect: Defect, project_key: str) -> str:
        """Try Bug with priority first, then degrade: some projects lack one or the other."""
        attempts = [("Bug", True), ("Bug", False), ("Task", True), ("Task", False)]
        last = None
        for issue_type, with_priority in attempts:
            resp = self._call("POST", "/rest/api/3/issue", json=build_issue(defect, project_key, issue_type, with_priority))
            if resp.status_code == 201:
                return resp.json()["key"]
            last = resp
            if resp.status_code != 400:
                break
        raise SystemExit(f"Could not create {defect.key}: HTTP {last.status_code} {last.text[:300]}")

    def close(self, issue_key: str) -> bool:
        resp = self._call("GET", f"/rest/api/3/issue/{issue_key}/transitions")
        if resp.status_code != 200:
            return False
        done = [t for t in resp.json().get("transitions", []) if t.get("to", {}).get("statusCategory", {}).get("key") == "done"]
        if not done:
            return False
        resp = self._call("POST", f"/rest/api/3/issue/{issue_key}/transitions", json={"transition": {"id": done[0]["id"]}})
        return resp.status_code == 204


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print what would be created; no network calls")
    parser.add_argument("--only", metavar="DEF-nnn", help="sync a single defect")
    parser.add_argument("--doc", type=Path, default=DEFECTS_DOC)
    args = parser.parse_args(argv)

    defects = parse_defects(args.doc.read_text())
    if args.only:
        defects = [d for d in defects if d.key == args.only]
    if not defects:
        raise SystemExit("No matching defects found in the document.")

    if args.dry_run:
        for d in defects:
            state = "Done" if d.closed else "Open"
            print(f"would create  {d.summary}\n              priority={PRIORITY.get(d.priority)}  status={state}  labels=qa-portfolio,{d.key},severity-{d.severity}")
        print(f"\n{len(defects)} defects parsed. Nothing was sent.")
        return 0

    missing = [v for v in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY") if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}. Set them in .env and load it with: set -a; source .env; set +a")

    project = os.environ["JIRA_PROJECT_KEY"]
    jira = Jira(os.environ["JIRA_BASE_URL"], os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
    print(f"Connected to {jira.base} as {jira.whoami()}, project {project}\n")

    created = skipped = 0
    for d in defects:
        existing = jira.find_by_label(project, d.key)
        if existing:
            print(f"exists   {existing}  {d.summary}")
            skipped += 1
            continue
        key = jira.create(d, project)
        note = " (moved to Done)" if d.closed and jira.close(key) else ""
        print(f"created  {key}  {d.summary}{note}\n         {jira.base}/browse/{key}")
        created += 1
    print(f"\n{created} created, {skipped} already existed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
