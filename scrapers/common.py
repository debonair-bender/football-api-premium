"""Refresh the weekly calendar from ESPN while retaining the seasonal archive."""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ROME = ZoneInfo("Europe/Rome")
ALIASES = {
    "aekathensfc": "aekathens", "sabahfk": "sabahfa", "vikingfk": "viking",
    "internazionale": "inter", "usavellino": "avellino",
    "vicenza": "vicenzavirtus", "lrvicenza": "vicenzavirtus",
    "bayernmunich": "bayernmunchen", "olympiacos": "olympiakospiraeus",
    "sportinglisbon": "sportingcp", "clubbrugge": "clubbruggekv",
    "slaviaprague": "slaviapraha", "parissaintgermain": "psg",
    "unionstgilloise": "unionsaintgilloise", "lyonnais": "lyon",
    "redstarbelgrade": "fkcrvenazvezda", "fcbarcelona": "barcelona",
}


def team_key(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]", "", plain.lower())
    return ALIASES.get(key, key)


def names(side):
    team = side["team"]
    return {team_key(team[k]) for k in ("displayName", "shortDisplayName", "name") if team.get(k)}


def update_match(rows, event):
    game = event["competitions"][0]
    sides = {side["homeAway"]: side for side in game["competitors"]}
    home, away = sides["home"], sides["away"]
    kickoff = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
    espn_id = str(event["id"])
    existing = next((row for row in rows if row.get("espnId") == espn_id), None)
    if existing is None:
        home_names, away_names = names(home), names(away)
        candidates = [row for row in rows if not row.get("espnId")
                      and team_key(row["homeTeam"]) in home_names
                      and team_key(row["awayTeam"]) in away_names]
        if len(candidates) > 1:
            candidates = [row for row in candidates if row["date"] == kickoff.date().isoformat()]
            if len(candidates) != 1:
                raise ValueError(f"Ambiguous legacy fixture: {event['name']}")
        existing = candidates[0] if candidates else None
    if existing is None:
        existing = {"id": "espn-" + espn_id, "homeTeam": home["team"]["displayName"],
                    "awayTeam": away["team"]["displayName"], "round": None}
        rows.append(existing)
    status = game["status"]["type"]
    mapped = {"STATUS_POSTPONED": "PST", "STATUS_CANCELED": "CANC",
              "STATUS_SUSPENDED": "SUSP", "STATUS_HALFTIME": "HT"}
    state = status["state"]
    venue = game.get("venue") or {}
    def score(side):
        value = side.get("score")
        return int(value) if state != "pre" and value is not None else None
    existing.update(espnId=espn_id, timestamp=int(kickoff.timestamp()),
                    date=kickoff.strftime("%Y-%m-%d"), time=kickoff.strftime("%H:%M"),
                    stadium=venue.get("fullName") or existing.get("stadium"),
                    city=(venue.get("address") or {}).get("city") or existing.get("city"),
                    status=mapped.get(status["name"], {"pre": "SCHEDULED", "in": "LIVE", "post": "FINISHED"}[state]),
                    homeScore=score(home), awayScore=score(away))


def collect(*, slug, competition, league):
    today = datetime.now(ROME).date()
    season = "2026/2027"
    target = ROOT / "storage" / "calendars" / slug / "2026-2027.json"
    previous = json.loads(target.read_text(encoding="utf-8"))
    rows = [dict(row) for row in previous["matches"]]
    count = 0
    for offset in range(-1, 7):
        day = today + timedelta(days=offset)
        url = (f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
               f"?dates={day:%Y%m%d}&limit=200")
        with urlopen(url, timeout=30) as response:
            events = json.load(response)["events"]
        if not isinstance(events, list):
            raise ValueError(f"Invalid ESPN response for {league} on {day}")
        for event in events:
            if event["season"]["year"] == 2026:
                update_match(rows, event)
                count += 1
    rows.sort(key=lambda row: (row["timestamp"] or 0, row["id"]))
    if previous["matches"] != rows:
        payload = dict(competition=competition, season=season, total=len(rows),
                       updatedAt=datetime.now(timezone.utc).isoformat(), matches=rows)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
    print(f"{slug}: checked {count} fixtures, {len(rows)} in season archive")
