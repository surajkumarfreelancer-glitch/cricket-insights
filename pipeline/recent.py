"""Same-day scorecards for India's men's internationals from CricketData.org (free plan).

Cricsheet stays the main source; this only fills the gap until Cricsheet publishes a match.
Needs the CRICKETDATA_API_KEY secret. Without it, this script does nothing.
Free plan: 100 hits/day. A normal day uses about 3 to 6 hits.
"""
import os, json, datetime, urllib.request, urllib.parse

KEY = os.environ.get('CRICKETDATA_API_KEY', '').strip()
CACHE = 'recent_cache.json'
TEAM = 'India'
TYPES = {'odi': 'ODI', 't20': 'T20I', 'test': 'Test'}
MAX_SCORECARDS_PER_RUN = 4
DAYS_BACK = 30

def call(endpoint, **params):
    q = urllib.parse.urlencode(dict(apikey=KEY, **params))
    req = urllib.request.Request(f'https://api.cricapi.com/v1/{endpoint}?{q}', headers={'User-Agent': 'CricketInsights/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read())
    info = j.get('info', {})
    print(f"{endpoint}: {j.get('status')} hits {info.get('hitsToday')}/{info.get('hitsLimit')}")
    return j

def is_target(m):
    teams = m.get('teams') or []
    return TEAM in teams and m.get('matchType') in TYPES and len(teams) == 2

def main():
    if not KEY:
        print('No CRICKETDATA_API_KEY set, skipping same-day scorecards')
        return
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
    cutoff = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK)).isoformat()
    found = {}
    try:
        for ep, offs in (('currentMatches', [0]), ('matches', [0, 25])):
            for off in offs:
                j = call(ep, offset=off)
                if j.get('status') != 'success':
                    print('list call failed:', j.get('reason') or j.get('status'))
                    continue
                for m in j.get('data') or []:
                    if is_target(m) and (m.get('date') or '') >= cutoff:
                        found[m['id']] = m
    except Exception as e:
        print('list error', e)
    for mid, m in found.items():
        c = cache.setdefault(mid, {'tries': 0})
        c['match'] = {k: m.get(k) for k in ('id', 'name', 'matchType', 'status', 'venue', 'date', 'dateTimeGMT', 'teams', 'score', 'matchEnded', 'matchStarted')}
    # scorecards for finished matches we don't have yet (or that were still live last time)
    todo = [mid for mid, c in cache.items()
            if c.get('match', {}).get('matchEnded') and not c.get('final') and c.get('tries', 0) < 5]
    todo.sort(key=lambda mid: cache[mid]['match'].get('date') or '', reverse=True)
    for mid in todo[:MAX_SCORECARDS_PER_RUN]:
        c = cache[mid]
        c['tries'] = c.get('tries', 0) + 1
        try:
            j = call('match_scorecard', id=mid, offset=0)
        except Exception as e:
            print('scorecard error', mid, e); continue
        d = j.get('data') if j.get('status') == 'success' else None
        if isinstance(d, dict) and d.get('scorecard'):
            c['scorecard'] = d.get('scorecard')
            c['toss'] = [d.get('tossWinner'), d.get('tossChoice')]
            c['winner'] = d.get('matchWinner')
            c['final'] = True
        else:
            print('no scorecard for', mid, j.get('reason') or j.get('status'))
    # forget matches older than 60 days (Cricsheet will have them by then)
    old = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    cache = {k: v for k, v in cache.items() if (v.get('match', {}).get('date') or '9') >= old}
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), indent=1)
    print('cached India matches:', len(cache), 'with scorecard:', sum(1 for v in cache.values() if v.get('scorecard')))

if __name__ == '__main__':
    main()
