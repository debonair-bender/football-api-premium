"""Build versioned client-ready competition snapshots from local source data."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from epg.sync_epg import key, team_names, write_json

ROOT = Path(__file__).resolve().parent
ZONE = ZoneInfo('Europe/Rome')
SLUGS = ('serie-a', 'serie-b', 'champions-league')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def teams_equal(a, b, aliases):
    return bool(team_names(a, aliases) & team_names(b, aliases))


def timestamp(row):
    value = row.get('timestamp')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return datetime.fromtimestamp(value, timezone.utc)
    return None


def build(slug, season, calendar, live_docs, epg_matches, channels, aliases, source_status, now):
    live_by_id = defaultdict(list)
    for doc in live_docs:
        for item in doc.get('matches', []):
            live_by_id[str(item['id'])].append((item, doc))
    candidates = []
    for values in live_by_id.values():
        candidates.append(max(values, key=lambda x: x[1].get('updatedAt', '')))
    claimed = defaultdict(list)
    for row in calendar['matches']:
        start = timestamp(row)
        possible = []
        for live, doc in candidates:
            try:
                day = datetime.fromisoformat(live['date'].replace('Z', '+00:00')).astimezone(ZONE).date()
            except (KeyError, ValueError):
                continue
            if start and start.astimezone(ZONE).date() == day and teams_equal(row['homeTeam'], live.get('homeTeam') or '', aliases) and teams_equal(row['awayTeam'], live.get('awayTeam') or '', aliases):
                possible.append((live, doc))
        if len(possible) == 1:
            claimed[possible[0][0]['id']].append(row['id'])
    epg_index = {m['calendarId']: m for m in epg_matches.get('matches', []) if m.get('competition') == slug}
    channel_map = {c['id']: c for c in channels.get('channels', [])}
    results = []
    for row in calendar['matches']:
        start = timestamp(row)
        live = None
        for candidate, doc in candidates:
            if claimed.get(candidate['id']) == [row['id']]:
                live = (candidate, doc)
                break
        broadcasts = []
        epg = epg_index.get(str(row['id']), {})
        if not start or epg.get('kickoffUtc') != start.isoformat().replace('+00:00', 'Z') or epg.get('homeTeam') != row['homeTeam'] or epg.get('awayTeam') != row['awayTeam']:
            epg = {}
        for broadcast in epg.get('broadcasts', []):
            channel = channel_map.get(broadcast['channelId'])
            if channel:
                broadcasts.append({**broadcast, 'channelName': (channel.get('names') or [channel['id']])[0], 'channelAliases': channel.get('aliases', [])})
        result = {'id': f"{slug}:{season}:{row['id']}", 'competition': slug,
                  'homeTeam': row['homeTeam'], 'awayTeam': row['awayTeam'],
                  'kickoffUtc': start.isoformat().replace('+00:00', 'Z') if start else None,
                  'round': row.get('round'), 'venue': row.get('stadium'),
                  'status': {'PLAYED': 'FINISHED', 'GIOCATA': 'FINISHED', 'NS': 'SCHEDULED'}.get(row.get('status'), row.get('status') or 'UNKNOWN'), 'homeScore': row.get('homeScore'), 'awayScore': row.get('awayScore'),
                  'minute': None, 'broadcasts': broadcasts}
        if live and not (result['status'] == 'FINISHED' and live[0].get('status') == 'SCHEDULED'):
            result.update(status=live[0].get('status'), homeScore=live[0].get('homeScore'), awayScore=live[0].get('awayScore'), minute=live[0].get('elapsed'), liveUpdatedAt=live[1].get('updatedAt'))
        results.append(result)
    return {'schemaVersion': 1, 'competition': slug, 'season': season, 'generatedAt': now.isoformat().replace('+00:00', 'Z'),
            'sources': {'calendarUpdatedAt': calendar.get('updatedAt'), 'liveUpdatedAt': [d.get('updatedAt') for d in live_docs],
                        'epgUpdatedAt': epg_matches.get('updatedAt'), 'epgState': source_status.get('state'), 'epgCalendarState': source_status.get('calendarState')},
            'matches': results}


def main():
    now = datetime.now(timezone.utc)
    local = now.astimezone(ZONE)
    year = local.year if local.month >= 7 else local.year - 1
    season = f'{year}-{year+1}'
    aliases = load(ROOT / 'epg/aliases/teams.json')
    matches = load(ROOT / 'storage/epg/data/matches.json')
    channels = load(ROOT / 'storage/epg/data/channels.json')
    status = load(ROOT / 'storage/epg/data/status.json')
    snapshots = []
    for slug in SLUGS:
        folder = ROOT / 'storage' / 'calendars' / slug
        calendar = load(folder / f'{season}.json')
        if calendar.get('season') != season.replace('-', '/') or not isinstance(calendar.get('matches'), list) or not calendar['matches']:
            raise ValueError(f'Invalid calendar: {slug} {season}')
        live_docs = [load(p) for p in (folder / 'live-current.json', folder / 'live-yesterday.json') if p.exists()]
        snapshots.append((slug, build(slug, season, calendar, live_docs, matches, channels, aliases, status, now)))
    for slug, snapshot in snapshots:
        write_json(ROOT / 'public/v1' / f'{slug}.json', snapshot)


if __name__ == '__main__':
    main()
