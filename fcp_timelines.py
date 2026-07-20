#!/usr/bin/env python3
"""
Extracteur de timelines FCP 1-7 'KeyG' — version finale.

- Big-endian (PowerPC) ET little-endian (Intel), détection automatique.
- Les ids de propriétés numériques sont DYNAMIQUES par fichier (ce sont des
  références vers les noms de clés internés). Découverte par rôle :
    master-id  = id portant le plus de GUIDs (type 0x23) inline
    name-id    = id 0x1f le plus fréquent ET le plus proche des masters
    track-id   = id conteneur-réf (type 0, '01 00') le plus proche APRÈS masters
    seq-id     = id int ver-00 suivant un record-nom de près
- Clipitem : doubles ver-01 = début/fin timeline (+durée média),
             doubles ver-02 = in/out source. Attribution clip→séquence par
             flux (dernier en-tête), cohérence couverture/durée signalée.

Usage: fcp_timelines.py projet.fcp [--seq FILTRE] [--csv F] [--json F] [--all]
"""
import re, struct, sys, json, csv, collections, bisect

GUID_RE = re.compile(rb'[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}')

def decode_str(b):
    for enc in ('utf-8', 'mac-roman'):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode('latin1', 'replace')

def tc(frames, fps=25):
    if frames is None: return '--:--:--:--'
    f = int(round(frames)); s = '-' if f < 0 else ''; f = abs(f)
    return f"{s}{f//(3600*fps):02d}:{f//(60*fps)%60:02d}:{f//fps%60:02d}:{f%fps:02d}"

class F:
    """Fabrique de motifs pour une endianness donnée."""
    def __init__(self, e):
        self.e = e
    def kb(self, kid):
        """clé numérique complète : [00][u32 id]"""
        return b'\x00' + struct.pack(self.e + 'I', kid)
    def tb(self, t):
        return struct.pack(self.e + 'I', t)
    def u32(self, d, o): return struct.unpack_from(self.e + 'I', d, o)[0]
    def i32(self, d, o): return struct.unpack_from(self.e + 'i', d, o)[0]
    def f64(self, d, o): return struct.unpack_from(self.e + 'd', d, o)[0]
    def numkey_re(self, type_bytes):
        """regex lookahead : [00][u32 id] + type, capture id 16 bits utiles."""
        if self.e == '>':
            return re.compile(rb'(?=\x00\x00\x00(..)' + type_bytes + rb')', re.S)
        return re.compile(rb'(?=\x00(..)\x00\x00' + type_bytes + rb')', re.S)
    def kid(self, m):
        return struct.unpack(self.e + 'H', m.group(1))[0]

def detect_endian(data):
    assert data[:8] == b'\xa2KeyG\n\r\n', "pas un projet FCP (magic KeyG absent)"
    be = len(re.findall(rb'\x08duration\x00\x00\x00\x04', data[:2**22]))
    le = len(re.findall(rb'\x08duration\x04\x00\x00\x00', data[:2**22]))
    if not be and not le:
        be = len(re.findall(rb'\x00\x00\x00\x1f\x01\x01', data[:2**22]))
        le = len(re.findall(rb'\x1f\x00\x00\x00\x01\x01', data[:2**22]))
    return '>' if be >= le else '<'

def discover(data, f):
    """Découvre les ids de rôle du fichier."""
    # masters : GUID inline
    g_ctr = collections.Counter(); g_pos = collections.defaultdict(list)
    pat = f.numkey_re(f.tb(0x23))
    for m in pat.finditer(data):
        if GUID_RE.search(data, m.start()+9, m.start()+70):
            kid = f.kid(m)
            g_ctr[kid] += 1
            g_pos[kid].append(m.start())
    if not g_ctr: raise SystemExit("aucun GUID master trouvé")
    MASTER = g_ctr.most_common(1)[0][0]
    mpos = sorted(g_pos[MASTER])

    def proximity(positions, before=0, after=1500):
        s = 0
        for p in positions[:4000]:
            i = bisect.bisect_left(mpos, p - before)
            if i < len(mpos) and -before <= mpos[i] - p <= after:
                s += 1
        return s

    # noms : chaînes 0x1f inline, fréquence * proximité aux masters
    s_pos = collections.defaultdict(list)
    pat = f.numkey_re(f.tb(0x1f) + (b'\x01\x01' if f.e == '>' else b'\x01\x01'))
    for m in pat.finditer(data):
        s_pos[f.kid(m)].append(m.start())
    best = None
    for kid, pos in s_pos.items():
        if len(pos) < 5: continue
        sc = len(pos) * (1 + proximity(pos, before=0, after=1500))
        if best is None or sc > best[1]: best = (kid, sc)
    NAME = best[0]

    # trackref : conteneur-réf '01 00' juste APRÈS un master (dans le clipitem)
    t_pos = collections.defaultdict(list)
    pat = f.numkey_re(f.tb(0) + b'\x01\x00')
    for m in pat.finditer(data):
        t_pos[f.kid(m)].append(m.start())
    best = None
    nmast = len(mpos)
    for kid, pos in t_pos.items():
        # le vrai id piste apparaît ~1 fois par clip : volume comparable aux masters
        if not (0.15 * nmast <= len(pos) <= 1.5 * nmast): continue
        frac = proximity(pos, before=1500, after=0) / min(len(pos), 4000)
        if best is None or frac > best[1]: best = (kid, frac)
    TRACK = best[0] if best and best[1] > 0.3 else None

    # marqueur séquence : int ver-00 proche après un nom.
    # score = votes² / fréquence globale (écarte les ids « bruit » très fréquents)
    npos = sorted(s_pos[NAME])
    q_ctr = collections.Counter()
    g_all = collections.Counter()
    pat = f.numkey_re(f.tb(1) + b'\x00')
    for m in pat.finditer(data):
        kid = f.kid(m)
        g_all[kid] += 1
        i = bisect.bisect_left(npos, m.start() - 80)
        if i < len(npos) and 0 < m.start() - npos[i] < 80:
            q_ctr[kid] += 1
    SEQ = max(q_ctr, key=lambda k: q_ctr[k]**2 / g_all[k]) if q_ctr else None

    # ids temporels du clipitem : ancrage sur les paires de doubles ver-02
    # (in/out source), apprentissage par vote des ids voisins
    d1 = []   # (off, id) doubles ver 01
    d2 = []   # (off, id) doubles ver 02
    for m in f.numkey_re(f.tb(4) + b'\x01').finditer(data):
        d1.append((m.start(), f.kid(m)))
    for m in f.numkey_re(f.tb(4) + b'\x02').finditer(data):
        d2.append((m.start(), f.kid(m)))
    d1.sort(); d2.sort()
    d1pos = [x[0] for x in d1]
    votes = collections.Counter()
    for (o1, i1), (o2, i2) in zip(d2, d2[1:]):
        if 0 < o2 - o1 < 120:                      # paire src in/out
            j = bisect.bisect_left(d1pos, o1)
            prev = d1[max(0, j-2):j]               # 2 ver-01 avant = start, end
            k = bisect.bisect_right(d1pos, o2)
            nxt = d1[k:k+1]                        # 1 ver-01 après = durée média
            if len(prev) == 2 and nxt:
                votes[(prev[0][1], prev[1][1], i1, i2, nxt[0][1])] += 1
    roles = votes.most_common(1)[0][0] if votes else None
    return {'master': MASTER, 'name': NAME, 'track': TRACK, 'seq': SEQ,
            'roles': roles}

def scan_events(data, f, ids):
    ev = []
    # noms inline
    kb = f.kb(ids['name']); tb = f.tb(0x1f)
    for m in re.finditer(re.escape(kb + tb + b'\x01\x01'), data):
        ln = f.u32(data, m.end())
        if 0 < ln <= 300:
            txt = data[m.end()+4:m.end()+4+ln]
            if len(txt) == ln:
                ev.append((m.start(), 'name', decode_str(txt)))
    # noms par référence
    for m in re.finditer(re.escape(kb + tb + b'\x01\x00'), data):
        ev.append((m.start(), 'nameref', f.u32(data, m.end())))
    # marqueur séquence (int ver 00)
    if ids['seq'] is not None:
        kb = f.kb(ids['seq'])
        for m in re.finditer(re.escape(kb + f.tb(1) + b'\x00'), data):
            ev.append((m.start(), 'seqmark', f.i32(data, m.end())))
    # doubles temporels avec les ids appris (start, end, src_in, src_out, dur)
    if ids.get('roles'):
        START, END, SIN, SOUT, DUR = ids['roles']
        for kid, tag, ver in ((START, 'start', 1), (END, 'end', 1),
                              (SIN, 'src_in', 2), (SOUT, 'src_out', 2),
                              (DUR, 'mdur', 1)):
            kb2 = f.kb(kid)
            for m in re.finditer(re.escape(kb2 + f.tb(4) + bytes([ver])), data):
                try: v = f.f64(data, m.end())
                except struct.error: continue
                ev.append((m.start(), tag, v))
    # masters GUID : inline OU référence ([01 00] / [00 00] + u32)
    kb = f.kb(ids['master'])
    for m in re.finditer(re.escape(kb + f.tb(0x23)), data):
        fl = data[m.end():m.end()+2]
        if fl in (b'\x01\x00', b'\x00\x00'):
            ev.append((m.start(), 'masterref', f.u32(data, m.end()+2)))
        else:
            g = GUID_RE.search(data, m.end(), m.end()+50)
            if g: ev.append((m.start(), 'master', g.group().decode()))
    # trackrefs
    if ids['track'] is not None:
        kb = f.kb(ids['track'])
        for m in re.finditer(re.escape(kb + f.tb(0) + b'\x01\x00'), data):
            ev.append((m.start(), 'trackref', f.u32(data, m.end())))
    ev.sort(key=lambda e: e[0])
    return ev

def item_table_resolver(data, f, names):
    """Résolution des réfs d'ids persistants via la table CProjectItemTableEntry.

    Chaque entrée fine (v1,v2) marque le début de la plage d'ids d'un item ;
    l'item possède [v1_i, v1_suivant). Les annotations '...18 [00][u32 X]'
    dans la fenêtre d'un item ancrent son intervalle → nom. Une réf R se
    résout par l'intervalle qui la contient."""
    fine = set()
    for m in re.finditer(rb'22CProjectItemTableEntry', data):
        off = m.start()
        p = data[off+24:off+24+14]
        if len(p) == 14 and p[4] == 0 and p[9] == 0:
            v1 = struct.unpack(f.e + 'I', p[5:9])[0]
            v2 = struct.unpack(f.e + 'I', p[10:14])[0]
            if 0 < v2 - v1 < 500:
                fine.add(v1)
    fine = sorted(fine)
    if not fine:
        return lambda R: None
    if f.e == '>':
        ANN = re.compile(rb'\x01\x00\x00\x00\x01\x00\x00\x00\x18\x00')
    else:
        ANN = re.compile(rb'\x01\x01\x00\x00\x00\x18\x00\x00\x00\x00')
    def own(x):
        i = bisect.bisect_right(fine, x) - 1
        return i if i >= 0 else None
    votes = collections.defaultdict(collections.Counter)
    nlist = names + [(len(data), '')]
    for (off, name), (noff, _) in zip(nlist, nlist[1:]):
        if re.match(r'(com|net|org)\.[a-z]+\.', name): continue
        w = data[off:min(max(off+1500, noff), len(data)-4)]
        for am in ANN.finditer(w):
            if am.end()+4 > len(w): break
            i = own(f.u32(w, am.end()))
            if i is not None: votes[i][name] += 1
    itv2name = {i: c.most_common(1)[0][0] for i, c in votes.items()}
    return lambda R: itv2name.get(own(R))

def build(data):
    f = F(detect_endian(data))
    ids = discover(data, f)
    ev = scan_events(data, f, ids)

    # GUID -> nom d'élément (masters inline près d'un nom + clé pascal 'master')
    guid2name = {}
    last_name = None
    name_list = []
    for off, k, v in ev:
        if k == 'name':
            last_name = (off, v)
            name_list.append((off, v))
        elif k == 'master' and last_name and off - last_name[0] < 3000 \
                and not re.match(r'(com|net|org)\.[a-z]+\.', last_name[1]):
            guid2name.setdefault(v, last_name[1])
    npos = [x[0] for x in name_list]
    for m in re.finditer(rb'\x06master', data):
        g = GUID_RE.search(data, m.end(), m.end()+70)
        if g:
            i = bisect.bisect_left(npos, m.start())
            if i and m.start() - npos[i-1] < 4000:
                guid2name.setdefault(g.group().decode(), name_list[i-1][1])
    resolve_ref = item_table_resolver(data, f, name_list)

    sequences = []
    cur_seq = None
    cur = None
    pending = None

    def close_clip():
        nonlocal cur
        if cur and cur_seq is not None and 'end' in cur:
            has_link = (cur.get('src_in') is not None or cur.get('master'))
            if has_link and 0 <= cur['start'] < 1e7 and cur['end'] > cur['start']:
                cur_seq['clips'].append({
                    'start': cur['start'], 'end': cur['end'],
                    'src_in': cur.get('src_in'), 'src_out': cur.get('src_out'),
                    'master': cur.get('master'), 'mref': cur.get('mref'),
                    'nref': cur.get('nref'), 'track': cur.get('track')})
        cur = None

    for off, k, v in ev:
        if k == 'name':
            close_clip()
            pending = (off, v)
        elif k == 'seqmark' and pending and 0 < off - pending[0] < 80:
            close_clip()
            cur_seq = {'name': pending[1], 'off': pending[0],
                       'duration': None, 'clips': []}
            sequences.append(cur_seq)
            pending = None
        elif k == 'start':
            close_clip()
            if v >= 0:
                cur = {'start': v, 'off': off}
        elif cur is not None and k in ('end', 'src_in', 'src_out'):
            cur.setdefault(k, v)
        elif k == 'mdur':
            if cur_seq and cur_seq['duration'] is None and not cur_seq['clips'] \
                    and off - cur_seq['off'] < 900 and v and v > 0:
                cur_seq['duration'] = v
        elif k == 'master' and cur is not None:
            cur.setdefault('master', v)
        elif k == 'masterref' and cur is not None:
            cur.setdefault('mref', v)
        elif k == 'nameref' and cur is not None:
            cur.setdefault('nref', v)
        elif k == 'trackref':
            if cur is not None:
                cur['track'] = v
                close_clip()
    close_clip()
    return sequences, guid2name, ids, f.e, resolve_ref

if __name__ == '__main__':
    data = open(sys.argv[1], 'rb').read()
    sequences, guid2name, ids, endian, resolve_ref = build(data)
    print(f"endian={'BE' if endian=='>' else 'LE'}  ids: name={ids['name']:#x} "
          f"master={ids['master']:#x} track={ids['track'] and hex(ids['track'])} seq={ids['seq'] and hex(ids['seq'])}")
    flt = sys.argv[sys.argv.index('--seq')+1].lower() if '--seq' in sys.argv else None
    show_all = '--all' in sys.argv
    rows = []
    for s in sequences:
        clips = s['clips']
        if flt and flt not in s['name'].lower(): continue
        if not flt and not show_all and len(clips) < 6: continue
        cov = max((c['end'] for c in clips), default=0)
        dur = s.get('duration')
        flag = '  [!] attribution partielle ?' if dur and cov > dur * 1.25 else ''
        print(f"\n### {s['name']}  @{s['off']:#x}  durée={tc(dur)}  clips={len(clips)}  couverture={tc(cov)}{flag}")
        tracks = collections.defaultdict(list)
        trefs = [c.get('track') for c in clips if c.get('track') is not None]
        per_clip_ids = len(set(trefs)) > 0.8 * max(len(trefs), 1)
        for c in clips:
            tracks[None if per_clip_ids else c.get('track')].append(c)
        for tref in sorted(tracks, key=lambda x: (x is None, x)):
            tcl = sorted(tracks[tref], key=lambda c: c['start'])
            print(f"  -- piste #{tref} ({len(tcl)} clips)")
            for c in tcl:
                nm = guid2name.get(c.get('master'))
                if not nm and c.get('mref') is not None:
                    nm = resolve_ref(c['mref'])
                if not nm and c.get('nref') is not None:
                    nm = resolve_ref(c['nref'])
                if not nm and isinstance(c.get('master'), str): nm = 'GUID:' + c['master'][:8]
                if not nm: nm = '(transition/générateur)'
                print(f"     {tc(c['start'])} -> {tc(c['end'])}  src[{tc(c.get('src_in'))}..{tc(c.get('src_out'))}]  {nm}")
                rows.append({'sequence': s['name'], 'track': tref,
                             'start_fr': int(c['start']), 'end_fr': int(c['end']),
                             'start_tc': tc(c['start']), 'end_tc': tc(c['end']),
                             'src_in': c.get('src_in'), 'src_out': c.get('src_out'),
                             'clip': nm, 'master_guid': c.get('master')})
    print(f"\n[{len(sequences)} séquences détectées]")
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json')+1]
        json.dump({'sequences': sequences, 'guid2name': guid2name},
                  open(out, 'w'), indent=1, ensure_ascii=False, default=str)
        print("json →", out)
    if '--csv' in sys.argv and rows:
        out = sys.argv[sys.argv.index('--csv')+1]
        w = csv.DictWriter(open(out, 'w', newline=''), fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
        print("csv →", out)
