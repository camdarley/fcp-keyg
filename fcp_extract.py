#!/usr/bin/env python3
"""
Extracteur d'informations pour projets Final Cut Pro 1-7 (format binaire 'KeyG').

Format rétro-conçu (juillet 2026) :
  - Magic : A2 'KeyG' 0A 0D 0A  (KeyGrip = nom de code originel de FCP)
  - Arbre de propriétés sérialisé, big-endian :
      record := [clé][type:u32][payload]
      clé    := [len:u8][ASCII]  si len>0, sinon [0x00][id:u16] (clé numérique)
      types  : 0x01=int32, 0x04=double, 0x05=bool/u8, 0x0b=str(u32 len),
               0x1f=str('01 01' + u32 len, UTF-8), 0x23=GUID-string,
               0x00=conteneur/objet, 0x0e=rect...
      Chaque valeur est suivie d'un octet 'annotation' (0=aucune,
      1=annotation de 9 octets + GUID optionnel).
  - Références médias : AliasRecord Mac OS classiques (avec chemins POSIX)
"""
import re, struct, sys, collections, datetime

MAC_EPOCH = datetime.datetime(1904, 1, 1)

def mac_date(secs):
    if not secs: return None
    return (MAC_EPOCH + datetime.timedelta(seconds=secs)).strftime('%Y-%m-%d %H:%M:%S')

def decode_str(b):
    for enc in ('utf-8', 'mac-roman'):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode('latin1', 'replace')

def parse_header(data):
    assert data[:8] == b'\xa2KeyG\n\r\n', "magic KeyG absent"
    v1, v2 = struct.unpack_from('>II', data, 8)
    guid = data[16:32].hex()
    return {'version_a': v1, 'version_b': v2, 'guid': guid}

KEY_RE = re.compile(rb'([\x02-\x1c])([A-Za-z_][A-Za-z0-9_ ]{1,27})')

def keyed_scalars(data):
    """Tous les enregistrements [clé ASCII][type scalaire][valeur]."""
    out = []
    for m in KEY_RE.finditer(data):
        i, l = m.start(), data[m.start()]
        key = m.group(2)
        if len(key) != l: continue
        t, = struct.unpack_from('>I', data, i+1+l)
        vs = i+1+l+4
        try:
            if t == 0x01:
                v = struct.unpack_from('>i', data, vs+1)[0]
            elif t == 0x04:
                v = struct.unpack_from('>d', data, vs+1)[0]
            elif t == 0x05:
                v = bool(data[vs+1])
            elif t == 0x0b:
                ln, = struct.unpack_from('>I', data, vs+1)
                if ln > 1000: continue
                v = decode_str(data[vs+5:vs+5+ln])
            elif t == 0x1f:
                if data[vs:vs+2] != b'\x01\x01': continue
                ln, = struct.unpack_from('>I', data, vs+2)
                if ln > 1000: continue
                v = decode_str(data[vs+6:vs+6+ln])
            else:
                continue
        except struct.error:
            continue
        out.append((i, key.decode(), t, v))
    return out

def numeric_strings(data):
    """Chaînes type 0x1f à clé numérique : [00][id:u16][00 00 00 1f][01 01][len][texte]"""
    out = []
    for m in re.finditer(rb'\x00([\x00-\xff]{2})\x00\x00\x00\x1f\x01\x01', data):
        kid, = struct.unpack('>H', m.group(1))
        ln, = struct.unpack_from('>I', data, m.end())
        if 0 < ln <= 300:
            txt = data[m.end()+4:m.end()+4+ln]
            if len(txt) == ln:
                out.append((m.start(), kid, decode_str(txt)))
    return out

def alias_records(data):
    """AliasRecords Mac OS : cherche l'en-tête [type 4cc][creator 4cc][ver=0002]
    puis lit volume + chemins. Structure alias v2 classique."""
    out = []
    # signature : 4cc + 4cc + 00 02 00 XX ... déjà observé: 'MooVKeyG 00 01 00 02'
    for m in re.finditer(rb'([ -~]{4})([ -~]{4})\x00\x01\x00\x02\x00', data):
        base = m.start()
        rec = {'off': base, 'type': m.group(1).decode(), 'creator': m.group(2).decode()}
        # après l'en-tête: userType(4)+size(2)? on cherche pragmatiquement le
        # bloc de chaînes taguées en fin d'alias : [tag:u16][len:u16][data pad2]
        # On scanne en avant jusqu'à 1200 octets pour tag 0x0002 (chemin HFS)
        # et 0x0012 (chemin POSIX), 0xFFFF = fin.
        w = data[base:base+1400]
        paths = {}
        for t_off in range(0, len(w)-4):
            tag, ln = struct.unpack_from('>HH', w, t_off)
            if tag in (0x0002, 0x0012) and 0 < ln < 600 and t_off+4+ln <= len(w):
                cand = w[t_off+4:t_off+4+ln]
                if all(0x20 <= c < 0xff and c != 0x7f for c in cand):
                    name = {2: 'hfs', 0x12: 'posix'}[tag]
                    s = decode_str(cand)
                    if (tag == 2 and s.count(':') >= 1) or (tag == 0x12 and s.startswith('/')):
                        paths.setdefault(name, s)
        rec.update(paths)
        if paths:
            out.append(rec)
    return out

def item_table(data):
    idx = [m.start() for m in re.finditer(rb'22CProjectItemTableEntry', data)]
    return len(idx)

if __name__ == '__main__':
    path = sys.argv[1]
    data = open(path, 'rb').read()
    hdr = parse_header(data)
    print(f"# Projet : {path.rsplit('/',1)[-1]}  ({len(data)} octets)")
    print(f"en-tête : versions {hdr['version_a']:#x}/{hdr['version_b']:#x} guid {hdr['guid']}")

    n_items = item_table(data)
    scal = keyed_scalars(data)
    seqc = [v for _, k, _, v in scal if k == 'sequence_count']
    print(f"éléments du projet (table) : {n_items} ; sequence_count : {seqc}")

    print("\n## Chaînes à clé numérique (noms d'éléments, effets, presets)")
    ns = numeric_strings(data)
    ctr = collections.Counter((kid, txt) for _, kid, txt in ns)
    for (kid, txt), c in sorted(ctr.items()):
        print(f"  id={kid:#06x} ×{c:<3d} {txt!r}")

    print("\n## Médias référencés (AliasRecords)")
    seen = set()
    for rec in alias_records(data):
        p = rec.get('posix') or rec.get('hfs')
        key = (rec['type'], p)
        if key in seen: continue
        seen.add(key)
        print(f"  [{rec['type']}/{rec['creator']}] {p}")
