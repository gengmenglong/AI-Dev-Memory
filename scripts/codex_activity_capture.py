#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_CODEX_DIR = Path.home() / ".codex"
DEFAULT_MEMORY_REPO = Path("/root/menglong/github/docs_all_process")
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass
class SessionActivity:
    session_id: str
    started_at: datetime | None = None
    cwd: str = ""
    model: str = ""
    user_messages: list[tuple[datetime, str]] = field(default_factory=list)
    final_answers: list[tuple[datetime, str]] = field(default_factory=list)


def parse_timestamp(value: str | None, timezone: ZoneInfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone)


def text_from_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("input_text") or item.get("output_text")
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def parse_session_file(path: Path, timezone: ZoneInfo) -> SessionActivity | None:
    activity: SessionActivity | None = None
    fallback_session_id = path.stem.removeprefix("rollout-")

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_time = parse_timestamp(event.get("timestamp"), timezone)
            payload = event.get("payload") or {}
            event_type = event.get("type")

            if event_type == "session_meta":
                session_id = payload.get("session_id") or payload.get("id") or fallback_session_id
                activity = activity or SessionActivity(session_id=session_id)
                activity.started_at = parse_timestamp(payload.get("timestamp"), timezone) or event_time
                activity.cwd = payload.get("cwd") or activity.cwd
                activity.model = payload.get("model") or activity.model
                continue

            if activity is None:
                activity = SessionActivity(session_id=fallback_session_id)

            if event_type == "response_item":
                role = payload.get("role")
                content = payload.get("content")
                phase = payload.get("phase")
                text = text_from_content(content)
                if not text or event_time is None:
                    continue
                if role == "assistant" and phase == "final_answer":
                    activity.final_answers.append((event_time, text))

            elif event_type == "event_msg":
                event_payload_type = payload.get("type")
                text = payload.get("message")
                if event_payload_type == "user_message" and text and event_time:
                    activity.user_messages.append((event_time, str(text).strip()))

    if activity is None:
        return None
    if not activity.user_messages and not activity.final_answers:
        return None
    return activity


def project_slug(cwd: str) -> str:
    if not cwd:
        return "unknown"
    return Path(cwd).name or "unknown"


def markdown_for_day(day: str, activities: list[SessionActivity]) -> str:
    lines = [
        "---",
        f'title: "{day} Codex Inbox"',
        f'date: "{day}"',
        'scope: "codex-inbox"',
        'tags: ["worklog", "codex", "inbox"]',
        "---",
        "",
        f"# {day} Codex Inbox",
        "",
        "This file is generated from local Codex session logs. Treat it as raw capture for later daily reports, weekly reports, and project memory updates.",
        "",
    ]

    for activity in sorted(activities, key=lambda item: item.started_at or datetime.min.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))):
        started = activity.started_at.isoformat(timespec="seconds") if activity.started_at else "unknown"
        slug = project_slug(activity.cwd)
        lines.extend(
            [
                f"## {started} - {slug}",
                "",
                f"- Session: `{activity.session_id}`",
                f"- Project: `{slug}`",
                f"- CWD: `{activity.cwd or 'unknown'}`",
                f"- Model: `{activity.model or 'unknown'}`",
                "",
            ]
        )

        if activity.user_messages:
            lines.extend(["### User Requests", ""])
            for timestamp, text in activity.user_messages:
                safe_text = text.replace("\n", "\n  ")
                lines.append(f"- `{timestamp.strftime('%H:%M:%S')}` {safe_text}")
            lines.append("")

        if activity.final_answers:
            lines.extend(["### Final Answers", ""])
            for timestamp, text in activity.final_answers:
                safe_text = text.replace("\n", "\n  ")
                lines.append(f"- `{timestamp.strftime('%H:%M:%S')}` {safe_text}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def collect_activities(codex_dir: Path, timezone: ZoneInfo, since_days: int) -> dict[str, list[SessionActivity]]:
    sessions_dir = codex_dir / "sessions"
    cutoff = datetime.now(timezone) - timedelta(days=since_days)
    by_day: dict[str, list[SessionActivity]] = defaultdict(list)

    for path in sorted(sessions_dir.glob("**/*.jsonl")):
        activity = parse_session_file(path, timezone)
        if activity is None:
            continue
        anchor = activity.started_at
        if anchor is None and activity.user_messages:
            anchor = activity.user_messages[0][0]
        if anchor is None or anchor < cutoff:
            continue
        by_day[anchor.date().isoformat()].append(activity)

    return by_day


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Codex session activity into AI-Dev-Memory inbox markdown files.")
    parser.add_argument("--codex-dir", type=Path, default=DEFAULT_CODEX_DIR)
    parser.add_argument("--memory-repo", type=Path, default=DEFAULT_MEMORY_REPO)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--since-days", type=int, default=2)
    args = parser.parse_args()

    timezone = ZoneInfo(args.timezone)
    output_dir = args.memory_repo / "worklog" / "inbox" / "codex"
    output_dir.mkdir(parents=True, exist_ok=True)

    by_day = collect_activities(args.codex_dir, timezone, args.since_days)
    for day, activities in by_day.items():
        output_path = output_dir / f"{day}.md"
        output_path.write_text(markdown_for_day(day, activities), encoding="utf-8")

    print(f"Captured {sum(len(items) for items in by_day.values())} sessions into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
