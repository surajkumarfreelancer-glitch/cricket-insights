"""Refresh bowling/batting styles and full names for every player with a Cricinfo ID on Wikidata.
Writes wiki_styles.json ({cricinfo_id: [bowling, batting]}) and wiki_titles.json ({cricinfo_id: article title})."""
import json, re, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'CricketInsights/1.0 (https://github.com/surajkumarfreelancer-glitch/cricket-insights)'}

def get(url, tries=4):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(3 * (t + 1))
    return None

def clean(s):
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'<[^>]*>', ' ', s); s = re.sub(r'\{\{[^}]*\}\}', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def field(c, k):
    x = re.search(r'\n\s*\|\s*' + k + r'\s*=([^\n]*)', c, re.I)
    return clean(x.group(1)) if x else ''

def main():
    q = 'SELECT ?id ?article WHERE { ?p wdt:P2697 ?id . ?article schema:about ?p; schema:isPartOf <https://en.wikipedia.org/>. }'
    rows = get('https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(q))['results']['bindings']
    by_title = {urllib.parse.unquote(r['article']['value'].split('/wiki/')[1]).replace('_', ' '): r['id']['value'] for r in rows}
    json.dump({v: k for k, v in by_title.items()}, open('wiki_titles.json', 'w', encoding='utf-8'))
    titles = list(by_title)
    batches = [titles[i:i + 50] for i in range(0, len(titles), 50)]
    res = {}

    def run(b):
        u = ('https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&format=json'
             '&formatversion=2&redirects=1&titles=' + urllib.parse.quote('|'.join(b)))
        j = get(u)
        if not j:
            return {}
        j = j['query']; out = {}
        m = {n['to']: n['from'] for n in j.get('normalized', [])}
        for n in j.get('redirects', []):
            m[n['to']] = m.get(n['from'], n['from'])
        for p in j.get('pages', []):
            cid = by_title.get(m.get(p['title'], p['title']))
            if cid and 'revisions' in p:
                c = p['revisions'][0]['slots']['main']['content']
                out[cid] = [field(c, 'bowling'), field(c, 'batting')]
        return out

    with ThreadPoolExecutor(6) as ex:
        for i, out in enumerate(ex.map(run, batches)):
            res.update(out)
    old = json.load(open('wiki_styles.json', encoding='utf-8'))
    old.update(res)
    json.dump(old, open('wiki_styles.json', 'w', encoding='utf-8'))
    print('styles', len(res), 'total', len(old))

if __name__ == '__main__':
    main()
