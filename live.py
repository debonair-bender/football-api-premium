"""Publish separate today/yesterday ESPN football snapshots, local to Europe/Rome."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scrapers.espn import fetch_scoreboard

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "storage" / "calendars"
CONFIG = ROOT / "config.json"
LIVE_FILES = ("live-current.json", "live-yesterday.json")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_if_changed(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    print(f"Written: {path.relative_to(ROOT)}", flush=True)
    return True


def local_day(match, zone):
    return datetime.fromisoformat(match["date"].replace("Z", "+00:00")).astimezone(zone).date()


def doc(name, espn_id, date_value, matches):
    return {
        "competition": name,
        "espnId": espn_id,
        "date": date_value.isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "total": len(matches),
        "liveCount": sum(bool(m.get("isLive")) for m in matches),
        "matches": sorted(matches, key=lambda m: (m["date"], m["id"])),
    }


def existing_matches(folder):
    """Read both files: yesterday's matches may still be in yesterday's current file."""
    matches = {}
    for filename in LIVE_FILES:
        for match in (read_json(folder / filename) or {}).get("matches", []):
            matches[match["id"]] = match
    return matches


def merge(new_matches, old_matches, allowed_dates, zone):
    """Prefer fresh ESPN; preserve previous scores if a schedule response is less detailed."""
    merged = {mid: m for mid, m in old_matches.items() if local_day(m, zone) in allowed_dates}
    for match in new_matches:
        if local_day(match, zone) not in allowed_dates:
            continue
        previous = merged.get(match["id"])
        if previous and (previous.get("isFinished") or previous.get("status") == "FINISHED") and not (match.get("isFinished") or match.get("status") == "FINISHED"):
            continue
        if previous and (previous.get("isFinished") or previous.get("isLive")) and match.get("status") == "SCHEDULED":
            continue
        merged[match["id"]] = match
    return list(merged.values())


def publish(folder, name, espn_id, matches, zone):
    today = datetime.now(zone).date()
    yesterday = today - timedelta(days=1)
    for filename, day in (("live-current.json", today), ("live-yesterday.json", yesterday)):
        selected = [m for m in matches if local_day(m, zone) == day]
        save_if_changed(folder / filename, doc(name, espn_id, day, selected))


def process(slug, comp, settings):
    folder = DATA / slug
    zone = ZoneInfo(settings.get("timezone", "Europe/Rome"))
    today = datetime.now(zone).date()
    yesterday = today - timedelta(days=1)
    # Discover every day's events even if the previous calendar was outdated.
    fetched = fetch_scoreboard(
        comp["espn_id"],
        [yesterday.strftime("%Y%m%d"), today.strftime("%Y%m%d")],
        settings.get("request_timeout_seconds", 20),
    )
    candidates = merge(fetched, existing_matches(folder), {today, yesterday}, zone)
    publish(folder, comp["name"], comp["espn_id"], candidates, zone)


def main():
    config = read_json(CONFIG)
    errors = []
    for slug, comp in config["competitions"].items():
        if not comp.get("enabled", False):
            continue
        try:
            print(f"{slug}: live", flush=True)
            process(slug, comp, config.get("settings", {}))
        except Exception as exc:
            errors.append(slug)
            print(f"ERROR {slug}: {exc}", file=sys.stderr, flush=True)
    if errors:
        raise SystemExit(f"Failed competitions: {', '.join(errors)}")


if __name__ == "__main__":
    main()
