# fcp-keyg — The Final Cut Pro 1–7 binary project format, documented

**The first public specification of Apple Final Cut Pro's legacy binary
project format (`.fcp`, magic `KeyG`), with working extraction tools.**

From 1999 to 2011, Final Cut Pro (versions 1 through 7) saved projects in an
undocumented proprietary binary format. FCP 7 was discontinued in 2011 and no
modern software can open these files — yet countless post-production archives
still hold thousands of them, each containing edits, timelines, markers, and
media references that are otherwise lost.

This project is the result of a clean-room reverse engineering effort
conducted exclusively by analyzing project *data files* (no decompilation of
Apple software, no circumvention of any technical protection measure), for
interoperability and digital-preservation purposes.

> This is independent documentation, not affiliated with, endorsed by, or
> sponsored by Apple Inc. "Final Cut Pro" and "Apple" are trademarks of
> Apple Inc., used here only to identify the file format concerned.

## Contents

| File | Description |
|------|-------------|
| [`SPEC_FCP_KeyG_EN.md`](SPEC_FCP_KeyG_EN.md) | Full format specification (English) |
| [`SPEC_FCP_KeyG.md`](SPEC_FCP_KeyG.md) | Spécification complète (français, version originale) |
| `fcp_timelines.py` | Timeline extractor — sequences, tracks, clips with timeline/source in-out points. Auto-detects endianness (PowerPC/Intel) and auto-calibrates the file's dynamic property ids. CSV/JSON output. |
| `fcp_export_xml.py` | FCP7 XML (XMEML v4) exporter — import the recovered timelines into DaVinci Resolve or Premiere Pro. |
| `fcp_extract.py` | Header, strings, item table, and media references (Alias records with POSIX paths). |
| `fcp_items.py` | Browser item listing with durations and dimensions. |
| `process_vault.sh` | Batch-process an entire FCP Autosave Vault into CSVs + XMLs. |

## Quick start

```sh
# What's inside a project?
python3 fcp_extract.py MyProject.fcp

# Recover the timelines
python3 fcp_timelines.py MyProject.fcp --csv timelines.csv

# Export to FCP7 XML for DaVinci Resolve / Premiere Pro
python3 fcp_export_xml.py MyProject.fcp MyProject.xml
```

No dependencies beyond Python 3.

## Format at a glance

- Magic: `A2 4B 65 79 47 0A 0D 0A` (`.KeyG` — from *KeyGrip*, FCP's original
  codename at Macromedia).
- A serialized property tree, big-endian on PowerPC-era files and
  little-endian on Intel-era files.
- Numeric property ids are **dynamic per file** (references to interned key
  names) — any parser must discover them statistically, not hardcode them.
- Persistent object ids resolved through hierarchical id ranges stored in the
  project's item table.
- Media references are classic Mac OS Alias records, including POSIX paths.

See the [specification](SPEC_FCP_KeyG_EN.md) for the full picture, including
what remains unresolved (contributions welcome).

## Status and limitations

Validated on a corpus of real-world projects from 2007–2013 (FCP 5 through 7,
PAL). Known gaps: audio clip layout in little-endian files, track grouping in
little-endian files, NTSC/drop-frame untested, FCP 1–3 (Mac OS 9) untested.
Issue reports with sample files are very welcome.

## Licensing

- Code (`*.py`, `*.sh`): [MIT License](LICENSE)
- Documentation (`SPEC_*.md`, this README):
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
