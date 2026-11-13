"""Build the static search site: one JSON file per player, ground, team and match, plus a search index."""
import os, re, json, shutil, sys
import pandas as pd, numpy as np
import stats

OUT = os.environ.get('SITE_DIR', 'site')
KEYS = os.environ.get('KEYS', 'ipl t20i odi test t20i_w odi_w test_w').split()
FMT = stats.KEY
BOWLER_WKTS = stats.BOWLER_WKTS
stats.MIN_MATCHES.update({k: 1 for k in stats.MIN_MATCHES})  # every ground gets a page

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')

def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (pd.isna(o) or np.isinf(o)) else round(float(o), 2)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime('%Y-%m-%d')
    if hasattr(o, 'isoformat'):
        return o.isoformat()
    if o is pd.NaT or (not isinstance(o, str) and o is not None and pd.isna(o)):
        return None
    return o

def recs(df):
    return clean(df.to_dict('records'))

def write(path, obj):
    p = os.path.join(OUT, 'data', path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(clean(obj), f, separators=(',', ':'), ensure_ascii=False)

def how_out(r):
    k, b, f = r.wkt_kind, r.bowler, r.fielder
    if not isinstance(k, str): return 'not out'
    if k == 'caught': return f"c {f} b {b}" if isinstance(f, str) else f"c ? b {b}"
    if k == 'caught and bowled': return f"c & b {b}"
    if k == 'bowled': return f"b {b}"
    if k == 'lbw': return f"lbw b {b}"
    if k == 'stumped': return f"st {f} b {b}" if isinstance(f, str) else f"st b {b}"
    if k == 'run out': return f"run out ({f})" if isinstance(f, str) else 'run out'
    return k

def add_recent(index):
    """Same-day India scorecards from CricketData.org, only for matches Cricsheet doesn't have yet."""
    if not os.path.exists('recent_cache.json'):
        return
    from parse import clean_venue
    cache = json.load(open('recent_cache.json', encoding='utf-8'))
    have = {}
    for e in index:
        if e['t'] == 'm':
            have.setdefault((e['n'].split(' vs ')[0], e['n'].split(' vs ')[-1]), []).append(e['d'])
    fmt_of = {'odi': 'ODI', 't20': 'T20I', 'test': 'Test'}
    added = 0
    for mid, c in cache.items():
        m = c.get('match') or {}
        teams = m.get('teams') or []
        if len(teams) != 2 or not m.get('date'):
            continue
        d = pd.Timestamp(m['date'])
        days = {(d + pd.Timedelta(days=k)).strftime('%Y%m%d') for k in (-1, 0, 1)}
        dates = have.get((teams[0], teams[1]), []) + have.get((teams[1], teams[0]), [])
        if any(x in days for x in dates):
            continue  # Cricsheet already has the full ball-by-ball version
        fmt = fmt_of.get(m.get('matchType'), m.get('matchType'))
        venue = clean_venue(m.get('venue') or '')
        inns = []
        for k, sc in enumerate(c.get('scorecard') or [], 1):
            team = (sc.get('inning') or '').replace(' Inning 1', '').replace(' Inning 2', '').strip()
            tot = sc.get('totals') or {}
            bat = [dict(batter=(b.get('batsman') or {}).get('name'), runs=b.get('r'), balls=b.get('b'), fours=b.get('4s'), sixes=b.get('6s'),
                        how=b.get('dismissal-text') or 'not out') for b in sc.get('batting') or []]
            bowl = [dict(bowler=(b.get('bowler') or {}).get('name'), overs=b.get('o'), maidens=b.get('m'), runs=b.get('r'), wkts=b.get('w'), econ=b.get('eco')) for b in sc.get('bowling') or []]
            inns.append(dict(n=k, team=team, runs=tot.get('R'), wkts=tot.get('W'), overs_txt=tot.get('O'), extras=(sc.get('extras') or {}).get('r'),
                             bat=bat, bowl=bowl, overs=[], phases=[], fow=[]))
        if not inns:  # list data only: innings totals
            for k, s in enumerate(m.get('score') or [], 1):
                inns.append(dict(n=k, team=(s.get('inning') or '').rsplit(' Inning', 1)[0], runs=s.get('r'), wkts=s.get('w'), overs_txt=s.get('o'),
                                 extras=None, bat=[], bowl=[], overs=[], phases=[], fow=[]))
        allbat = [dict(b, team=i['team']) for i in inns for b in i['bat']]
        allbowl = [dict(b, team=next((t for t in teams if t != i['team']), '')) for i in inns for b in i['bowl']]
        for b in allbat:
            b['sr'] = round(b['runs'] / b['balls'] * 100, 1) if b.get('balls') else None
        toss = c.get('toss') or [None, None]
        rec = dict(id=f'cd-{mid}', lite=True, fmt=fmt, date=m['date'], event=m.get('name'), stage=None, venue=venue, gid=slug(venue),
                   city=None, team1=teams[0], team2=teams[1], toss=f"{toss[0]} chose to {toss[1]}" if toss[0] else None,
                   winner=c.get('winner'), result=m.get('status'), by_runs=None, by_wkts=None, method=None, pom=None, innings=inns,
                   top_bat=sorted(allbat, key=lambda b: -(b.get('runs') or 0))[:5],
                   top_bowl=sorted(allbowl, key=lambda b: (-(b.get('wkts') or 0), b.get('runs') or 0))[:5])
        write(f'm/cd-{mid}.json', rec)
        index.append(dict(t='m', id=f'cd-{mid}', n=f"{teams[0]} vs {teams[1]}",
                          s=f"{fmt} · {d.strftime('%d %b %Y')} · {venue} · {m.get('status') or ''} · quick scorecard", d=d.strftime('%Y%m%d')))
        added += 1
    print('same-day matches added:', added)

def main():
    if os.path.exists(os.path.join(OUT, 'data')):
        shutil.rmtree(os.path.join(OUT, 'data'))
    titles = json.load(open('wiki_titles.json', encoding='utf-8'))
    people = pd.read_csv('people.csv', dtype=str).set_index('identifier')
    full = {pid: re.sub(r'\s*\(.*\)$', '', titles[ck]) for pid, ck in people.key_cricinfo.dropna().items() if ck in titles}
    styles = pd.read_csv('player_styles.csv').set_index('player_id')
    index = []
    players = {}   # pid -> {name, formats:{}}
    grounds = {}
    teams = {}
    built = {}
    for key in KEYS:
        fmt = FMT[key]
        m, d = stats.load(key)
        m = m.sort_values('date')
        # ---------- innings-level player tables ----------
        d['out_here'] = (d.player_out_id == d.batter_id).astype(int)
        bi = d.groupby(['match_id', 'innings', 'batter_id']).agg(
            batter=('batter', 'first'), team=('bat_team', 'first'), opp=('bowl_team', 'first'), date=('date', 'first'),
            venue=('venue', 'first'), runs=('runs_bat', 'sum'), balls=('bf', 'sum'), fours=('four', 'sum'),
            sixes=('six', 'sum'), first_ball=('ballno', 'first')).reset_index()
        outs = d[d.player_out_id.notna()][['match_id', 'innings', 'player_out_id', 'player_out', 'wkt_kind', 'bowler', 'fielder', 'bowl_type', 'phase', 'ballno']]
        outs = outs.drop_duplicates(['match_id', 'innings', 'player_out_id'])
        # batters dismissed without facing (non-striker run out) also need an innings row
        bi = bi.merge(outs.rename(columns={'player_out_id': 'batter_id'}), on=['match_id', 'innings', 'batter_id'], how='left')
        bi['out'] = bi.wkt_kind.notna().astype(int)
        bi['how'] = [how_out(r) for r in bi.itertuples()]
        # order in innings
        bi['order'] = bi.groupby(['match_id', 'innings']).cumcount() + 1
        bw = d.groupby(['match_id', 'innings', 'bowler_id']).agg(
            bowler=('bowler', 'first'), team=('bowl_team', 'first'), opp=('bat_team', 'first'), date=('date', 'first'),
            venue=('venue', 'first'), balls=('legal', 'sum'), runs=('runs_total', 'sum'), wkts=('bowler_wkt', 'sum'),
            dots=('dot', 'sum'), fours=('four', 'sum'), sixes=('six', 'sum'), wides=('wide', 'sum'), nbs=('noball', 'sum')).reset_index()
        ov_runs = d.groupby(['match_id', 'innings', 'bowler_id', 'over']).runs_total.sum()
        maidens = (ov_runs == 0).groupby(level=[0, 1, 2]).sum()
        bw = bw.merge(maidens.rename('maidens').reset_index(), on=['match_id', 'innings', 'bowler_id'], how='left')
        bw['overs'] = (bw.balls // 6).astype(str) + '.' + (bw.balls % 6).astype(str)
        bw['econ'] = (bw.runs / bw.balls * 6).round(2)
        # ---------- matches ----------
        mi = m.set_index('match_id')
        dg = d.groupby('match_id')
        big = bi.groupby('match_id'); bwg = bw.groupby('match_id')
        for mid, g in dg:
            r = mi.loc[mid]
            inns = []
            for n, gi in g.groupby('innings'):
                bat = big.get_group(mid); bat = bat[bat.innings == n].sort_values('order')
                bowl = bwg.get_group(mid); bowl = bowl[bowl.innings == n]
                ovs = gi.groupby('over').agg(runs=('runs_total', 'sum'), wkts=('wicket', 'sum')).reset_index()
                ovs['cum'] = ovs.runs.cumsum()
                ph = gi.groupby('phase', sort=False).agg(runs=('runs_total', 'sum'), wkts=('wicket', 'sum'), balls=('legal', 'sum'),
                                                         fours=('four', 'sum'), sixes=('six', 'sum'), dots=('dot', 'sum')).reset_index()
                fow = gi[gi.wicket == 1].copy()
                fow['score'] = gi.runs_total.cumsum()[gi.wicket == 1]
                fow['wn'] = range(1, len(fow) + 1)
                ext = gi.extras.sum()
                inns.append(dict(n=int(n), team=gi.bat_team.iat[0], runs=int(gi.runs_total.sum()), wkts=int(gi.wicket.sum()),
                                 balls=int(gi.legal.sum()), extras=int(ext),
                                 bat=recs(bat[['batter', 'batter_id', 'runs', 'balls', 'fours', 'sixes', 'how']]),
                                 bowl=recs(bowl[['bowler', 'bowler_id', 'overs', 'maidens', 'runs', 'wkts', 'econ', 'dots']]),
                                 overs=recs(ovs), phases=recs(ph),
                                 fow=recs(fow[['wn', 'score', 'ballno', 'player_out', 'wkt_kind', 'bowler']])))
            # performers
            allbat = big.get_group(mid).copy(); allbat['sr'] = (allbat.runs / allbat.balls.replace(0, np.nan) * 100).round(1)
            allbowl = bwg.get_group(mid)
            top_bat = allbat.sort_values(['runs', 'balls'], ascending=[False, True]).head(5)
            top_bowl = allbowl.sort_values(['wkts', 'runs'], ascending=[False, True]).head(5)
            mrec = dict(id=f'{key}-{mid}', fmt=fmt, date=r.date.strftime('%Y-%m-%d'), event=r.event, stage=r.stage,
                        venue=r.venue, gid=slug(r.venue), city=r.city, team1=r.team1, team2=r.team2,
                        toss=f"{r.toss_winner} chose to {r.toss_decision}" if isinstance(r.toss_winner, str) else None,
                        winner=r.winner, result=r.result, by_runs=r.win_by_runs, by_wkts=r.win_by_wkts, method=r.method, pom=r.pom,
                        innings=inns, top_bat=recs(top_bat[['batter', 'batter_id', 'team', 'runs', 'balls', 'fours', 'sixes', 'sr']]),
                        top_bowl=recs(top_bowl[['bowler', 'bowler_id', 'team', 'overs', 'runs', 'wkts', 'econ']]))
            write(f'm/{key}-{mid}.json', mrec)
            res = (f"{r.winner} won" + (f" by {int(r.win_by_runs)} runs" if pd.notna(r.win_by_runs) else (f" by {int(r.win_by_wkts)} wkts" if pd.notna(r.win_by_wkts) else ''))) if isinstance(r.winner, str) else (r.result or '')
            index.append(dict(t='m', id=f'{key}-{mid}', n=f"{r.team1} vs {r.team2}", s=f"{fmt} · {r.date.strftime('%d %b %Y')} · {r.venue} · {res}", d=r.date.strftime('%Y%m%d')))
        # ---------- grounds ----------
        vs = stats.venue_summary(m, d, fmt)
        vp = stats.venue_phase(m, d, fmt)
        vb = stats.venue_bowler_type(m, d, fmt)
        vb = vb.drop(columns=['Venue'] if False else [])
        ybs = m[m.winner.notna() & m.method.isna()].groupby(['venue', 'year']).agg(
            matches=('match_id', 'size'), avg1=('inn1_runs', 'mean'), avg2=('inn2_runs', 'mean'),
            bf_win=('winner', lambda s: 0)).reset_index()
        bfw = m[m.winner.notna()].assign(bf=lambda x: (x.winner == x.bat_first).astype(int)).groupby(['venue', 'year']).bf.mean() * 100
        ybs = ybs.merge(bfw.rename('bat1_win_pct').reset_index(), on=['venue', 'year'], how='left').drop(columns='bf_win')
        last = m.date.max()
        d5 = d[d.date >= last - pd.DateOffset(years=5)]
        top_b = bi[bi.date >= last - pd.DateOffset(years=5)].groupby(['venue', 'batter_id']).agg(name=('batter', 'last'), runs=('runs', 'sum'), balls=('balls', 'sum'), inns=('match_id', 'nunique'), outs=('out', 'sum')).reset_index()
        top_w = bw[bw.date >= last - pd.DateOffset(years=5)].groupby(['venue', 'bowler_id']).agg(name=('bowler', 'last'), wkts=('wkts', 'sum'), balls=('balls', 'sum'), runs=('runs', 'sum')).reset_index()
        tbg, twg = top_b.groupby('venue'), top_w.groupby('venue')
        vsg, vpg, vbg, ybg = vs.groupby('Venue'), vp.groupby('Venue'), vb.groupby('Venue'), ybs.groupby('venue')
        mg = m.groupby('venue')
        for v, mm in mg:
            gid = slug(v)
            G = grounds.setdefault(gid, dict(id=gid, name=v, city=mm.city.dropna().iat[0] if mm.city.notna().any() else None, formats={}))
            periods = {}
            for p, srow in vsg.get_group(v).groupby('Period'):
                ph = vpg.get_group(v) if v in vpg.groups else pd.DataFrame()
                ph = ph[ph.Period == p] if len(ph) else ph
                most = None
                if len(ph):
                    tot = ph.assign(w=ph['Avg wkts in phase'] * ph['Innings sampled']).groupby('Phase').w.sum()
                    most = dict(phase=tot.idxmax(), share=round(tot.max() / tot.sum() * 100, 1) if tot.sum() else None)
                    by_inn = {}
                    for inn, x in ph.groupby('Innings'):
                        by_inn[int(inn)] = x.loc[x['Avg wkts in phase'].idxmax(), 'Phase']
                    most['by_innings'] = by_inn
                bt = vbg.get_group(v) if v in vbg.groups else pd.DataFrame()
                bt = bt[bt.Period == p] if len(bt) else bt
                periods[p] = dict(summary=recs(srow.drop(columns=['Period', 'Venue']))[0], most_wkts_phase=most,
                                  phases=recs(ph.drop(columns=['Period', 'Venue'])) if len(ph) else [],
                                  btypes=recs(bt.drop(columns=['Period', 'Venue'])) if len(bt) else [])
            recent = mm.sort_values('date', ascending=False).head(15)
            G['formats'][fmt] = dict(
                matches=len(mm), first=mm.date.min().strftime('%Y-%m-%d'), last=mm.date.max().strftime('%Y-%m-%d'), periods=periods,
                by_year=recs(ybg.get_group(v)) if v in ybg.groups else [],
                recent=[dict(id=f'{key}-{x.match_id}', date=x.date.strftime('%Y-%m-%d'), t=f"{x.team1} vs {x.team2}",
                             s=f"{x.inn1_team} {x.inn1_runs}/{x.inn1_wkts}" + (f", {x.inn2_team} {x.inn2_runs}/{x.inn2_wkts}" if isinstance(x.inn2_team, str) else ''),
                             w=x.winner) for x in recent.itertuples()],
                top_bat=recs(tbg.get_group(v).sort_values('runs', ascending=False).head(10)) if v in tbg.groups else [],
                top_bowl=recs(twg.get_group(v).sort_values('wkts', ascending=False).head(10)) if v in twg.groups else [])
        # ---------- teams ----------
        tv = stats.team_venue(m, fmt) if len(m) else pd.DataFrame()
        for side in ['team1', 'team2']:
            pass
        long = pd.concat([m.assign(team=m.team1, opp=m.team2), m.assign(team=m.team2, opp=m.team1)])
        long['won'] = (long.winner == long.team).astype(int)
        long['lost'] = (long.winner.notna() & (long.winner != long.team)).astype(int)
        long['bf'] = (long.bat_first == long.team)
        tg = long.groupby('team')
        bi_t = bi.groupby('team'); bw_t = bw.groupby('team')
        recent_cut = last - pd.DateOffset(years=2)
        for t, x in tg:
            tid = slug(t)
            T = teams.setdefault(tid, dict(id=tid, name=t, formats={}))
            yr = x.groupby('year').agg(played=('match_id', 'size'), won=('won', 'sum'), lost=('lost', 'sum')).reset_index()
            h2h = x.groupby('opp').agg(played=('match_id', 'size'), won=('won', 'sum'), lost=('lost', 'sum')).reset_index().sort_values('played', ascending=False)
            bfx, bsx = x[x.bf], x[~x.bf]
            rb = bi_t.get_group(t) if t in bi_t.groups else pd.DataFrame(columns=['date'])
            rb = rb[rb.date >= recent_cut].groupby('batter_id').agg(name=('batter', 'last'), runs=('runs', 'sum'), balls=('balls', 'sum'), inns=('match_id', 'nunique'), outs=('out', 'sum')).reset_index().sort_values('runs', ascending=False).head(12) if len(rb) else pd.DataFrame()
            rw = bw_t.get_group(t) if t in bw_t.groups else pd.DataFrame(columns=['date'])
            rw = rw[rw.date >= recent_cut].groupby('bowler_id').agg(name=('bowler', 'last'), wkts=('wkts', 'sum'), balls=('balls', 'sum'), runs=('runs', 'sum')).reset_index().sort_values('wkts', ascending=False).head(12) if len(rw) else pd.DataFrame()
            gr = tv[tv.Team == t] if len(tv) else pd.DataFrame()
            T['formats'][fmt] = dict(played=len(x), won=int(x.won.sum()), lost=int(x.lost.sum()),
                                     bat_first=dict(p=len(bfx), w=int(bfx.won.sum())), bat_second=dict(p=len(bsx), w=int(bsx.won.sum())),
                                     by_year=recs(yr), h2h=recs(h2h.head(15)),
                                     grounds=recs(gr.drop(columns=['Team']).head(20)) if len(gr) else [],
                                     top_bat=recs(rb), top_bowl=recs(rw),
                                     recent=[dict(id=f'{key}-{r.match_id}', date=r.date.strftime('%Y-%m-%d'), opp=r.opp, venue=r.venue,
                                                  res='Won' if r.won else ('Lost' if r.lost else (r.result or '-'))) for r in x.sort_values('date', ascending=False).head(15).itertuples()])
        # ---------- players ----------
        bi['yr'] = bi.date.dt.year; bw['yr'] = bw.date.dt.year
        for pid, x in bi.groupby('batter_id'):
            P = players.setdefault(pid, dict(id=pid, name=x.batter.iat[-1], formats={}))
            F = P['formats'].setdefault(fmt, {})
            outs_ = int(x.out.sum()); runs = int(x.runs.sum()); balls = int(x.balls.sum())
            yr = x.groupby('yr').agg(inns=('match_id', 'size'), runs=('runs', 'sum'), balls=('balls', 'sum'), outs=('out', 'sum')).reset_index()
            yr['avg'] = (yr.runs / yr.outs.replace(0, np.nan)).round(1); yr['sr'] = (yr.runs / yr.balls.replace(0, np.nan) * 100).round(1)
            kinds = x.wkt_kind.value_counts().to_dict()
            F['bat'] = dict(inns=len(x), runs=runs, balls=balls, outs=outs_, avg=runs / outs_ if outs_ else None,
                            sr=runs / balls * 100 if balls else None, fours=int(x.fours.sum()), sixes=int(x.sixes.sum()),
                            hs=int(x.runs.max()), fifties=int(((x.runs >= 50) & (x.runs < 100)).sum()), hundreds=int((x.runs >= 100).sum()),
                            ducks=int(((x.runs == 0) & (x.out == 1)).sum()), dismissals=kinds,
                            out_phase=x.phase.value_counts().to_dict(), out_to_type=x[x.wkt_kind.isin(BOWLER_WKTS)].bowl_type.value_counts().to_dict(),
                            by_year=recs(yr),
                            last=[dict(id=f'{key}-{r.match_id}', date=r.date.strftime('%Y-%m-%d'), opp=r.opp, venue=r.venue, runs=r.runs, balls=r.balls, how=r.how)
                                  for r in x.sort_values('date', ascending=False).head(15).itertuples()])
        # batter vs type & phase (ball level)
        bvt = d[d.bowl_type != 'Unknown'].groupby(['batter_id', 'bowl_type']).agg(runs=('runs_bat', 'sum'), balls=('bf', 'sum'), dots=('dot', 'sum'), fours=('four', 'sum'), sixes=('six', 'sum')).reset_index()
        bvw = d[d.bowler_wkt == 1].groupby(['player_out_id', 'bowl_type']).size().rename('outs').reset_index().rename(columns={'player_out_id': 'batter_id'})
        bvt = bvt.merge(bvw, on=['batter_id', 'bowl_type'], how='left').fillna({'outs': 0})
        bph = d.groupby(['batter_id', 'phase']).agg(runs=('runs_bat', 'sum'), balls=('bf', 'sum'), dots=('dot', 'sum'), fours=('four', 'sum'), sixes=('six', 'sum')).reset_index()
        bpo = d[d.player_out_id.notna()].groupby(['player_out_id', 'phase']).size().rename('outs').reset_index().rename(columns={'player_out_id': 'batter_id'})
        bph = bph.merge(bpo, on=['batter_id', 'phase'], how='left').fillna({'outs': 0})
        for pid, x in bvt.groupby('batter_id'):
            if pid in players and fmt in players[pid]['formats'] and 'bat' in players[pid]['formats'][fmt]:
                players[pid]['formats'][fmt]['bat']['vs_type'] = recs(x.drop(columns='batter_id').sort_values('balls', ascending=False))
        for pid, x in bph.groupby('batter_id'):
            if pid in players and fmt in players[pid]['formats'] and 'bat' in players[pid]['formats'][fmt]:
                players[pid]['formats'][fmt]['bat']['phases'] = recs(x.drop(columns='batter_id'))
        # bowling
        dw = d[d.bowler_wkt == 1]
        for pid, x in bw.groupby('bowler_id'):
            P = players.setdefault(pid, dict(id=pid, name=x.bowler.iat[-1], formats={}))
            F = P['formats'].setdefault(fmt, {})
            balls, runs, wk = int(x.balls.sum()), int(x.runs.sum()), int(x.wkts.sum())
            yr = x.groupby('yr').agg(inns=('match_id', 'size'), wkts=('wkts', 'sum'), balls=('balls', 'sum'), runs=('runs', 'sum')).reset_index()
            yr['econ'] = (yr.runs / yr.balls.replace(0, np.nan) * 6).round(2); yr['avg'] = (yr.runs / yr.wkts.replace(0, np.nan)).round(1)
            best = x.sort_values(['wkts', 'runs'], ascending=[False, True]).iloc[0]
            F['bowl'] = dict(inns=len(x), balls=balls, runs=runs, wkts=wk, econ=runs / balls * 6 if balls else None,
                             avg=runs / wk if wk else None, sr=balls / wk if wk else None, dots=int(x.dots.sum()),
                             best=f"{int(best.wkts)}/{int(best.runs)}", four_plus=int((x.wkts >= 4).sum()), five_plus=int((x.wkts >= 5).sum()),
                             by_year=recs(yr),
                             last=[dict(id=f'{key}-{r.match_id}', date=r.date.strftime('%Y-%m-%d'), opp=r.opp, venue=r.venue, fig=f"{r.wkts}/{r.runs}", overs=r.overs)
                                   for r in x.sort_values('date', ascending=False).head(15).itertuples()])
        bwk = dw.groupby(['bowler_id', 'wkt_kind']).size().rename('n').reset_index()
        bwp = d.groupby(['bowler_id', 'phase']).agg(balls=('legal', 'sum'), runs=('runs_total', 'sum'), wkts=('bowler_wkt', 'sum'), dots=('dot', 'sum')).reset_index()
        bwh = d[d.bat_hand != 'Unknown'].groupby(['bowler_id', 'bat_hand']).agg(balls=('legal', 'sum'), runs=('runs_total', 'sum'), wkts=('bowler_wkt', 'sum')).reset_index()
        victims = dw.groupby(['bowler_id', 'player_out_id']).agg(name=('player_out', 'last'), n=('wicket', 'size')).reset_index()
        for name_, tab in [('kinds', bwk), ('phases', bwp), ('vs_hand', bwh)]:
            for pid, x in tab.groupby('bowler_id'):
                if pid in players and 'bowl' in players[pid]['formats'].get(fmt, {}):
                    players[pid]['formats'][fmt]['bowl'][name_] = recs(x.drop(columns='bowler_id'))
        for pid, x in victims.groupby('bowler_id'):
            if pid in players and 'bowl' in players[pid]['formats'].get(fmt, {}):
                players[pid]['formats'][fmt]['bowl']['victims'] = recs(x.sort_values('n', ascending=False).head(10).drop(columns='bowler_id'))
        # team of player
        for pid, x in bi.groupby('batter_id'):
            players[pid]['formats'][fmt]['team'] = x.team.iat[-1]; players[pid]['formats'][fmt]['last_date'] = x.date.max().strftime('%Y-%m-%d')
        for pid, x in bw.groupby('bowler_id'):
            players[pid]['formats'][fmt].setdefault('team', x.team.iat[-1]); players[pid]['formats'][fmt].setdefault('last_date', x.date.max().strftime('%Y-%m-%d'))
        built[fmt] = dict(matches=len(m), first=m.date.min().strftime('%Y-%m-%d'), last=m.date.max().strftime('%Y-%m-%d'),
                          decided=int(m.winner.notna().sum()), ties=int((m.result == 'tie').sum()), no_results=int((m.result == 'no result').sum()),
                          draws=int((m.result == 'draw').sum()), shortened=int(m.shortened.fillna(False).sum()), follow_ons=int(m.follow_on.sum()),
                          balls=int(len(d)), styled_balls_pct=round(float((d.bowl_type != 'Unknown').mean() * 100), 1))
        print(fmt, 'done', flush=True)
    # ---------- write players, grounds, teams ----------
    for pid, P in players.items():
        P['full'] = full.get(pid)
        if pid in styles.index:
            s = styles.loc[pid]
            P['bowl_style'] = s.bowl_type if isinstance(s.bowl_type, str) else None
            P['bat_hand'] = s.bat_hand if isinstance(s.bat_hand, str) else None
        # phase with most dismissals / wickets
        for fmt, F in P['formats'].items():
            if 'bat' in F and F['bat'].get('out_phase'):
                op = F['bat']['out_phase']; F['bat']['most_out_phase'] = max(op, key=op.get)
            if 'bowl' in F and F['bowl'].get('phases'):
                ph = F['bowl']['phases']; F['bowl']['most_wkts_phase'] = max(ph, key=lambda r: r['wkts'] or 0)['phase']
        write(f'p/{pid}.json', P)
        fm = sorted(P['formats'], key=lambda f: -max(P['formats'][f].get('bat', {}).get('inns', 0), P['formats'][f].get('bowl', {}).get('inns', 0)))
        team = P['formats'][fm[0]].get('team') if fm else None
        act = sum(P['formats'][f].get('bat', {}).get('runs', 0) + 20 * P['formats'][f].get('bowl', {}).get('wkts', 0) for f in fm)
        index.append(dict(t='p', id=pid, n=P['full'] or P['name'], a=P['name'], s=f"{team or ''} · {', '.join(fm)}", w=act))
    for gid, G in grounds.items():
        write(f'g/{gid}.json', G)
        index.append(dict(t='g', id=gid, n=G['name'], s=f"{G['city'] or ''} · " + ', '.join(f"{f} {v['matches']}" for f, v in G['formats'].items()), w=sum(v['matches'] for v in G['formats'].values())))
    for tid, T in teams.items():
        write(f't/{tid}.json', T)
        index.append(dict(t='t', id=tid, n=T['name'], s=', '.join(f"{f} {v['played']}" for f, v in T['formats'].items()), w=sum(v['played'] for v in T['formats'].values())))
    add_recent(index)
    write('index.json', index)
    write('meta.json', dict(built=pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M UTC'), formats=built,
                            sources=[dict(name='Cricsheet ball-by-ball data (ODC-BY licence)', url='https://cricsheet.org', use='all matches, scores, results and every delivery'),
                                     dict(name='Wikipedia / Wikidata player pages', url='https://www.wikidata.org', use='bowling style (pace/spin type), batting hand, full names'),
                                     dict(name='CricketData.org free plan', url='https://cricketdata.org', use="same-day scorecards for India men's matches until Cricsheet publishes them")]))
    print('players', len(players), 'grounds', len(grounds), 'teams', len(teams), 'index', len(index))

if __name__ == '__main__':
    main()
