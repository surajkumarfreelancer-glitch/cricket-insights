"""Turn raw Wikipedia bowling/batting strings into clean bowler types."""
import json, re
import pandas as pd

def bowl_type(s):
    s0 = (s or '').lower()
    s0 = re.sub(r'[\[\]#]', ' ', s0)
    if not s0.strip():
        return None, None
    left = 'left' in s0 and not re.search(r'right[- ]arm', s0.split('left')[0])
    # first listed style is the main one
    first = re.split(r',|/|<br|;| and |\bor\b', s0)[0]
    t = first if len(first) > 3 else s0
    arm = 'Left-arm' if 'left' in t else 'Right-arm'
    if any(k in t for k in ['wrist', 'chinaman', 'unorthodox']):
        return 'Spin', 'Left-arm wrist spin'
    if any(k in t for k in ['leg spin', 'leg-spin', 'legbreak', 'leg break', 'leg-break', 'googly']):
        return 'Spin', ('Left-arm wrist spin' if arm == 'Left-arm' else 'Leg spin')
    if any(k in t for k in ['off spin', 'off-spin', 'offbreak', 'off break', 'off-break']):
        return 'Spin', ('Left-arm orthodox' if arm == 'Left-arm' and 'off' not in t else 'Off spin')
    if 'orthodox' in t or ('slow' in t and 'left' in t and 'medium' not in t):
        return 'Spin', 'Left-arm orthodox'
    if 'spin' in t:
        return 'Spin', ('Left-arm orthodox' if arm == 'Left-arm' else 'Off spin')
    if 'fast' in t or 'medium' in t or 'seam' in t or 'swing' in t:
        if 'fast' in t and 'medium' not in t:
            speed = 'fast'
        elif 'fast' in t:
            speed = 'fast-medium' if t.find('fast') < t.find('medium') else 'medium-fast'
        else:
            speed = 'medium'
        return 'Pace', f'{arm} {speed}'
    return None, None

def bat_hand(s):
    s = (s or '').lower()
    return 'Left-hand bat' if 'left' in s else ('Right-hand bat' if 'right' in s else None)

if __name__ == '__main__':
    raw = json.load(open('wiki_styles.json', encoding='utf-8'))
    p = pd.read_csv('people.csv', dtype=str)
    rows = []
    for _, r in p.iterrows():
        k = r.key_cricinfo
        if pd.isna(k) or k not in raw:
            continue
        b, h = raw[k]
        g, t = bowl_type(b)
        rows.append(dict(player_id=r.identifier, name=r['name'], bowl_raw=b, bowl_group=g, bowl_type=t, bat_hand=bat_hand(h)))
    df = pd.DataFrame(rows)
    # hand fixes for well-known bowlers whose Wikipedia field lists several styles in a template
    FIX = {'A Symonds': ('Spin', 'Off spin'), 'SR Tendulkar': ('Spin', 'Leg spin'), 'LS Livingstone': ('Spin', 'Leg spin'),
           'DS Rathi': ('Spin', 'Leg spin'), 'V Nigam': ('Spin', 'Leg spin'), 'P Awana': ('Pace', 'Right-arm medium-fast'),
           'Mohammad Irfan': ('Pace', 'Left-arm fast'), 'Mohammad Ashraful': ('Spin', 'Leg spin')}
    for n, (g, t) in FIX.items():
        mask = df.name == n
        df.loc[mask, 'bowl_group'] = g; df.loc[mask, 'bowl_type'] = t
    df.to_csv('player_styles.csv', index=False)
    print(len(df), df.bowl_type.value_counts(dropna=False).to_string())
