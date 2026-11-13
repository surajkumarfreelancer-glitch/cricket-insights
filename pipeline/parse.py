"""Parse Cricsheet JSON into matches + deliveries parquet files per format (men's and women's kept separate)."""
import json, glob, re, sys, os
import pandas as pd

# key: (folder, gender, label)
FORMATS = {'ipl': ('ipl', 'male', 'IPL'), 't20i': ('t20i', 'male', 'T20I'), 'odi': ('odi', 'male', 'ODI'), 'test': ('test', 'male', 'Test'),
           't20i_w': ('t20i', 'female', 'Women T20I'), 'odi_w': ('odi', 'female', 'Women ODI'), 'test_w': ('test', 'female', 'Women Test')}
STD_OVERS = {'T20': 20, 'ODI': 50}

def base(fmt):
    return 'T20' if ('T20' in fmt or fmt == 'IPL') else ('ODI' if 'ODI' in fmt else 'Test')

ALIAS = {  # fold common spelling variants of the same ground
    'M Chinnaswamy Stadium': 'M Chinnaswamy Stadium',
    'Wankhede Stadium': 'Wankhede Stadium',
    'Eden Gardens': 'Eden Gardens',
    'Feroz Shah Kotla': 'Arun Jaitley Stadium',
    'Arun Jaitley Stadium': 'Arun Jaitley Stadium',
    'Sardar Patel Stadium': 'Narendra Modi Stadium',
    'Narendra Modi Stadium': 'Narendra Modi Stadium',
    'MA Chidambaram Stadium': 'MA Chidambaram Stadium (Chepauk)',
    'MA Chidambaram Stadium Chepauk': 'MA Chidambaram Stadium (Chepauk)',
    'Punjab Cricket Association Stadium': 'PCA Stadium, Mohali',
    'Punjab Cricket Association IS Bindra Stadium': 'PCA Stadium, Mohali',
    'Rajiv Gandhi International Stadium': 'Rajiv Gandhi Intl Stadium, Hyderabad',
    'Rajiv Gandhi International Stadium Uppal': 'Rajiv Gandhi Intl Stadium, Hyderabad',
    'Sawai Mansingh Stadium': 'Sawai Mansingh Stadium',
    'Dubai International Cricket Stadium': 'Dubai International Cricket Stadium',
    'Sheikh Zayed Stadium': 'Sheikh Zayed Stadium, Abu Dhabi',
    'Zayed Cricket Stadium': 'Sheikh Zayed Stadium, Abu Dhabi',
    'Maharashtra Cricket Association Stadium': 'MCA Stadium, Pune',
    'Brabourne Stadium': 'Brabourne Stadium',
    'Dr DY Patil Sports Academy': 'DY Patil Stadium',
    'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium': 'Ekana Stadium, Lucknow',
    'Barsapara Cricket Stadium': 'Barsapara Stadium, Guwahati',
    'Himachal Pradesh Cricket Association Stadium': 'HPCA Stadium, Dharamsala',
    'Holkar Cricket Stadium': 'Holkar Stadium, Indore',
    'Dr YS Rajasekhara Reddy ACA-VDCA Cricket Stadium': 'ACA-VDCA Stadium, Visakhapatnam',
    'Maharaja Yadavindra Singh International Cricket Stadium': 'Mullanpur Stadium (New Chandigarh)',
    'Andhra Cricket Association-Visakhapatnam District Cricket Association Stadium': 'ACA-VDCA Stadium, Visakhapatnam',
    'National Bank Cricket Arena': 'National Stadium, Karachi',
    'National Stadium': 'National Stadium, Karachi',
    'Westpac Stadium': 'Sky Stadium, Wellington',
    'Sky Stadium': 'Sky Stadium, Wellington',
    'Sydney Cricket Ground': 'Sydney Cricket Ground',
    'Melbourne Cricket Ground': 'Melbourne Cricket Ground',
    "Lord's": "Lord's",
    'Kennington Oval': 'The Oval',
    'The Oval': 'The Oval',
}

def clean_venue(v):
    v = v or 'Unknown'
    base = v.split(',')[0]
    base = re.sub(r'\.', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    if base in ALIAS:
        return ALIAS[base]
    for k, val in ALIAS.items():
        if base.startswith(k):
            return val
    return base

def phase(fmt, over):  # over is 1-based
    b = base(fmt)
    if b == 'T20':
        return 'Powerplay (1-6)' if over <= 6 else ('Middle (7-15)' if over <= 15 else 'Death (16-20)')
    if b == 'ODI':
        if over <= 10: return 'Powerplay (1-10)'
        if over <= 25: return 'Middle 1 (11-25)'
        if over <= 40: return 'Middle 2 (26-40)'
        return 'Death (41-50)'
    lo = (over - 1) // 20 * 20 + 1
    return f'Overs {lo}-{lo + 19}'

def run(key):
    folder, gender, fmt = FORMATS[key]
    M, D = [], []
    for f in glob.glob(f'{folder}/*.json'):
        d = json.load(open(f, encoding='utf-8'))
        info = d['info']
        if info.get('gender') != gender:
            continue
        mid = os.path.basename(f)[:-5]
        reg = info['registry']['people']
        out = info.get('outcome', {})
        teams = info.get('teams', [])
        inns = [i for i in d.get('innings', []) if not i.get('super_over')]
        date = info['dates'][0]
        venue = clean_venue(info.get('venue'))
        totals = []
        for n, inn in enumerate(inns, 1):
            bat = inn['team']
            bowl = [t for t in teams if t != bat][0] if len(teams) == 2 else None
            runs = wk = legal = 0
            for o in inn.get('overs', []):
                ov = o['over'] + 1
                lc = 0
                for bi, b in enumerate(o['deliveries']):
                    ex = b.get('extras', {})
                    is_legal = not ('wides' in ex or 'noballs' in ex)
                    legal += is_legal
                    lc += is_legal
                    r = b['runs']
                    runs += r['total']
                    wks = b.get('wickets', [])
                    rec = dict(match_id=mid, fmt=fmt, date=date, season=str(info.get('season')), venue=venue,
                               city=info.get('city'), innings=n, bat_team=bat, bowl_team=bowl, over=ov,
                               phase=phase(fmt, ov), batter=b['batter'], batter_id=reg.get(b['batter']),
                               bowler=b['bowler'], bowler_id=reg.get(b['bowler']), runs_bat=r['batter'],
                               runs_total=r['total'], extras=r['extras'], legal=int(is_legal),
                               wide=int('wides' in ex), noball=int('noballs' in ex),
                               four=int(r['batter'] == 4 and not r.get('non_boundary')),
                               six=int(r['batter'] == 6), dot=int(r['total'] == 0 and is_legal),
                               ballno=f"{ov - 1}.{lc if is_legal else lc + 1}",
                               wicket=0, wkt_kind=None, player_out=None, player_out_id=None, fielder=None)
                    for w in wks:
                        wk += 1
                    if wks:
                        w = wks[0]
                        rec.update(wicket=1, wkt_kind=w['kind'], player_out=w['player_out'],
                                   player_out_id=reg.get(w['player_out']),
                                   fielder=(w.get('fielders') or [{}])[0].get('name'))
                    D.append(rec)
            totals.append((bat, runs, wk, legal, inn.get('declared', False), (inn.get('target') or {}).get('runs'),
                           (inn.get('target') or {}).get('overs'), inn.get('forfeited', False)))
        rec = dict(match_id=mid, fmt=fmt, date=date, season=str(info.get('season')), venue=venue,
                   city=info.get('city'), event=info.get('event', {}).get('name'),
                   team1=teams[0] if teams else None, team2=teams[1] if len(teams) > 1 else None,
                   toss_winner=info.get('toss', {}).get('winner'), toss_decision=info.get('toss', {}).get('decision'),
                   winner=out.get('winner'), result=out.get('result') or ('win' if out.get('winner') else None),
                   method=out.get('method'), win_by_runs=out.get('by', {}).get('runs'),
                   win_by_wkts=out.get('by', {}).get('wickets'),
                   overs_limit=info.get('overs'), pom=', '.join(info.get('player_of_match', [])),
                   stage=info.get('event', {}).get('stage') or (f"Match {info.get('event', {}).get('match_number')}" if info.get('event', {}).get('match_number') else None),
                   n_inns=len(totals), eliminator=out.get('eliminator'), bowl_out=out.get('bowl_out'))
        std = STD_OVERS.get(base(fmt))
        tov = [t[6] for t in totals if t[6]]
        rec['shortened'] = bool(std and ((info.get('overs') or std) < std or any(x < std for x in tov) or out.get('method')))
        # follow-on: same team bats 2nd and 3rd in a Test
        rec['follow_on'] = bool(len(totals) >= 3 and totals[1][0] == totals[2][0])
        for i, (bat, r_, w_, l_, dec, tgt, tov_, ff) in enumerate(totals[:4], 1):
            rec[f'inn{i}_dec'] = dec
            rec[f'inn{i}_target'] = tgt
            rec[f'inn{i}_team'] = bat; rec[f'inn{i}_runs'] = r_; rec[f'inn{i}_wkts'] = w_; rec[f'inn{i}_balls'] = l_
        rec['bat_first'] = totals[0][0] if totals else None
        M.append(rec)
    m = pd.DataFrame(M); dd = pd.DataFrame(D)
    m.to_parquet(f'out_{key}_matches.parquet'); dd.to_parquet(f'out_{key}_deliveries.parquet')
    print(fmt, len(m), 'matches', len(dd), 'balls', m.date.min(), m.date.max())

if __name__ == '__main__':
    for k in (sys.argv[1:] or FORMATS):
        run(k)
