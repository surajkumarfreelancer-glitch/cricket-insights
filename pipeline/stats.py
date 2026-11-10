"""Build venue / phase / bowler-type / batter / bowler insight tables for one format."""
import sys, json
import pandas as pd, numpy as np

KEY = {'ipl': 'IPL', 't20i': 'T20I', 'odi': 'ODI', 'test': 'Test'}
BOWLER_WKTS = {'bowled', 'caught', 'lbw', 'stumped', 'caught and bowled', 'hit wicket'}
MIN_MATCHES = {'IPL': 5, 'T20I': 5, 'ODI': 5, 'Test': 3}
MIN_BALLS_BAT = {'IPL': 100, 'T20I': 100, 'ODI': 300, 'Test': 600}
MIN_BALLS_BOWL = {'IPL': 180, 'T20I': 180, 'ODI': 300, 'Test': 600}
MIN_VS_TYPE = {'IPL': 48, 'T20I': 48, 'ODI': 90, 'Test': 180}

def r1(x):
    return None if x is None or pd.isna(x) or np.isinf(x) else round(float(x), 1)

def load(key):
    m = pd.read_parquet(f'out_{key}_matches.parquet')
    d = pd.read_parquet(f'out_{key}_deliveries.parquet')
    st = pd.read_csv('player_styles.csv')
    bt = st.set_index('player_id')
    d['bowl_group'] = d.bowler_id.map(bt.bowl_group).fillna('Unknown')
    d['bowl_type'] = d.bowler_id.map(bt.bowl_type).fillna('Unknown')
    d['bat_hand'] = d.batter_id.map(bt.bat_hand).fillna('Unknown')
    d['bowler_wkt'] = d.wkt_kind.isin(BOWLER_WKTS).astype(int)
    # balls faced by batter excludes wides; runs conceded by bowler excludes byes/legbyes
    d['bf'] = 1 - d.wide
    d['conceded'] = d.runs_bat + d.wide * 0  # wides/no-balls added below
    d['conceded'] = d.runs_total  # approximation then remove byes/legbyes
    d['date'] = pd.to_datetime(d.date)
    m['date'] = pd.to_datetime(m.date)
    m['year'] = m.date.dt.year
    return m, d

def periods(m):
    last = m.date.max()
    return {'All years': m.date.min(), 'Last 10 years': last - pd.DateOffset(years=10),
            'Last 5 years': last - pd.DateOffset(years=5)}

def venue_summary(m, d, fmt):
    rows = []
    lim = fmt != 'Test'
    wk_all = d[d.bowler_wkt == 1]
    SPIN_BASE[fmt] = (wk_all.bowl_group == 'Spin').sum() / max((wk_all.bowl_group != 'Unknown').sum(), 1) * 100
    for pname, start in periods(m).items():
        mm = m[m.date >= start]
        for v, g in mm.groupby('venue'):
            if len(g) < MIN_MATCHES[fmt]:
                continue
            res = g[g.winner.notna()]
            r = dict(Period=pname, Venue=v, City=g.city.mode().iat[0] if g.city.notna().any() else None,
                     Matches=len(g), First=g.date.min().date(), Last=g.date.max().date())
            if lim:
                clean = g[g.method.isna() & g.winner.notna()]
                full1 = clean  # 1st innings full value
                r['Avg 1st inns'] = r1(full1.inn1_runs.mean())
                r['Avg 2nd inns'] = r1(clean.inn2_runs.mean())
                r['Median 1st inns'] = r1(full1.inn1_runs.median())
                r['Highest'] = int(g[['inn1_runs', 'inn2_runs']].max().max())
                r['Lowest completed 1st inns'] = int(full1.inn1_runs.min()) if len(full1) else None
                bf_win = (res.winner == res.bat_first).mean() * 100 if len(res) else None
                r['Bat 1st win %'] = r1(bf_win)
                r['Chase win %'] = r1(100 - bf_win) if bf_win is not None else None
                r['Avg wkts 1st inns'] = r1(full1.inn1_wkts.mean())
                r['Avg wkts 2nd inns'] = r1(clean.inn2_wkts.mean())
                chase = clean[clean.winner != clean.bat_first]
                r['Highest chase'] = int(chase.inn2_runs.max()) if len(chase) else None
                r['Lowest total defended'] = int(clean[clean.winner == clean.bat_first].inn1_runs.min()) if (clean.winner == clean.bat_first).any() else None
            else:
                for i in range(1, 5):
                    r[f'Avg {i} inns'] = r1(g[f'inn{i}_runs'].mean())
                r['Bat 1st win %'] = r1((g.winner == g.bat_first).mean() * 100)
                r['Bat 2nd win %'] = r1(((g.winner.notna()) & (g.winner != g.bat_first)).mean() * 100)
                r['Draw %'] = r1((g.result == 'draw').mean() * 100)
            tw = g[g.toss_winner.notna() & g.winner.notna()]
            r['Toss winner wins %'] = r1((tw.toss_winner == tw.winner).mean() * 100) if len(tw) else None
            r['Toss: chose to bat %'] = r1((g.toss_decision == 'bat').mean() * 100)
            dv = d[(d.venue == v) & (d.date >= start)]
            wk = dv[dv.bowler_wkt == 1]
            tot = (wk.bowl_group != 'Unknown').sum()
            r['Pace wkt %'] = r1((wk.bowl_group == 'Pace').sum() / tot * 100) if tot else None
            r['Spin wkt %'] = r1((wk.bowl_group == 'Spin').sum() / tot * 100) if tot else None
            for grp in ['Pace', 'Spin']:
                x = dv[dv.bowl_group == grp]
                balls = (x.legal).sum()
                r[f'{grp} econ'] = r1(x.runs_total.sum() / balls * 6) if balls else None
                w = x.bowler_wkt.sum()
                r[f'{grp} avg'] = r1(x.runs_total.sum() / w) if w else None
            ty = dv[dv.bowl_type != 'Unknown'].groupby('bowl_type').agg(b=('legal', 'sum'), w=('bowler_wkt', 'sum'))
            ty = ty[(ty.b >= 0.06 * ty.b.sum()) & (ty.w >= 5)]
            if len(ty):
                ty['sr'] = ty.b / ty.w
                bt = ty.sort_values('sr').iloc[0]
                r['Best bowler type'] = f"{ty.sort_values('sr').index[0]} (wkt every {bt.sr:.0f} balls)"
            else:
                r['Best bowler type'] = None
            r['Pitch read'] = pitch_read(r, fmt)
            rows.append(r)
    return pd.DataFrame(rows).sort_values(['Period', 'Matches'], ascending=[True, False])

SPIN_BASE = {}
def pitch_read(r, fmt):
    tags = []
    s = r.get('Spin wkt %')
    base = SPIN_BASE.get(fmt, 33)
    if s is None: tags.append('Bowler styles unknown')
    elif s >= base + 8: tags.append('Spin friendly')
    elif s <= base - 8: tags.append('Pace friendly')
    else: tags.append('Balanced pace/spin')
    a = r.get('Avg 1st inns') if fmt != 'Test' else r.get('Avg 1 inns')
    hi = {'IPL': 180, 'T20I': 165, 'ODI': 280, 'Test': 380}[fmt]
    lo = {'IPL': 155, 'T20I': 130, 'ODI': 230, 'Test': 300}[fmt]
    if a:
        tags.append('High scoring' if a >= hi else ('Low scoring' if a <= lo else 'Par scoring'))
    c = r.get('Chase win %')
    if c is not None:
        tags.append('Chasing ground' if c >= 57 else ('Defending ground' if c <= 43 else 'No toss edge'))
    return ', '.join(tags)

def venue_phase(m, d, fmt):
    rows = []
    for pname, start in periods(m).items():
        x = d[d.date >= start]
        keep = x.groupby('venue').match_id.nunique()
        x = x[x.venue.isin(keep[keep >= MIN_MATCHES[fmt]].index)]
        inn = x.innings.clip(upper=4 if fmt == 'Test' else 2)
        g = x.assign(inn=inn).groupby(['venue', 'inn', 'phase'])
        a = g.agg(matches=('match_id', 'nunique'), runs=('runs_total', 'sum'), balls=('legal', 'sum'),
                  wkts=('wicket', 'sum'), fours=('four', 'sum'), sixes=('six', 'sum'), dots=('dot', 'sum')).reset_index()
        sp = x[x.bowler_wkt == 1].assign(inn=inn).groupby(['venue', 'inn', 'phase', 'bowl_group']).size().unstack(fill_value=0)
        a = a.merge(sp.reset_index(), on=['venue', 'inn', 'phase'], how='left').fillna(0)
        a['Period'] = pname
        rows.append(a)
    a = pd.concat(rows)
    out = pd.DataFrame({
        'Period': a.Period, 'Venue': a.venue, 'Innings': a.inn, 'Phase': a.phase,
        'Innings sampled': a.matches,
        'Avg runs in phase': (a.runs / a.matches).round(1),
        'Run rate': (a.runs / a.balls * 6).round(2),
        'Avg wkts in phase': (a.wkts / a.matches).round(2),
        'Dot %': (a.dots / a.balls * 100).round(1),
        'Boundary %': ((a.fours + a.sixes) / a.balls * 100).round(1),
        'Sixes per inns': (a.sixes / a.matches).round(2),
        'Pace wkts': a.get('Pace', 0).astype(int), 'Spin wkts': a.get('Spin', 0).astype(int)})
    return out.sort_values(['Period', 'Venue', 'Innings', 'Phase'])

def venue_bowler_type(m, d, fmt):
    rows = []
    for pname, start in periods(m).items():
        x = d[(d.date >= start) & (d.bowl_type != 'Unknown')]
        keep = x.groupby('venue').match_id.nunique()
        x = x[x.venue.isin(keep[keep >= MIN_MATCHES[fmt]].index)]
        g = x.groupby(['venue', 'bowl_group', 'bowl_type']).agg(balls=('legal', 'sum'), runs=('runs_total', 'sum'),
                                                               wkts=('bowler_wkt', 'sum'), dots=('dot', 'sum'),
                                                               bowled=('wkt_kind', lambda s: (s == 'bowled').sum()),
                                                               lbw=('wkt_kind', lambda s: (s == 'lbw').sum()),
                                                               caught=('wkt_kind', lambda s: s.isin(['caught', 'caught and bowled']).sum()),
                                                               stumped=('wkt_kind', lambda s: (s == 'stumped').sum())).reset_index()
        tot = g.groupby('venue').wkts.transform('sum')
        g['Period'] = pname
        g['Share of wkts %'] = (g.wkts / tot * 100).round(1)
        rows.append(g)
    g = pd.concat(rows)
    g['Overs'] = (g.balls / 6).round(1)
    g['Economy'] = (g.runs / g.balls * 6).round(2)
    g['Average'] = (g.runs / g.wkts.replace(0, np.nan)).round(1)
    g['Strike rate'] = (g.balls / g.wkts.replace(0, np.nan)).round(1)
    g['Dot %'] = (g.dots / g.balls * 100).round(1)
    g = g.rename(columns={'venue': 'Venue', 'bowl_group': 'Pace/Spin', 'bowl_type': 'Bowler type', 'wkts': 'Wickets',
                          'bowled': 'Bowled', 'lbw': 'LBW', 'caught': 'Caught', 'stumped': 'Stumped'})
    return g[['Period', 'Venue', 'Pace/Spin', 'Bowler type', 'Overs', 'Wickets', 'Share of wkts %', 'Economy',
              'Average', 'Strike rate', 'Dot %', 'Bowled', 'LBW', 'Caught', 'Stumped']].sort_values(['Period', 'Venue', 'Wickets'], ascending=[True, True, False])

def batter_profiles(m, d, fmt):
    last = m.date.max()
    x = d[d.date >= last - pd.DateOffset(years=10)]  # recent careers matter most
    b = x.groupby(['batter_id']).agg(Batter=('batter', 'last'), Hand=('bat_hand', 'last'), Team=('bat_team', 'last'),
                                      Inns=('match_id', 'nunique'), Runs=('runs_bat', 'sum'), Balls=('bf', 'sum'),
                                      Fours=('four', 'sum'), Sixes=('six', 'sum'), Dots=('dot', 'sum'),
                                      Last=('date', 'max'))
    outs = x[x.player_out_id.notna()].groupby('player_out_id')
    b['Outs'] = outs.size()
    b = b[b.Balls >= MIN_BALLS_BAT[fmt]].copy()
    b['Outs'] = b.Outs.fillna(0).astype(int)
    b['Average'] = (b.Runs / b.Outs.replace(0, np.nan)).round(1)
    b['Strike rate'] = (b.Runs / b.Balls * 100).round(1)
    b['Dot %'] = (b.Dots / b.Balls * 100).round(1)
    ok = x[x.player_out_id.notna()]
    kinds = ok.groupby(['player_out_id', 'wkt_kind']).size().unstack(fill_value=0)
    for k, lab in [('caught', 'Caught'), ('bowled', 'Bowled'), ('lbw', 'LBW'), ('stumped', 'Stumped'), ('run out', 'Run out')]:
        b[f'Out {lab}'] = kinds.get(k, pd.Series(dtype=int)).reindex(b.index).fillna(0).astype(int)
    # vs bowler type (dismissal by the bowler only)
    vt = x[x.bowl_type != 'Unknown'].groupby(['batter_id', 'bowl_type']).agg(r=('runs_bat', 'sum'), bf=('bf', 'sum'))
    vw = x[(x.bowler_wkt == 1) & (x.bowl_type != 'Unknown')].groupby(['player_out_id', 'bowl_type']).size()
    vw.index.names = ['batter_id', 'bowl_type']
    vt['w'] = vw.reindex(vt.index).fillna(0)
    vt = vt.reset_index()
    vt = vt[vt.batter_id.isin(b.index)]
    weak, strong, outs_most = {}, {}, {}
    vs_rows = []
    for bid, g in vt.groupby('batter_id'):
        gg = g[g.bf >= MIN_VS_TYPE[fmt]].copy()
        gg['avg'] = gg.r / gg.w.replace(0, np.nan)
        gg['sr'] = gg.r / gg.bf * 100
        gg['bpd'] = gg.bf / gg.w.replace(0, np.nan)  # balls per dismissal
        for _, q in g.iterrows():
            vs_rows.append(dict(batter_id=bid, Type=q.bowl_type, Runs=int(q.r), Balls=int(q.bf), Outs=int(q.w),
                                Average=r1(q.r / q.w) if q.w else None, SR=r1(q.r / q.bf * 100) if q.bf else None))
        if len(gg):
            k = gg.sort_values('bpd').iloc[0]
            if not pd.isna(k.bpd):
                weak[bid] = f"{k.bowl_type} (out every {k.bpd:.0f} balls, avg {k.avg:.0f}, SR {k.sr:.0f})"
            s = gg.sort_values('sr', ascending=False).iloc[0]
            strong[bid] = f"{s.bowl_type} (SR {s.sr:.0f})"
        if g.w.sum():
            t = g.sort_values('w', ascending=False).iloc[0]
            outs_most[bid] = f"{t.bowl_type} ({int(t.w)} of {int(g.w.sum())})"
    b['Most dismissed by'] = pd.Series(outs_most)
    b['Weakest vs'] = pd.Series(weak)
    b['Scores fastest vs'] = pd.Series(strong)
    # phase strike rates
    ph = x.groupby(['batter_id', 'phase']).agg(r=('runs_bat', 'sum'), bf=('bf', 'sum'))
    ph = (ph.r / ph.bf * 100).round(1).unstack()
    for c in ph.columns:
        b[f'SR {c}'] = ph[c]
    pace_spin = x[x.bowl_group != 'Unknown'].groupby(['batter_id', 'bowl_group']).agg(r=('runs_bat', 'sum'), bf=('bf', 'sum'))
    pw = x[(x.bowler_wkt == 1)].groupby(['player_out_id', 'bowl_group']).size()
    pw.index.names = ['batter_id', 'bowl_group']
    pace_spin['w'] = pw.reindex(pace_spin.index).fillna(0)
    for grp in ['Pace', 'Spin']:
        q = pace_spin.xs(grp, level='bowl_group') if grp in pace_spin.index.get_level_values(1) else None
        if q is not None:
            b[f'SR vs {grp}'] = (q.r / q.bf * 100).round(1)
            b[f'Avg vs {grp}'] = (q.r / q.w.replace(0, np.nan)).round(1)
    b['How to bowl (data)'] = [tip(r, fmt) for _, r in b.iterrows()]
    b['Last'] = b.Last.dt.date
    b = b.reset_index().sort_values('Runs', ascending=False)
    vs = pd.DataFrame(vs_rows).merge(b[['batter_id', 'Batter']], on='batter_id')
    return b.drop(columns=['Dots']), vs

def tip(r, fmt):
    parts = []
    if isinstance(r.get('Weakest vs'), str):
        parts.append('Bring on ' + r['Weakest vs'].split(' (')[0])
    tot = max(r.Outs, 1)
    if r['Out Bowled'] + r['Out LBW'] >= 0.3 * tot and r.Outs >= 8:
        parts.append(f"attack the stumps ({(r['Out Bowled'] + r['Out LBW']) * 100 // tot}% bowled/LBW)")
    elif r['Out Caught'] >= 0.7 * tot and r.Outs >= 8:
        parts.append(f"tempt the catch, he holes out {r['Out Caught'] * 100 // tot}% of the time")
    if r['Out Stumped'] >= 0.08 * tot and r.Outs >= 8:
        parts.append('stumping risk, toss it up and beat him in flight')
    sp, pa = r.get('SR vs Spin'), r.get('SR vs Pace')
    if pd.notna(sp) and pd.notna(pa) and abs(sp - pa) > 12:
        parts.append(('slows down vs spin' if sp < pa else 'slows down vs pace') + f' (SR {min(sp, pa):.0f} vs {max(sp, pa):.0f})')
    return '; '.join(parts)

def bowler_profiles(m, d, fmt):
    last = m.date.max()
    x = d[d.date >= last - pd.DateOffset(years=10)]
    g = x.groupby('bowler_id').agg(Bowler=('bowler', 'last'), Type=('bowl_type', 'last'), Group=('bowl_group', 'last'),
                                    Team=('bowl_team', 'last'), Matches=('match_id', 'nunique'), Balls=('legal', 'sum'),
                                    Runs=('runs_total', 'sum'), Wickets=('bowler_wkt', 'sum'), Dots=('dot', 'sum'),
                                    Last=('date', 'max'))
    g = g[g.Balls >= MIN_BALLS_BOWL[fmt]].copy()
    g['Economy'] = (g.Runs / g.Balls * 6).round(2)
    g['Average'] = (g.Runs / g.Wickets.replace(0, np.nan)).round(1)
    g['Strike rate'] = (g.Balls / g.Wickets.replace(0, np.nan)).round(1)
    g['Dot %'] = (g.Dots / g.Balls * 100).round(1)
    w = x[x.bowler_wkt == 1]
    k = w.groupby(['bowler_id', 'wkt_kind']).size().unstack(fill_value=0)
    tot = k.sum(axis=1)
    g['Bowled/LBW %'] = ((k.get('bowled', 0) + k.get('lbw', 0)) / tot * 100).round(0).reindex(g.index)
    g['Caught %'] = ((k.get('caught', 0) + k.get('caught and bowled', 0)) / tot * 100).round(0).reindex(g.index)
    ph = w.groupby(['bowler_id', 'phase']).size().unstack(fill_value=0)
    for c in ph.columns:
        g[f'Wkts {c}'] = ph[c].reindex(g.index).fillna(0).astype(int)
    hand = x[x.bat_hand != 'Unknown'].groupby(['bowler_id', 'bat_hand']).agg(r=('runs_total', 'sum'), b=('legal', 'sum'))
    hw = w[w.bat_hand != 'Unknown'].groupby(['bowler_id', 'bat_hand']).size()
    hand['w'] = hw.reindex(hand.index).fillna(0)
    for h, lab in [('Right-hand bat', 'RHB'), ('Left-hand bat', 'LHB')]:
        if h in hand.index.get_level_values(1):
            q = hand.xs(h, level='bat_hand')
            g[f'Avg vs {lab}'] = (q.r / q.w.replace(0, np.nan)).round(1).reindex(g.index)
            g[f'Econ vs {lab}'] = (q.r / q.b * 6).round(2).reindex(g.index)
    best = x[x.bowler_wkt == 1].groupby(['bowler_id', 'venue']).size().reset_index(name='w').sort_values('w', ascending=False).drop_duplicates('bowler_id').set_index('bowler_id')
    g['Best venue'] = (best.venue + ' (' + best.w.astype(str) + ' wkts)').reindex(g.index)
    g['Last'] = g.Last.dt.date
    return g.reset_index().drop(columns=['Dots']).sort_values('Wickets', ascending=False)

def team_venue(m, fmt):
    rows = []
    last = m.date.max()
    mm = m[m.date >= last - pd.DateOffset(years=10)]
    for side in ['team1', 'team2']:
        t = mm[['venue', side, 'bat_first', 'winner', 'result']].rename(columns={side: 'team'})
        rows.append(t)
    t = pd.concat(rows)
    t['batted_first'] = t.team == t.bat_first
    t['won'] = t.winner == t.team
    out = []
    for (v, team), g in t.groupby(['venue', 'team']):
        if len(g) < 3:
            continue
        f, s = g[g.batted_first], g[~g.batted_first]
        out.append(dict(Venue=v, Team=team, Played=len(g), Won=int(g.won.sum()), **{'Win %': r1(g.won.mean() * 100)},
                        **{'Batting 1st P': len(f), 'Batting 1st W': int(f.won.sum()),
                           'Batting 2nd P': len(s), 'Batting 2nd W': int(s.won.sum())}))
    return pd.DataFrame(out).sort_values(['Venue', 'Played'], ascending=[True, False])

def match_log(m, fmt):
    cols = ['date', 'event', 'venue', 'city', 'team1', 'team2', 'toss_winner', 'toss_decision', 'bat_first']
    for i in range(1, 5 if fmt == 'Test' else 3):
        cols += [f'inn{i}_team', f'inn{i}_runs', f'inn{i}_wkts']
    cols += ['winner', 'result', 'win_by_runs', 'win_by_wkts', 'method', 'match_id']
    x = m[[c for c in cols if c in m]].copy().sort_values('date', ascending=False)
    x['date'] = x.date.dt.date
    return x

def build(key):
    fmt = KEY[key]
    m, d = load(key)
    T = {}
    T['Venue summary'] = venue_summary(m, d, fmt)
    T['Venue phases'] = venue_phase(m, d, fmt)
    T['Venue bowler types'] = venue_bowler_type(m, d, fmt)
    T['Batters'], T['Batter vs type'] = batter_profiles(m, d, fmt)
    T['Bowlers'] = bowler_profiles(m, d, fmt)
    T['Teams at venues'] = team_venue(m, fmt)
    T['Match log'] = match_log(m, fmt)
    meta = dict(fmt=fmt, matches=len(m), first=str(m.date.min().date()), last=str(m.date.max().date()),
                styled_pct=round((d.bowl_type != 'Unknown').mean() * 100, 1))
    return T, meta

if __name__ == '__main__':
    for k in sys.argv[1:]:
        T, meta = build(k)
        print(meta, {n: len(t) for n, t in T.items()})
