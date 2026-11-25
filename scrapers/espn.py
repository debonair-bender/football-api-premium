"""ESPN scoreboard JSON adapter (unofficial endpoint; subject to change)."""

import json
from urllib.request import Request, urlopen

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def game_status(status):
    info = status.get("type") or {}
    name = info.get("name", "")
    state = info.get("state", "")
    special = {
        "STATUS_HALFTIME": "HALF_TIME",
        "STATUS_POSTPONED": "POSTPONED",
        "STATUS_CANCELED": "CANCELLED",
        "STATUS_CANCELLED": "CANCELLED",
        "STATUS_SUSPENDED": "SUSPENDED",
        "STATUS_FULL_TIME": "FINISHED",
        "STATUS_FINAL": "FINISHED",
    }
    if name in special:
        return special[name]
    if state == "pre":
        return "SCHEDULED"
    if state == "post":
        return "FINISHED"
    if state == "in":
        return {1: "FIRST_HALF", 2: "SECOND_HALF", 3: "EXTRA_TIME", 4: "EXTRA_TIME", 5: "PENALTIES"}.get(status.get("period"), "LIVE")
    return name or "UNKNOWN"


def score(value):
    if isinstance(value, dict):
        value = value.get("value", value.get("displayValue"))
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def parse_event(event):
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    game = competitions[0]
    competitors = game.get("competitors") or []
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not home or not away or not event.get("id") or not event.get("date"):
        return None
    raw_status = event.get("status") or game.get("status") or {}
    info = raw_status.get("type") or {}
    state = info.get("state")
    venue = game.get("venue") or {}
    return {
        "id": str(event["id"]),
        "date": event["date"],
        "homeTeam": (home.get("team") or {}).get("displayName"),
        "awayTeam": (away.get("team") or {}).get("displayName"),
        "homeScore": score(home.get("score")),
        "awayScore": score(away.get("score")),
        "status": game_status(raw_status),
        "espnStatus": info.get("name"),
        "statusDetail": info.get("detail"),
        "state": state,
        "elapsed": raw_status.get("displayClock"),
        "period": raw_status.get("period"),
        "isLive": state == "in",
        "isFinished": state == "post",
        "venue": venue.get("fullName") if isinstance(venue, dict) else None,
    }


def fetch_events(espn_id, day, timeout=20):
    request = Request(
        f"{BASE}/{espn_id}/scoreboard?dates={day}&limit=200",
        headers={"Accept": "application/json", "User-Agent": "FootballApiSync/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError(f"{espn_id} / {day}: unexpected ESPN response")
    return payload["events"]


def fetch_scoreboard(espn_id, dates, timeout=20):
    matches = {}
    for day in sorted(set(dates)):
        events = fetch_events(espn_id, day, timeout)
        for event in events:
            parsed = parse_event(event)
            if parsed is None:
                raise ValueError(f"{espn_id} / {day}: incomplete event")
            matches[parsed["id"]] = parsed
        print(f"{espn_id} / {day}: {len(events)} events", flush=True)
    return sorted(matches.values(), key=lambda x: (x["date"], x["id"]))
