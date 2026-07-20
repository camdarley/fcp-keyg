#!/usr/bin/env python3
"""
Liste les éléments (clips, séquences, chutiers) d'un projet FCP 1-7 binaire,
avec leurs propriétés numériques.

Chaque élément commence par un enregistrement 'nom' :
  [00][id=0x001d][type=0x1f][01 01][len:u32][texte UTF-8]
suivi d'enregistrements scalaires à clé numérique :
  [00][id:u16][type:u32][ver:u8][valeur]
IDs connus : 0x17=durée (frames), 0x1d=nom, 0x25=qualité de rendu,
             0x2a=largeur, 0x2b=hauteur, 0x1b=base de temps (fps)
"""
import re, struct, sys

PROP_NAMES = {
    0x11: 'in', 0x16: 'out', 0x17: 'duration', 0x1b: 'framebase',
    0x1c: 'flag1c', 0x1d: 'name', 0x22: 'p22', 0x23: 'state',
    0x24: 'p24', 0x25: 'renderQuality', 0x2a: 'width', 0x2b: 'height',
    0xbb: 'pBB', 0xbc: 'pBC',
}

def decode_str(b):
    for enc in ('utf-8', 'mac-roman'):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode('latin1', 'replace')

def tc(frames, fps=25):
    if frames is None: return ''
    f = int(frames)
    return f"{f//(3600*fps):02d}:{f//(60*fps)%60:02d}:{f//fps%60:02d}:{f%fps:02d}"

def scan_items(data):
    """Retourne [(offset, nom, {props})] pour chaque enregistrement-nom id 0x1d."""
    name_re = re.compile(rb'\x00\x00\x1d\x00\x00\x00\x1f\x01\x01')
    starts = []
    for m in name_re.finditer(data):
        ln, = struct.unpack_from('>I', data, m.end())
        if 0 < ln <= 300:
            txt = data[m.end()+4:m.end()+4+ln]
            if len(txt) == ln:
                starts.append((m.start(), m.end()+4+ln, decode_str(txt)))
    items = []
    num_re = re.compile(rb'\x00([\x00-\xff]{2})\x00\x00\x00([\x01\x04\x05])')
    for (s, vend, name), nxt in zip(starts, starts[1:] + [(len(data),0,'')]):
        window = data[vend:min(nxt[0], vend + 2000)]
        props = {}
        for m in num_re.finditer(window):
            pid, = struct.unpack('>H', m.group(1))
            t = m.group(2)[0]
            vo = m.end() + 1  # après octet version
            try:
                if t == 1: v = struct.unpack_from('>i', window, vo)[0]
                elif t == 4: v = struct.unpack_from('>d', window, vo)[0]
                else: v = window[vo]
            except (struct.error, IndexError):
                continue
            props.setdefault(pid, v)
        items.append((s, name, props))
    return items

if __name__ == '__main__':
    data = open(sys.argv[1], 'rb').read()
    items = scan_items(data)
    print(f"{len(items)} éléments nommés\n")
    seqs = [(o,n,p) for o,n,p in items if p.get(0x2a) and p.get(0x2b)]
    print(f"## Séquences probables ({len(seqs)}) — largeur×hauteur définies")
    for o, n, p in seqs:
        d = p.get(0x17)
        fb = p.get(0x1b) or 25
        print(f"  {n:40s} {p.get(0x2a)}x{p.get(0x2b)}  durée={tc(d)} ({d and int(d)} fr)")
    if '--all' in sys.argv:
        print("\n## Tous les éléments")
        for o, n, p in items:
            ps = {PROP_NAMES.get(k, hex(k)): v for k, v in sorted(p.items())}
            print(f"@{o:#08x} {n!r} {ps}")
