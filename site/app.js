/* Cricket Insights front end: hash-routed pages over static JSON. */
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const f1 = (v) => (v === null || v === undefined || Number.isNaN(v) ? '–' : (+v).toFixed(1).replace(/\.0$/, ''));
const f2 = (v) => (v === null || v === undefined || Number.isNaN(v) ? '–' : (+v).toFixed(2));
const n0 = (v) => (v === null || v === undefined ? '–' : Math.round(v).toLocaleString('en-IN'));
const cache = {};
const getJSON = async (p) => (cache[p] ??= fetch('data/' + p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
const app = $('#app');
const charts = [];
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PHASE_ORDER = (a, b) => (parseInt((a.match(/\((\d+)/) || [])[1]) || 0) - (parseInt((b.match(/\((\d+)/) || [])[1]) || 0);
const FORMATS = ['IPL', 'T20I', 'ODI', 'Test'];
const isSpin = (t) => /spin|orthodox/i.test(t || '');

function chart(canvas, cfg) {
  if (!window.Chart) return;
  const ink = css('--muted'), line = css('--line');
  Chart.defaults.color = ink; Chart.defaults.borderColor = line; Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 12 } } } }, cfg.options || {});
  charts.push(new Chart(canvas, cfg));
}
const box = (title, inner, note) => `<div class="panel"><h3>${esc(title)}</h3>${inner}${note ? `<p class="note">${esc(note)}</p>` : ''}</div>`;
const canv = (id) => `<div class="chartbox"><canvas id="${id}"></canvas></div>`;
const card = (k, v, cls = '') => `<div class="card ${cls}"><div class="k">${esc(k)}</div><div class="v ${cls.includes('wide') ? 'txt' : ''}">${esc(v)}</div></div>`;
const table = (cols, rows, opts = {}) => `<div class="scroll"><table><thead><tr>${cols.map((c) => `<th class="${c.l ? 'l' : ''}">${esc(c.h)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr class="${opts.hl && opts.hl(r) ? 'hl' : ''}">${cols.map((c) => `<td class="${c.l ? 'l' : ''} ${c.cls || ''}">${c.html ? c.html(r) : esc(c.f ? c.f(r) : r[c.k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const plink = (name, id) => (id ? `<a href="#/p/${esc(id)}">${esc(name)}</a>` : esc(name));
const mlink = (txt, id) => `<a href="#/m/${esc(id)}">${esc(txt)}</a>`;
const resPill = (r) => `<span class="pill ${r === 'Won' ? 'w' : r === 'Lost' ? 'l' : 'n'}">${esc(r)}</span>`;
const dt = (s) => new Date(s + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

/* ---------------- search ---------------- */
const ALIAS = { ind: 'india', nz: 'new zealand', aus: 'australia', sa: 'south africa', rsa: 'south africa', eng: 'england', pak: 'pakistan', sl: 'sri lanka', ban: 'bangladesh', afg: 'afghanistan', wi: 'west indies', ire: 'ireland', zim: 'zimbabwe', ned: 'netherlands', sco: 'scotland', nep: 'nepal', uae: 'united arab emirates', usa: 'united states of america',
  rcb: 'royal challengers', csk: 'chennai super kings', mi: 'mumbai indians', kkr: 'kolkata knight riders', srh: 'sunrisers hyderabad', dc: 'delhi capitals', pbks: 'punjab kings', kxip: 'kings xi punjab', rr: 'rajasthan royals', lsg: 'lucknow super giants', gt: 'gujarat titans',
  chepauk: 'chidambaram', wankhede: 'wankhede', mcg: 'melbourne cricket ground', scg: 'sydney cricket ground', motera: 'narendra modi' };
let INDEX = null;
const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ');
async function loadIndex() {
  if (INDEX) return INDEX;
  const raw = await getJSON('index.json');
  INDEX = raw.map((e) => Object.assign(e, { h: norm(`${e.n} ${e.a || ''} ${e.s || ''}`) }));
  return INDEX;
}
function search(q) {
  const toks = norm(q).split(/\s+/).filter((t) => t && t !== 'vs' && t !== 'v').map((t) => ALIAS[t] || t);
  if (!toks.length) return [];
  const out = [];
  for (const e of INDEX) {
    if (!toks.every((t) => e.h.includes(t))) continue;
    const n = norm(e.n + ' ' + (e.a || ''));
    let s = 0;
    toks.forEach((t) => { if (n.startsWith(t)) s += 30; else if (n.includes(' ' + t)) s += 20; else if (n.includes(t)) s += 10; });
    if (e.t === 'm') s += 5 + (+e.d) / 1e8; else s += Math.log10((e.w || 1) + 1) * 4 + (e.t === 't' ? 6 : e.t === 'g' ? 3 : 0);
    out.push([s, e]);
  }
  return out.sort((a, b) => b[0] - a[0]).slice(0, 30).map((x) => x[1]);
}
const TAG = { p: 'Player', g: 'Ground', t: 'Team', m: 'Match' };
function setupSearch() {
  const q = $('#q'), res = $('#results');
  let sel = -1, items = [];
  const render = async () => {
    await loadIndex();
    items = search(q.value);
    sel = -1;
    res.hidden = !items.length;
    res.innerHTML = items.map((e) => `<a href="#/${e.t}/${esc(e.id)}"><span class="tag ${e.t}">${TAG[e.t]}</span><span><b>${esc(e.n)}</b> <span class="sub">${esc(e.s || '')}</span></span></a>`).join('');
  };
  q.addEventListener('input', render);
  q.addEventListener('focus', () => { loadIndex(); if (items.length) res.hidden = false; });
  q.addEventListener('keydown', (ev) => {
    const as = [...res.querySelectorAll('a')];
    if (ev.key === 'ArrowDown') { sel = Math.min(sel + 1, as.length - 1); ev.preventDefault(); }
    else if (ev.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); ev.preventDefault(); }
    else if (ev.key === 'Enter') { const a = as[Math.max(sel, 0)]; if (a) location.hash = a.getAttribute('href'); res.hidden = true; q.blur(); return; }
    else if (ev.key === 'Escape') { res.hidden = true; return; }
    as.forEach((a, i) => a.classList.toggle('sel', i === sel));
  });
  document.addEventListener('click', (ev) => { if (!ev.target.closest('.searchwrap')) res.hidden = true; });
  res.addEventListener('click', () => { res.hidden = true; q.value = ''; });
}

/* ---------------- pages ---------------- */
async function home() {
  await loadIndex();
  const meta = await getJSON('meta.json');
  const latest = INDEX.filter((e) => e.t === 'm').sort((a, b) => b.d - a.d).slice(0, 24);
  const topG = INDEX.filter((e) => e.t === 'g').sort((a, b) => b.w - a.w).slice(0, 12);
  const topT = INDEX.filter((e) => e.t === 't').sort((a, b) => b.w - a.w).slice(0, 14);
  app.innerHTML = `
  <section class="home-hero">
    <h1>Search any player, ground, team or match</h1>
    <p class="sub">How every pitch plays, which bowlers take wickets there, how each batter gets out, and full match reviews. Updated every week.</p>
    <div class="chips">${['Virat Kohli', 'Jasprit Bumrah', 'Chinnaswamy', 'Wankhede', 'IND vs NZ', 'SA vs AUS', 'Rashid Khan', 'Eden Gardens'].map((s) => `<a href="#" data-q="${esc(s)}">${esc(s)}</a>`).join('')}</div>
  </section>
  <div class="grid2">
    ${box('Latest matches', `<div class="list">${latest.map((e) => `<a class="row" href="#/m/${esc(e.id)}"><span><b>${esc(e.n)}</b></span><span class="sub">${esc(e.s)}</span></a>`).join('')}</div>`)}
    <div>
      ${box('Most-played grounds', `<div class="list">${topG.map((e) => `<a class="row" href="#/g/${esc(e.id)}"><span>${esc(e.n)}</span><span class="sub">${esc(e.s)}</span></a>`).join('')}</div>`)}
      <div style="height:16px"></div>
      ${box('Teams', `<div class="chips" style="justify-content:flex-start">${topT.map((e) => `<a href="#/t/${esc(e.id)}">${esc(e.n)}</a>`).join('')}</div>`)}
    </div>
  </div>
  <p class="note">Data covers ${Object.entries(meta.formats).map(([f, v]) => `${f}: ${v.matches} matches to ${dt(v.last)}`).join(' · ')}.</p>`;
  app.querySelectorAll('[data-q]').forEach((a) => a.addEventListener('click', (ev) => { ev.preventDefault(); const q = $('#q'); q.value = a.dataset.q; q.dispatchEvent(new Event('input')); q.focus(); }));
}

function formatTabs(formats, cur, onPick) {
  const el = document.createElement('div'); el.className = 'tabs';
  FORMATS.filter((f) => formats.includes(f)).forEach((f) => {
    const b = document.createElement('button'); b.textContent = f === 'T20I' ? 'T20 Internationals' : f; if (f === cur) b.className = 'on';
    b.onclick = () => onPick(f); el.appendChild(b);
  });
  return el;
}
const pickFormat = (obj, scoreFn) => FORMATS.filter((f) => obj[f]).sort((a, b) => scoreFn(obj[b]) - scoreFn(obj[a]))[0];

/* ----- player ----- */
async function player(id, fmt) {
  const P = await getJSON(`p/${id}.json`);
  const fmts = Object.keys(P.formats);
  fmt = fmts.includes(fmt) ? fmt : pickFormat(P.formats, (x) => (x.bat?.inns || 0) + (x.bowl?.inns || 0));
  const F = P.formats[fmt];
  app.innerHTML = `<h1>${esc(P.full || P.name)}</h1>
    <p class="sub">${esc([F.team, P.bat_hand, P.bowl_style].filter(Boolean).join(' · '))}${F.last_date ? ` · last played ${dt(F.last_date)}` : ''}</p><div id="ft"></div><div id="body"></div>`;
  $('#ft').appendChild(formatTabs(fmts, fmt, (f) => { location.hash = `#/p/${id}/${f}`; }));
  let h = '';
  const B = F.bat, W = F.bowl;
  if (B && B.inns) {
    const kinds = Object.entries(B.dismissals || {}).sort((a, b) => b[1] - a[1]);
    const topKind = kinds[0];
    const outTypes = Object.entries(B.out_to_type || {}).sort((a, b) => b[1] - a[1]);
    const vs = (B.vs_type || []).filter((r) => r.balls >= 30).map((r) => Object.assign(r, { bpd: r.outs ? r.balls / r.outs : null, sr: r.runs / r.balls * 100, avg: r.outs ? r.runs / r.outs : null }));
    const weak = vs.filter((r) => r.bpd).sort((a, b) => a.bpd - b.bpd)[0];
    const phases = (B.phases || []).sort((a, b) => PHASE_ORDER(a.phase, b.phase));
    h += `<h2>Batting</h2><div class="cards">
      ${card('Innings', B.inns)}${card('Runs', n0(B.runs))}${card('Average', f1(B.avg))}${card('Strike rate', f1(B.sr))}
      ${card('High score', B.hs)}${card('100s / 50s', `${B.hundreds} / ${B.fifties}`)}${card('4s / 6s', `${B.fours} / ${B.sixes}`)}${card('Ducks', B.ducks)}</div>
      <div class="callout">Gets out most often <b>${esc(topKind ? topKind[0] : '–')}</b>${topKind && B.outs ? ` (${Math.round(topKind[1] / B.outs * 100)}% of dismissals)` : ''},
      most often in the <b>${esc(B.most_out_phase || '–')}</b> phase${outTypes[0] ? `, and most often to <b>${esc(outTypes[0][0])}</b> bowling (${outTypes[0][1]} times)` : ''}.
      ${weak ? `Weakest against <b>${esc(weak.bowl_type)}</b>: out every ${f1(weak.bpd)} balls, average ${f1(weak.avg)}.` : ''}</div>
      <div class="grid2">
        ${box('Runs and average by year', canv('c-byr'))}
        ${box('How he gets out', canv('c-kind'))}
        ${box('Phase by phase', canv('c-ph'), 'Bars: dismissals in each phase. Line: strike rate.')}
        ${box('Against each bowler type', canv('c-vs'), 'Balls faced per dismissal (longer bar = harder to get out). Types with under 30 balls left out.')}
      </div>
      <h2>Against bowler types</h2>${box('', table([{ h: 'Bowler type', k: 'bowl_type', l: 1 }, { h: 'Runs', k: 'runs' }, { h: 'Balls', k: 'balls' }, { h: 'Outs', k: 'outs' }, { h: 'Average', f: (r) => f1(r.avg) }, { h: 'SR', f: (r) => f1(r.sr) }, { h: 'Balls/out', f: (r) => f1(r.bpd) }, { h: 'Dot %', f: (r) => f1(r.dots / r.balls * 100) }, { h: '4s', k: 'fours' }, { h: '6s', k: 'sixes' }], vs.sort((a, b) => b.balls - a.balls), { hl: (r) => weak && r.bowl_type === weak.bowl_type }))}
      <h2>Last 15 innings</h2>${box('', table([{ h: 'Date', f: (r) => dt(r.date), l: 1 }, { h: 'Opponent', k: 'opp', l: 1 }, { h: 'Ground', k: 'venue', l: 1 }, { h: 'Runs', html: (r) => mlink(r.runs, r.id) }, { h: 'Balls', k: 'balls' }, { h: 'How out', k: 'how', cls: 'how' }], B.last))}`;
    setTimeout(() => {
      const yr = B.by_year || [];
      chart($('#c-byr'), { type: 'bar', data: { labels: yr.map((r) => r.yr), datasets: [{ label: 'Runs', data: yr.map((r) => r.runs), backgroundColor: css('--accent'), yAxisID: 'y' }, { type: 'line', label: 'Average', data: yr.map((r) => r.avg), borderColor: css('--accent2'), backgroundColor: css('--accent2'), tension: 0, yAxisID: 'y1' }] }, options: { scales: { y: { beginAtZero: true }, y1: { position: 'right', beginAtZero: true, grid: { display: false } } } } });
      chart($('#c-kind'), { type: 'doughnut', data: { labels: kinds.map((k) => k[0]), datasets: [{ data: kinds.map((k) => k[1]), backgroundColor: ['#0f6b4f', '#c2410c', '#2563eb', '#7c3aed', '#ca8a04', '#64748b', '#db2777'] }] }, options: { plugins: { legend: { position: 'right' } } } });
      chart($('#c-ph'), { type: 'bar', data: { labels: phases.map((r) => r.phase), datasets: [{ label: 'Dismissals', data: phases.map((r) => r.outs), backgroundColor: css('--accent2'), yAxisID: 'y' }, { type: 'line', label: 'Strike rate', data: phases.map((r) => r.balls ? r.runs / r.balls * 100 : null), borderColor: css('--accent'), backgroundColor: css('--accent'), yAxisID: 'y1' }] }, options: { scales: { y: { beginAtZero: true }, y1: { position: 'right', beginAtZero: true, grid: { display: false } } } } });
      const vv = vs.filter((r) => r.bpd).sort((a, b) => a.bpd - b.bpd);
      chart($('#c-vs'), { type: 'bar', data: { labels: vv.map((r) => r.bowl_type), datasets: [{ label: 'Balls per dismissal', data: vv.map((r) => r.bpd), backgroundColor: vv.map((r) => (isSpin(r.bowl_type) ? '#7c3aed' : '#0f6b4f')) }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
    });
  }
  if (W && W.balls >= 6) {
    const ph = (W.phases || []).sort((a, b) => PHASE_ORDER(a.phase, b.phase));
    const kinds = (W.kinds || []).sort((a, b) => b.n - a.n);
    const totW = kinds.reduce((s, k) => s + k.n, 0);
    const bl = kinds.filter((k) => k.wkt_kind === 'bowled' || k.wkt_kind === 'lbw').reduce((s, k) => s + k.n, 0);
    const mp = ph.find((r) => r.phase === W.most_wkts_phase);
    h += `<h2>Bowling</h2><div class="cards">
      ${card('Innings', W.inns)}${card('Wickets', W.wkts)}${card('Economy', f2(W.econ))}${card('Average', f1(W.avg))}${card('Strike rate', f1(W.sr))}${card('Best', W.best)}
      ${card('4+ wkt hauls', W.four_plus)}${card('Dot %', f1(W.dots / W.balls * 100))}</div>
      <div class="callout">Takes most wickets in the <b>${esc(W.most_wkts_phase || '–')}</b> phase${mp && W.wkts ? ` (${mp.wkts} of ${W.wkts})` : ''}. ${totW ? `<b>${Math.round(bl / totW * 100)}%</b> of his wickets are bowled or LBW.` : ''}</div>
      <div class="grid2">
        ${box('Wickets and economy by year', canv('c-wyr'))}
        ${box('Phase by phase', canv('c-wph'), 'Bars: wickets. Line: economy.')}
        ${box('How he takes wickets', canv('c-wk'))}
        ${box('Against right and left-handers', table([{ h: 'Batter', k: 'bat_hand', l: 1 }, { h: 'Balls', k: 'balls' }, { h: 'Wkts', k: 'wkts' }, { h: 'Econ', f: (r) => f2(r.runs / r.balls * 6) }, { h: 'Average', f: (r) => f1(r.wkts ? r.runs / r.wkts : null) }, { h: 'Balls/wkt', f: (r) => f1(r.wkts ? r.balls / r.wkts : null) }], W.vs_hand || []) + `<h3 style="margin-top:16px">Favourite victims</h3>` + table([{ h: 'Batter', l: 1, html: (r) => plink(r.name, r.player_out_id) }, { h: 'Times out', k: 'n' }], W.victims || []))}
      </div>
      <h2>Last 15 bowling innings</h2>${box('', table([{ h: 'Date', f: (r) => dt(r.date), l: 1 }, { h: 'Opponent', k: 'opp', l: 1 }, { h: 'Ground', k: 'venue', l: 1 }, { h: 'Overs', k: 'overs' }, { h: 'Figures', html: (r) => mlink(r.fig, r.id) }], W.last))}`;
    setTimeout(() => {
      const yr = W.by_year || [];
      chart($('#c-wyr'), { type: 'bar', data: { labels: yr.map((r) => r.yr), datasets: [{ label: 'Wickets', data: yr.map((r) => r.wkts), backgroundColor: css('--accent'), yAxisID: 'y' }, { type: 'line', label: 'Economy', data: yr.map((r) => r.econ), borderColor: css('--accent2'), backgroundColor: css('--accent2'), yAxisID: 'y1' }] }, options: { scales: { y: { beginAtZero: true }, y1: { position: 'right', grid: { display: false } } } } });
      chart($('#c-wph'), { type: 'bar', data: { labels: ph.map((r) => r.phase), datasets: [{ label: 'Wickets', data: ph.map((r) => r.wkts), backgroundColor: css('--accent'), yAxisID: 'y' }, { type: 'line', label: 'Economy', data: ph.map((r) => r.balls ? r.runs / r.balls * 6 : null), borderColor: css('--accent2'), backgroundColor: css('--accent2'), yAxisID: 'y1' }] }, options: { scales: { y: { beginAtZero: true }, y1: { position: 'right', beginAtZero: true, grid: { display: false } } } } });
      chart($('#c-wk'), { type: 'doughnut', data: { labels: kinds.map((k) => k.wkt_kind), datasets: [{ data: kinds.map((k) => k.n), backgroundColor: ['#0f6b4f', '#c2410c', '#2563eb', '#7c3aed', '#ca8a04', '#64748b'] }] }, options: { plugins: { legend: { position: 'right' } } } });
    });
  }
  $('#body').innerHTML = h || '<p class="sub">No batting or bowling recorded in this format.</p>';
}

/* ----- ground ----- */
async function ground(id, fmt, per) {
  const G = await getJSON(`g/${id}.json`);
  const fmts = Object.keys(G.formats);
  fmt = fmts.includes(fmt) ? fmt : pickFormat(G.formats, (x) => x.matches);
  const F = G.formats[fmt];
  const pers = ['Last 5 years', 'Last 10 years', 'All years'].filter((p) => F.periods[p]);
  per = pers.includes(per) ? per : pers[0];
  const P = F.periods[per], S = P.summary;
  const test = fmt === 'Test';
  app.innerHTML = `<h1>${esc(G.name)}</h1><p class="sub">${esc(G.city || '')} · ${F.matches} ${fmt} matches, ${dt(F.first)} to ${dt(F.last)}</p><div id="ft"></div>
    <div class="seg" id="per">${pers.map((p) => `<button class="${p === per ? 'on' : ''}" data-p="${esc(p)}">${esc(p)}</button>`).join('')}</div><div id="body"></div>`;
  $('#ft').appendChild(formatTabs(fmts, fmt, (f) => { location.hash = `#/g/${id}/${f}`; }));
  app.querySelectorAll('#per button').forEach((b) => (b.onclick = () => { location.hash = `#/g/${id}/${fmt}/${encodeURIComponent(b.dataset.p)}`; }));
  const mw = P.most_wkts_phase;
  const bt = (P.btypes || []).slice().sort((a, b) => b.Wickets - a.Wickets);
  const phases = (P.phases || []).slice().sort((a, b) => a.Innings - b.Innings || PHASE_ORDER(a.Phase, b.Phase));
  let h = `<div class="cards" style="margin-top:14px">
    ${card('Matches', S.Matches)}
    ${test ? card('Avg 1st inns', f1(S['Avg 1 inns'])) + card('Avg 2nd inns', f1(S['Avg 2 inns'])) + card('Avg 3rd inns', f1(S['Avg 3 inns'])) + card('Avg 4th inns', f1(S['Avg 4 inns'])) : card('Avg 1st inns', f1(S['Avg 1st inns'])) + card('Avg 2nd inns', f1(S['Avg 2nd inns'])) + card('Highest', S.Highest) + card('Highest chase', S['Highest chase'] ?? '–')}
    ${card('Bat 1st win %', f1(S['Bat 1st win %']))}${card(test ? 'Bat 2nd win %' : 'Chase win %', f1(test ? S['Bat 2nd win %'] : S['Chase win %']))}${test ? card('Draw %', f1(S['Draw %'])) : ''}
    ${card('Toss winner wins %', f1(S['Toss winner wins %']))}${card('Pace wkts %', f1(S['Pace wkt %']))}${card('Spin wkts %', f1(S['Spin wkt %']))}
    ${card('Pace economy', f2(S['Pace econ']))}${card('Spin economy', f2(S['Spin econ']))}
    ${card('Best bowler type', S['Best bowler type'] || '–', 'wide')}${card('Pitch read', S['Pitch read'] || '–', 'wide')}</div>
    ${mw ? `<div class="callout">Most wickets fall in the <b>${esc(mw.phase)}</b> phase (${f1(mw.share)}% of all wickets here). ${Object.entries(mw.by_innings || {}).map(([i, p]) => `Innings ${i}: <b>${esc(p)}</b>`).join(' · ')}</div>` : ''}
    <div class="grid2">
      ${box('Average 1st and 2nd innings score by year', canv('c-yr'))}
      ${box('Who takes the wickets', canv('c-bt'), 'Share of bowler wickets by bowling type. Green = pace, purple = spin.')}
      ${box('Runs and wickets by phase', canv('c-ph'), 'Average per innings in each phase.')}
      ${box('Batting first win % by year', canv('c-bf'))}
    </div>
    <h2>Phase by phase</h2>${box('', table([{ h: 'Inns', k: 'Innings' }, { h: 'Phase', k: 'Phase', l: 1 }, { h: 'Sample', k: 'Innings sampled' }, { h: 'Avg runs', f: (r) => f1(r['Avg runs in phase']) }, { h: 'Run rate', f: (r) => f2(r['Run rate']) }, { h: 'Avg wkts', f: (r) => f2(r['Avg wkts in phase']) }, { h: 'Dot %', f: (r) => f1(r['Dot %']) }, { h: 'Boundary %', f: (r) => f1(r['Boundary %']) }, { h: 'Sixes', f: (r) => f2(r['Sixes per inns']) }, { h: 'Pace wkts', k: 'Pace wkts' }, { h: 'Spin wkts', k: 'Spin wkts' }], phases, { hl: (r) => mw && r.Phase === mw.phase }))}
    <h2>Bowler types here</h2>${box('', table([{ h: 'Type', k: 'Bowler type', l: 1 }, { h: 'Wkts', k: 'Wickets' }, { h: 'Share %', f: (r) => f1(r['Share of wkts %']) }, { h: 'Balls/wkt', f: (r) => f1(r['Strike rate']) }, { h: 'Econ', f: (r) => f2(r.Economy) }, { h: 'Avg', f: (r) => f1(r.Average) }, { h: 'Bowled', k: 'Bowled' }, { h: 'LBW', k: 'LBW' }, { h: 'Caught', k: 'Caught' }, { h: 'Stumped', k: 'Stumped' }], bt), 'Lots of bowled and LBW means straight, full bowling works here; stumpings mean flight and turn.')}
    <div class="grid2" style="margin-top:16px">
      ${box('Top run scorers here (last 5 years)', table([{ h: 'Batter', l: 1, html: (r) => plink(r.name, r.batter_id) }, { h: 'Inns', k: 'inns' }, { h: 'Runs', k: 'runs' }, { h: 'Avg', f: (r) => f1(r.outs ? r.runs / r.outs : null) }, { h: 'SR', f: (r) => f1(r.runs / r.balls * 100) }], F.top_bat))}
      ${box('Top wicket takers here (last 5 years)', table([{ h: 'Bowler', l: 1, html: (r) => plink(r.name, r.bowler_id) }, { h: 'Wkts', k: 'wkts' }, { h: 'Econ', f: (r) => f2(r.runs / r.balls * 6) }, { h: 'Avg', f: (r) => f1(r.wkts ? r.runs / r.wkts : null) }], F.top_bowl))}
    </div>
    <h2>Recent matches here</h2>${box('', `<div class="list">${F.recent.map((r) => `<a class="row" href="#/m/${esc(r.id)}"><span><b>${esc(r.t)}</b> · ${dt(r.date)}</span><span class="sub">${esc(r.s)}${r.w ? ` · ${esc(r.w)} won` : ''}</span></a>`).join('')}</div>`)}`;
  $('#body').innerHTML = h;
  const yr = F.by_year || [];
  chart($('#c-yr'), { type: 'line', data: { labels: yr.map((r) => r.year), datasets: [{ label: '1st innings', data: yr.map((r) => r.avg1), borderColor: '#0f6b4f', backgroundColor: '#0f6b4f' }, { label: '2nd innings', data: yr.map((r) => r.avg2), borderColor: '#c2410c', backgroundColor: '#c2410c' }] } });
  chart($('#c-bf'), { type: 'bar', data: { labels: yr.map((r) => r.year), datasets: [{ label: 'Bat 1st win %', data: yr.map((r) => r.bat1_win_pct), backgroundColor: '#2563eb' }] }, options: { scales: { y: { min: 0, max: 100 } } } });
  chart($('#c-bt'), { type: 'bar', data: { labels: bt.map((r) => r['Bowler type']), datasets: [{ label: 'Share of wickets %', data: bt.map((r) => r['Share of wkts %']), backgroundColor: bt.map((r) => (r['Pace/Spin'] === 'Spin' ? '#7c3aed' : '#0f6b4f')) }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
  const labels = [...new Set(phases.map((r) => `Inns ${r.Innings} ${r.Phase.split(' (')[0]}`))];
  chart($('#c-ph'), { type: 'bar', data: { labels, datasets: [{ label: 'Avg runs', data: phases.map((r) => r['Avg runs in phase']), backgroundColor: '#0f6b4f', yAxisID: 'y' }, { type: 'line', label: 'Avg wickets', data: phases.map((r) => r['Avg wkts in phase']), borderColor: '#c2410c', backgroundColor: '#c2410c', yAxisID: 'y1' }] }, options: { scales: { y: { beginAtZero: true }, y1: { position: 'right', beginAtZero: true, grid: { display: false } } } } });
}

/* ----- team ----- */
async function team(id, fmt) {
  const T = await getJSON(`t/${id}.json`);
  const fmts = Object.keys(T.formats);
  fmt = fmts.includes(fmt) ? fmt : pickFormat(T.formats, (x) => x.played);
  const F = T.formats[fmt];
  app.innerHTML = `<h1>${esc(T.name)}</h1><p class="sub">${F.played} ${fmt} matches</p><div id="ft"></div><div id="body"></div>`;
  $('#ft').appendChild(formatTabs(fmts, fmt, (f) => { location.hash = `#/t/${id}/${f}`; }));
  const pct = (w, p) => (p ? f1(w / p * 100) + '%' : '–');
  $('#body').innerHTML = `<div class="cards">${card('Played', F.played)}${card('Won', F.won)}${card('Lost', F.lost)}${card('Win %', pct(F.won, F.played))}
    ${card('Win % batting 1st', pct(F.bat_first.w, F.bat_first.p))}${card('Win % batting 2nd', pct(F.bat_second.w, F.bat_second.p))}</div>
    <div class="grid2" style="margin-top:16px">
      ${box('Wins and losses by year', canv('c-yr'))}
      ${box('Head to head', table([{ h: 'Opponent', k: 'opp', l: 1 }, { h: 'P', k: 'played' }, { h: 'W', k: 'won' }, { h: 'L', k: 'lost' }, { h: 'Win %', f: (r) => pct(r.won, r.played) }], F.h2h))}
      ${box('Top run scorers (last 2 years)', table([{ h: 'Batter', l: 1, html: (r) => plink(r.name, r.batter_id) }, { h: 'Inns', k: 'inns' }, { h: 'Runs', k: 'runs' }, { h: 'Avg', f: (r) => f1(r.outs ? r.runs / r.outs : null) }, { h: 'SR', f: (r) => f1(r.runs / r.balls * 100) }], F.top_bat))}
      ${box('Top wicket takers (last 2 years)', table([{ h: 'Bowler', l: 1, html: (r) => plink(r.name, r.bowler_id) }, { h: 'Wkts', k: 'wkts' }, { h: 'Econ', f: (r) => f2(r.runs / r.balls * 6) }, { h: 'Avg', f: (r) => f1(r.wkts ? r.runs / r.wkts : null) }], F.top_bowl))}
    </div>
    <h2>Record at grounds (last 10 years)</h2>${box('', table([{ h: 'Ground', l: 1, html: (r) => `<a href="#/g/${esc(slugify(r.Venue))}/${fmt}">${esc(r.Venue)}</a>` }, { h: 'Played', k: 'Played' }, { h: 'Won', k: 'Won' }, { h: 'Win %', f: (r) => f1(r['Win %']) }, { h: 'Bat 1st P/W', f: (r) => `${r['Batting 1st P']}/${r['Batting 1st W']}` }, { h: 'Bat 2nd P/W', f: (r) => `${r['Batting 2nd P']}/${r['Batting 2nd W']}` }], F.grounds))}
    <h2>Recent matches</h2>${box('', table([{ h: 'Date', l: 1, html: (r) => mlink(dt(r.date), r.id) }, { h: 'Opponent', k: 'opp', l: 1 }, { h: 'Ground', k: 'venue', l: 1 }, { h: 'Result', html: (r) => resPill(r.res) }], F.recent))}`;
  const yr = F.by_year || [];
  chart($('#c-yr'), { type: 'bar', data: { labels: yr.map((r) => r.year), datasets: [{ label: 'Won', data: yr.map((r) => r.won), backgroundColor: '#16a34a' }, { label: 'Lost', data: yr.map((r) => r.lost), backgroundColor: '#dc2626' }] }, options: { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } } });
}
const slugify = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/* ----- match ----- */
async function match(id) {
  const M = await getJSON(`m/${id}.json`);
  const result = M.winner ? `${M.winner} won${M.by_runs ? ` by ${M.by_runs} runs` : M.by_wkts ? ` by ${M.by_wkts} wickets` : ''}${M.method ? ` (${M.method})` : ''}` : (M.result || 'No result');
  const ov = (b) => `${Math.floor(b / 6)}.${b % 6}`;
  let h = `<h1>${esc(M.team1)} vs ${esc(M.team2)}</h1>
    <p class="sub">${esc([M.fmt, M.event, M.stage].filter(Boolean).join(' · '))} · ${dt(M.date)} · <a href="#/g/${esc(M.gid)}/${M.fmt}">${esc(M.venue)}</a></p>
    <div class="result-line">${esc(result)}</div>
    <p class="sub">${esc(M.toss || '')}${M.pom ? ` · Player of the match: <b>${esc(M.pom)}</b>` : ''}</p>
    <div class="cards">${M.innings.map((i) => card(`${i.team} (inns ${i.n})`, `${i.runs}/${i.wkts}`)).join('')}</div>
    <div class="grid2" style="margin-top:16px">
      ${box('Top batters', table([{ h: 'Batter', l: 1, html: (r) => plink(r.batter, r.batter_id) }, { h: 'Team', k: 'team', l: 1 }, { h: 'R', k: 'runs' }, { h: 'B', k: 'balls' }, { h: '4s', k: 'fours' }, { h: '6s', k: 'sixes' }, { h: 'SR', f: (r) => f1(r.sr) }], M.top_bat))}
      ${box('Top bowlers', table([{ h: 'Bowler', l: 1, html: (r) => plink(r.bowler, r.bowler_id) }, { h: 'Team', k: 'team', l: 1 }, { h: 'O', k: 'overs' }, { h: 'R', k: 'runs' }, { h: 'W', k: 'wkts' }, { h: 'Econ', f: (r) => f2(r.econ) }], M.top_bowl))}
    </div>
    ${M.fmt !== 'Test' ? `<div class="grid2" style="margin-top:16px">${box('Worm: runs as the innings went', canv('c-worm'))}${box('Runs per over (dots mark wickets)', canv('c-man'))}</div>` : `<div style="margin-top:16px">${box('Runs per over by innings', canv('c-man'))}</div>`}`;
  M.innings.forEach((i) => {
    h += `<h2 class="innhead"><span>${esc(i.team)}, innings ${i.n}</span><span class="score">${i.runs}/${i.wkts} <span class="sub" style="font-size:14px">(${ov(i.balls)} ov, extras ${i.extras})</span></span></h2>
      <div class="grid2">
        ${box('Batting', table([{ h: 'Batter', l: 1, html: (r) => plink(r.batter, r.batter_id) }, { h: '', k: 'how', cls: 'how' }, { h: 'R', k: 'runs' }, { h: 'B', k: 'balls' }, { h: '4s', k: 'fours' }, { h: '6s', k: 'sixes' }, { h: 'SR', f: (r) => f1(r.balls ? r.runs / r.balls * 100 : null) }], i.bat))}
        ${box('Bowling', table([{ h: 'Bowler', l: 1, html: (r) => plink(r.bowler, r.bowler_id) }, { h: 'O', k: 'overs' }, { h: 'M', k: 'maidens' }, { h: 'R', k: 'runs' }, { h: 'W', k: 'wkts' }, { h: 'Econ', f: (r) => f2(r.econ) }, { h: 'Dots', k: 'dots' }], i.bowl))}
        ${box('Phase by phase', table([{ h: 'Phase', k: 'phase', l: 1 }, { h: 'Runs', k: 'runs' }, { h: 'Wkts', k: 'wkts' }, { h: 'Run rate', f: (r) => f2(r.balls ? r.runs / r.balls * 6 : null) }, { h: 'Dots', k: 'dots' }, { h: '4s', k: 'fours' }, { h: '6s', k: 'sixes' }], i.phases.sort((a, b) => PHASE_ORDER(a.phase, b.phase))))}
        ${box('Fall of wickets', table([{ h: 'Wkt', k: 'wn' }, { h: 'Score', k: 'score' }, { h: 'Over', k: 'ballno' }, { h: 'Batter', k: 'player_out', l: 1 }, { h: 'How', k: 'wkt_kind', l: 1 }, { h: 'Bowler', k: 'bowler', l: 1 }], i.fow))}
      </div>`;
  });
  app.innerHTML = h;
  const cols = ['#0f6b4f', '#c2410c', '#2563eb', '#7c3aed'];
  const maxOv = Math.max(...M.innings.map((i) => (i.overs.length ? i.overs[i.overs.length - 1].over : 0)));
  const labels = Array.from({ length: maxOv }, (_, k) => k + 1);
  if ($('#c-worm')) chart($('#c-worm'), { type: 'line', data: { labels, datasets: M.innings.map((i, k) => ({ label: i.team, data: labels.map((o) => (i.overs.find((x) => x.over === o) || {}).cum ?? null), borderColor: cols[k], backgroundColor: cols[k], pointRadius: labels.map((o) => ((i.overs.find((x) => x.over === o) || {}).wkts ? 4 : 0)), spanGaps: false })) } });
  chart($('#c-man'), { type: 'bar', data: { labels, datasets: M.innings.map((i, k) => ({ label: `${i.team} (inns ${i.n})`, data: labels.map((o) => (i.overs.find((x) => x.over === o) || {}).runs ?? null), backgroundColor: cols[k] })).concat(M.innings.map((i, k) => ({ type: 'scatter', label: `${i.team} wickets`, data: i.overs.filter((x) => x.wkts).map((x) => ({ x: x.over - 1, y: x.runs + 1 })), backgroundColor: '#111', pointRadius: 4, showLine: false }))) }, options: { plugins: { legend: { labels: { filter: (l) => !/wickets$/.test(l.text) } } } } });
}

/* ---------------- router ---------------- */
async function route() {
  charts.splice(0).forEach((c) => c.destroy());
  const [, type, id, a, b] = decodeURIComponent(location.hash || '#/').split('/');
  window.scrollTo(0, 0);
  try {
    if (type === 'p') await player(id, a);
    else if (type === 'g') await ground(id, a, b);
    else if (type === 't') await team(id, a);
    else if (type === 'm') await match(id);
    else await home();
    document.title = ($('h1')?.textContent || 'Cricket Insights') + ' · Cricket Insights';
  } catch (e) {
    console.error(e);
    app.innerHTML = `<p class="sub">Couldn't load that page. Try searching again.</p>`;
  }
}
window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', async () => {
  setupSearch();
  route();
  try { const m = await getJSON('meta.json'); $('#built').textContent = `Updated ${m.built}`; } catch (e) { /* first load */ }
});
