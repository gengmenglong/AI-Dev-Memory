#!/usr/bin/env python3
import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_MEMORY_REPO = Path("/root/menglong/github/docs_all_process")
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass
class InboxSession:
    heading: str
    project: str = "unknown"
    session_id: str = ""
    cwd: str = ""
    requests: list[str] = field(default_factory=list)
    final_answers: list[str] = field(default_factory=list)


def parse_frontmatter_date(text: str) -> str | None:
    match = re.search(r'^date:\s+"?([^"\n]+)"?', text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def clean_list_item(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^- `\d{2}:\d{2}:\d{2}`\s*", "", line)
    line = re.sub(r"^- ", "", line)
    return line.strip()


def parse_inbox(path: Path) -> tuple[str, list[InboxSession]]:
    text = path.read_text(encoding="utf-8")
    report_date = parse_frontmatter_date(text) or path.stem
    sessions: list[InboxSession] = []
    current: InboxSession | None = None
    section: str | None = None
    current_item: list[str] = []

    def flush_item() -> None:
        nonlocal current_item
        if current is None or section is None or not current_item:
            current_item = []
            return
        value = "\n".join(current_item).strip()
        if section == "requests":
            current.requests.append(value)
        elif section == "final_answers":
            current.final_answers.append(value)
        current_item = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            flush_item()
            current = InboxSession(heading=line.removeprefix("## ").strip())
            sessions.append(current)
            section = None
            continue

        if current is None:
            continue

        if line.startswith("- Session:"):
            current.session_id = line.split("`", 2)[1] if "`" in line else ""
        elif line.startswith("- Project:"):
            current.project = line.split("`", 2)[1] if "`" in line else "unknown"
        elif line.startswith("- CWD:"):
            current.cwd = line.split("`", 2)[1] if "`" in line else ""
        elif line == "### User Requests":
            flush_item()
            section = "requests"
        elif line == "### Final Answers":
            flush_item()
            section = "final_answers"
        elif line.startswith("- `"):
            flush_item()
            current_item = [clean_list_item(line)]
        elif current_item and (line.startswith("  ") or line == ""):
            current_item.append(line.strip())

    flush_item()
    return report_date, sessions


def first_sentence(text: str, max_len: int = 180) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    value = lines[0]
    return value if len(value) <= max_len else value[: max_len - 1].rstrip() + "..."


def bullet_lines(items: list[str], limit: int = 6) -> list[str]:
    output = []
    for item in items[:limit]:
        sentence = first_sentence(item)
        if sentence:
            output.append(f"- {sentence}")
    if len(items) > limit:
        output.append(f"- ...and {len(items) - limit} more")
    return output


def render_draft(report_date: str, sessions: list[InboxSession]) -> str:
    by_project: dict[str, list[InboxSession]] = defaultdict(list)
    for session in sessions:
        by_project[session.project].append(session)

    total_requests = sum(len(session.requests) for session in sessions)
    total_answers = sum(len(session.final_answers) for session in sessions)
    lines = [
        "---",
        f'title: "{report_date} Daily Report Draft"',
        f'date: "{report_date}"',
        'scope: "daily-draft"',
        'tags: ["worklog", "daily", "draft"]',
        "---",
        "",
        f"# {report_date} Daily Report Draft",
        "",
        "> Auto-generated from `worklog/inbox/codex/`. Review before treating this as the final daily report.",
        "",
        "## Summary",
        "",
        f"- Codex sessions captured: {len(sessions)}",
        f"- Projects touched: {len(by_project)}",
        f"- User requests captured: {total_requests}",
        f"- Final answers captured: {total_answers}",
        "",
        "## Projects",
        "",
    ]

    for project, project_sessions in sorted(by_project.items()):
        lines.extend(
            [
                f"### {project}",
                "",
                f"- Sessions: {len(project_sessions)}",
            ]
        )
        cwds = sorted({session.cwd for session in project_sessions if session.cwd})
        if cwds:
            lines.append(f"- Paths: {', '.join(f'`{cwd}`' for cwd in cwds)}")
        lines.append("")

        requests = [request for session in project_sessions for request in session.requests]
        answers = [answer for session in project_sessions for answer in session.final_answers]
        if requests:
            lines.extend(["#### Requests", ""])
            lines.extend(bullet_lines(requests))
            lines.append("")
        if answers:
            lines.extend(["#### Work Completed / Outcomes", ""])
            lines.extend(bullet_lines(answers))
            lines.append("")

    lines.extend(
        [
            "## Decisions",
            "",
            "- pending review",
            "",
            "## Blockers / Risks",
            "",
            "- pending review",
            "",
            "## Project Memory Candidates",
            "",
            "- Review project sections above and promote stable information into `worklog/projects/<project-slug>/`.",
            "",
            "## Follow-ups",
            "",
            "- Review this draft and convert it into a final daily report if needed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a daily report draft from Codex inbox capture.")
    parser.add_argument("--memory-repo", type=Path, default=DEFAULT_MEMORY_REPO)
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    args = parser.parse_args()

    timezone = ZoneInfo(args.timezone)
    report_date = args.date or datetime.now(timezone).date().isoformat()
    inbox_path = args.memory_repo / "worklog" / "inbox" / "codex" / f"{report_date}.md"
    output_dir = args.memory_repo / "worklog" / "daily" / "drafts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_date}.md"

    if not inbox_path.exists():
        output_path.write_text(
            render_draft(report_date, []),
            encoding="utf-8",
        )
        print(f"No inbox found for {report_date}; wrote empty draft to {output_path}")
        return 0

    parsed_date, sessions = parse_inbox(inbox_path)
    output_path.write_text(render_draft(parsed_date, sessions), encoding="utf-8")
    print(f"Wrote daily draft for {parsed_date} with {len(sessions)} sessions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
