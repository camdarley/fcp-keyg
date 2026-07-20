#!/usr/bin/env python3
"""
Export des timelines FCP 'KeyG' vers XML FCP7 (XMEML v4),
importable dans DaVinci Resolve / Premiere Pro.

- Réutilise l'extracteur fcp_timelines (BE/LE, ids auto-calibrés).
- Récupère les chemins POSIX des médias via les AliasRecords pour le relink.
- Les clips qui se chevauchent sont répartis sur plusieurs pistes (partition
  gloutonne par intervalle).
- Les clips sans source (transitions/générateurs) sont exportés en marqueurs
  de séquence plutôt qu'en clips (pour ne pas polluer le montage).

Usage: fcp_export_xml.py projet.fcp [sortie.xml] [--seq FILTRE] [--fps 25]
       [--min-clips N] (défaut 4)
"""
import re, struct, sys, os
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fcp_timelines import build, GUID_RE, decode_str, tc

def media_paths(data):
    """filename -> chemin POSIX complet, par scan global des tags d'alias :
    0x12 = chemin POSIX (souvent relatif au volume), 0x13 = point de montage.
    Un 0x12 est apparié au 0x13 qui le suit à moins de 300 octets."""
    PATH_CHARS = re.compile(rb'^[^\x00-\x1f]+$')
    entries = []          # (off, tag, texte)
    for m in re.finditer(rb'\x00([\x12\x13])\x00([\x01-\xff])', data):
        tag, ln = m.group(1)[0], m.group(2)[0]
        cand = data[m.end():m.end()+ln]
        if len(cand) == ln and b'/' in cand and PATH_CHARS.match(cand):
            try: s = cand.decode('utf-8')
            except UnicodeDecodeError:
                s = cand.decode('mac-roman', 'replace')
            entries.append((m.start(), tag, s))
    paths = {}
    for i, (off, tag, s) in enumerate(entries):
        if tag != 0x12: continue
        if s.startswith('/Volumes'):
            full = s
        else:
            mount = None
            for off2, tag2, s2 in entries[i+1:i+3]:
                if tag2 == 0x13 and off2 - off < 300 and s2.startswith('/'):
                    mount = s2; break
            full = (mount.rstrip('/') + '/' + s.lstrip('/')) if mount else None
        if full:
            base = os.path.basename(full)
            paths.setdefault(base, full)
            paths.setdefault(os.path.splitext(base)[0].lower(), full)
    return paths

def partition_tracks(clips):
    """Répartit les clips en pistes sans chevauchement (glouton)."""
    tracks = []
    for c in sorted(clips, key=lambda c: (c['start'], c['end'])):
        for t in tracks:
            if t[-1]['end'] <= c['start'] + 0.01:
                t.append(c); break
        else:
            tracks.append([c])
    return tracks

def xml_rate(fps):
    return f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"

def export(path, out, flt=None, fps=25, min_clips=4):
    data = open(path, 'rb').read()
    sequences, guid2name, ids, endian, resolve_ref = build(data)
    paths = media_paths(data)
    proj = os.path.splitext(os.path.basename(path))[0]

    file_ids = {}
    def file_xml(name):
        """Déclare (une fois) puis référence un <file>."""
        if name in file_ids:
            return f'<file id="{file_ids[name]}"/>'
        fid = f"file-{len(file_ids)+1}"
        file_ids[name] = fid
        p = paths.get(name) or paths.get(os.path.splitext(name)[0].lower())
        pathurl = f"<pathurl>file://localhost{escape(p)}</pathurl>" if p else ""
        return (f'<file id="{fid}"><name>{escape(name)}</name>{pathurl}'
                f'{xml_rate(fps)}<media><video/><audio/></media></file>')

    seq_blocks = []
    exported = 0
    for s in sequences:
        if flt and flt.lower() not in s['name'].lower(): continue
        clips = [c for c in s['clips']
                 if c.get('src_in') is not None and c.get('src_out') is not None
                 and c['src_in'] >= 0 and c['src_out'] > c['src_in']]
        if len(clips) < min_clips: continue
        dur = int(max(c['end'] for c in clips))
        tracks_xml = []
        for lane in partition_tracks(clips):
            items = []
            for i, c in enumerate(lane):
                nm = guid2name.get(c.get('master'))
                if not nm and c.get('mref') is not None: nm = resolve_ref(c['mref'])
                if not nm and c.get('nref') is not None: nm = resolve_ref(c['nref'])
                if not nm: nm = 'clip inconnu'
                start, end = int(c['start']), int(c['end'])
                cin = int(c['src_in']); cout = int(c['src_out'])
                if cout - cin != end - start:      # cohérence exigée par XMEML
                    cout = cin + (end - start)
                items.append(
                    f'<clipitem id="ci-{exported}-{len(tracks_xml)}-{i}">'
                    f'<name>{escape(nm)}</name>{xml_rate(fps)}'
                    f'<start>{start}</start><end>{end}</end>'
                    f'<in>{cin}</in><out>{cout}</out>'
                    f'<duration>{cout-cin}</duration>'
                    f'{file_xml(nm)}</clipitem>')
            tracks_xml.append('<track>' + ''.join(items) + '</track>')
        w, h = (720, 576)
        seq_blocks.append(
            f'<sequence id="seq-{exported}"><name>{escape(s["name"])}</name>'
            f'<duration>{dur}</duration>{xml_rate(fps)}'
            f'<timecode>{xml_rate(fps)}<frame>0</frame>'
            f'<displayformat>NDF</displayformat></timecode>'
            f'<media><video><format><samplecharacteristics>'
            f'{xml_rate(fps)}<width>{w}</width><height>{h}</height>'
            f'<pixelaspectratio>PAL-601</pixelaspectratio>'
            f'</samplecharacteristics></format>'
            + ''.join(tracks_xml) +
            '</video><audio><format><samplecharacteristics><depth>16</depth>'
            '<samplerate>48000</samplerate></samplecharacteristics></format>'
            '</audio></media></sequence>')
        exported += 1

    doc = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
           f'<xmeml version="4"><project><name>{escape(proj)}</name><children>'
           + ''.join(seq_blocks) + '</children></project></xmeml>')
    open(out, 'w', encoding='utf-8').write(doc)
    return exported, len(file_ids), out

if __name__ == '__main__':
    path = sys.argv[1]
    args = sys.argv[2:]
    out = args[0] if args and not args[0].startswith('--') else \
        os.path.splitext(os.path.basename(path))[0] + '.xml'
    flt = args[args.index('--seq')+1] if '--seq' in args else None
    fps = int(args[args.index('--fps')+1]) if '--fps' in args else 25
    mc = int(args[args.index('--min-clips')+1]) if '--min-clips' in args else 4
    n, nf, out = export(path, out, flt, fps, mc)
    print(f"{n} séquences, {nf} fichiers médias → {out}")
