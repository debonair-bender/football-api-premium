import unittest
from datetime import datetime, timezone
from publish import build

NOW = datetime(2026, 11, 5, 20, tzinfo=timezone.utc)
CAL = {'updatedAt': '2026-11-05T19:00:00Z', 'matches': [{'id': '1', 'timestamp': NOW.timestamp(), 'homeTeam': 'Inter', 'awayTeam': 'Milan', 'status': 'NS'}]}
EPG = {'updatedAt': '2026-11-05T19:00:00Z', 'matches': [{'calendarId': '1', 'competition': 'serie-a', 'homeTeam': 'Inter', 'awayTeam': 'Milan', 'kickoffUtc': '2026-11-05T20:00:00Z', 'broadcasts': [{'channelId': 'sky', 'confidence': 'high'}]}]}
CHANNELS = {'channels': [{'id': 'sky', 'names': ['Sky Sport'], 'aliases': []}]}
ALIASES = {'Inter': ['Internazionale']}

class PublisherTests(unittest.TestCase):
    def generate(self, calendar=CAL, live=None, epg=EPG):
        return build('serie-a', '2026-2027', calendar, live or [], epg, CHANNELS, ALIASES, {'state': 'ok'}, NOW)['matches'][0]

    def test_join_live_and_broadcast(self):
        live = [{'updatedAt': '2026-11-05T20:20:00Z', 'matches': [{'id': '9', 'date': '2026-11-05T20:00:00Z', 'homeTeam': 'Internazionale', 'awayTeam': 'Milan', 'status': 'FIRST_HALF', 'homeScore': 1, 'awayScore': 0, 'elapsed': '20:00'}]}]
        result = self.generate(live=live)
        self.assertEqual((result['status'], result['homeScore']), ('FIRST_HALF', 1))
        self.assertEqual(result['broadcasts'][0]['channelName'], 'Sky Sport')

    def test_changed_kickoff_does_not_reuse_epg(self):
        calendar = {**CAL, 'matches': [{**CAL['matches'][0], 'timestamp': NOW.timestamp() + 3600}]}
        self.assertEqual(self.generate(calendar=calendar)['broadcasts'], [])

    def test_ambiguous_live_does_not_attach(self):
        row = CAL['matches'][0]
        calendar = {**CAL, 'matches': [row, {**row, 'id': '2'}]}
        live = [{'updatedAt': '2026-11-05T20:20:00Z', 'matches': [{'id': '9', 'date': '2026-11-05T20:00:00Z', 'homeTeam': 'Inter', 'awayTeam': 'Milan', 'status': 'FIRST_HALF'}]}]
        self.assertEqual(self.generate(calendar=calendar, live=live)['status'], 'SCHEDULED')

if __name__ == '__main__':
    unittest.main()
