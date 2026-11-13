"""Same-day scorecards for India's men's internationals from CricketData.org (free plan).

Cricsheet stays the main source; this only fills the gap until Cricsheet publishes a match.
Needs the CRICKETDATA_API_KEY secret. Without it, this script does nothing.
Free plan: 100 hits/day. A normal day uses about 5 to 10 hits.
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

def series_span(srs):
    import re
    y = re.search(r'(20\d\d)', srs.get('name') or '')
    if not y:
        return None
    y = int(y.group(1))
    try:
        st = datetime.datetime.strptime(f"{srs.get('startDate')} {y}", '%b %d %Y').date()
        en = datetime.datetime.strptime(f"{srs.get('endDate')} {y}", '%b %d %Y').date()
    except Exception:
        return None
    if en < st:
        en = en.replace(year=y + 1)
    return st, en

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
        # 1) live/just-finished matches
        j = call('currentMatches', offset=0)
        for m in (j.get('data') or []) if j.get('status') == 'success' else []:
            if is_target(m) and (m.get('date') or '') >= cutoff:
                found[m['id']] = m
        # 2) India's series whose dates overlap the last 30 days, then every match in them
        today = datetime.date.today()
        cands = {}
        for off in (0, 25, 50):
            j = call('series', offset=off, search=TEAM)
            data = (j.get('data') or []) if j.get('status') == 'success' else []
            if os.environ.get('DEBUG_SERIES'):
                print('raw series sample:', [(x.get('name'), x.get('startDate'), x.get('endDate')) for x in data[:25]], j.get('reason'))
            for srs in data:
                nm = srs.get('name') or ''
                if TEAM not in nm or any(x in nm for x in ('Women', ' A ', 'U19', 'Under', 'Legends', 'Masters')):
                    continue
                span = series_span(srs)
                if span and span[1] >= today - datetime.timedelta(days=DAYS_BACK) and span[0] <= today + datetime.timedelta(days=1):
                    cands[srs['id']] = (span, nm)
            if len(data) < 25:
                break
        print('India series in window:', [v[1] for v in cands.values()])
        for sid, (span, nm) in sorted(cands.items(), key=lambda kv: kv[1][0][1], reverse=True)[:5]:
            j = call('series_info', id=sid, offset=0)
            ml = ((j.get('data') or {}).get('matchList') or []) if j.get('status') == 'success' else []
            for m in ml:
                if is_target(m) and cutoff <= (m.get('date') or '') <= today.isoformat():
                    found[m['id']] = m
    except Exception as e:
        print('list error', e)
    print('India matches in window:', sorted((m.get('date'), m.get('name')) for m in found.values()))
    for mid, m in found.items():
        c = cache.setdefault(mid, {'tries': 0})
        c['match'] = {k: m.get(k) for k in ('id', 'name', 'matchType', 'status', 'venue', 'date', 'dateTimeGMT', 'teams', 'score', 'matchEnded', 'matchStarted')}
    # scorecards for finished matches we don't have yet (or that were still live last time)
    def ended(m):
        st = (m.get('status') or '').lower()
        return bool(m.get('matchEnded')) or any(k in st for k in (' won ', ' won by', 'tied', 'drawn', 'no result', 'abandoned'))
    todo = [mid for mid, c in cache.items()
            if ended(c.get('match', {})) and not c.get('final') and c.get('tries', 0) < 5]
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
