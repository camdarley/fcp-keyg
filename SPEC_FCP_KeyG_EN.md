# The "KeyG" binary format — Final Cut Pro 1–7 project files: a specification

> **Independent documentation** — not affiliated with, endorsed by, or
> sponsored by Apple Inc. "Final Cut Pro" and "Apple" are trademarks of
> Apple Inc., used here only to identify the file format concerned. This
> specification was produced exclusively by analyzing data files (no
> decompilation of any software, no circumvention of any technical
> protection measure), for interoperability and digital-preservation
> purposes. Text licensed under CC BY-SA 4.0.


**Status: independent reverse engineering — July 2026**
**Document version: 1.0**

---

## Foreword and conventions

This document describes the binary format of the project files of Final Cut
Pro versions 1 through 7 (extension `.fcp`, internal magic "KeyG"). This
proprietary Apple format has never been publicly documented. The present
specification is the result of reverse engineering carried out on a corpus of
real-world projects: projects created in 2008 on PowerPC (big-endian) and
projects created in 2009 on Intel Macs (little-endian), including several
successive saves of the same projects (Autosave Vault), which made
differential analysis possible.

It is published for the digital-preservation and audiovisual-archiving
community: tens of thousands of editing projects from the 1999–2011 period
are today readable by no maintained software, and the primary goal is to
enable the extraction of timelines (sequences, clips, in/out points, media
references) to open formats.

### Notation conventions

- All offsets and constants are in hexadecimal, prefixed `0x`;
  raw bytes are written `A2 4B 65 79`.
- `u8`, `u16`, `u32`, `u64`: unsigned integers of 1, 2, 4, 8 bytes;
  `i32`: signed 32-bit integer; `f64`: IEEE 754 double-precision float.
  Unless stated otherwise, these fields are in the **file's native**
  endianness (see § 3).
- `4cc`: four-character ASCII code (FourCC), e.g. `MooV`.
- Every claim is qualified:
  - **[verified]**: checked on several independent files, often
    cross-checked by a successful import of the result into third-party
    software;
  - **[hypothesis]**: an interpretation consistent with the observations but
    not confirmed by independent cross-checking.
- Hexadecimal examples are either transcribed from real files
  (marked "observed"), or **reconstructed** with identical structure
  using generic anonymized data (marked "reconstructed"):
  clip names `INTERVIEW_01`, volumes `DISK01`, etc.
- The corpus specimens are referred to anonymously:
  - **specimen A**: 2008 project, PowerPC, big-endian (two successive
    saves A₁ and A₂ of the same project);
  - **specimen B**: 2009 project, Intel Mac, little-endian (two autosaves);
  - **specimens C, D**: other 2009 little-endian projects from an
    Autosave Vault.

---

## 1. Introduction and historical context

### 1.1 From KeyGrip to Final Cut Pro

Final Cut was born at Macromedia in the mid-1990s under the code name
**KeyGrip**. The project was acquired by Apple in 1998 and released as
Final Cut Pro 1.0 in 1999. The original code name survived in the file
format: the project magic contains the string "`KeyG`", and the audio
waveform cache carries the file type `KGWV`
("**K**ey**G**rip **W**a**V**e").

The "KeyG" format was used without interruption by every version of
"classic" Final Cut Pro (1.0, 1999 → 7.0.3, 2009, maintained until
2011), on Mac OS 8/9 then Mac OS X, on PowerPC then Intel. Final Cut Pro X
(2011) abandoned this format entirely in favor of an incompatible
database; Apple provided no migration tool beyond FCP X
10.x, and no current software reads binary `.fcp` files.

### 1.2 Why this format matters for archiving

An `.fcp` file contains the entirety of the intellectual value of an
edit: the list of source media with their original paths, the
sequences (timelines), the position of every clip, the in/out points
in the source footage, the transitions and effects, the logging metadata
(log notes, scenes, takes). The media themselves are generally
preserved; it is the *edit* that becomes unreadable. The ability to
extract from it an EDL or an interchange XML (XMEML) makes entire
production holdings from the 2000s usable again.

### 1.3 What this specification covers

- file identification and the header (§ 2);
- the two endianness variants and their detection (§ 3);
- the general serialization grammar — a tree of typed properties
  (§ 4 to § 6);
- the dynamic identifier system and string interning (§ 7);
- the project element table and reference resolution (§ 8);
- the semantic structure of elements: clips, sequences, clipitems (§ 9);
- media references (Mac OS AliasRecords) (§ 10);
- a method for automatic identifier calibration, indispensable because
  identifiers vary from one file to the next (§ 11).

Coverage is not exhaustive (§ 12 lists the unresolved areas), but it is
sufficient to extract complete timelines and to produce an XMEML v4
importable into current editing software — which served as
cross-validation.

---

## 2. File identification

### 2.1 Magic

A Final Cut Pro 1–7 project begins with the following 8 bytes **[verified]**:

```
A2 4B 65 79 47 0A 0D 0A
│  └─────────┘ └──────┘
│   "KeyG"      \n \r \n
└─ 0xA2 (non-ASCII byte, guards against line-ending conversions,
   in the manner of the PNG magic)
```

The `0A 0D 0A` (LF CR LF) sequence plays the same role as in the PNG magic:
a file transferred in text mode would be corrupted in a detectable way.

**Warning**: the `.fcp` extension guarantees nothing. The corpus contained a
`.fcp` file that was in reality a raw QuickTime video stream (frames in the
Animation/RLE codec with no `moov` atom), misnamed. Any tool must check
the magic before parsing.

### 2.2 Header (51 bytes)

The header occupies bytes `0x00`–`0x32`; the first data record
begins at offset `0x33` **[verified on all 6 specimens]**.

| Offset | Size | Contents |
|--------|--------|---------|
| 0x00 | 8 | Magic `A2 4B 65 79 47 0A 0D 0A` |
| 0x08 | 1 | Endianness indicator: `00` = big-endian, `01` = little-endian **[verified on 6 files; see § 3]** |
| 0x09 | 4 | native u32, variable between saves of the same project (increasing: 0xB7 then 0xC8 across the two saves of specimen A) — save/serialization counter **[hypothesis]** |
| 0x0D | 16 | UUID, fields stored in native endianness (u32, u16, u16, then 8 raw bytes) — see § 2.3 |
| 0x1D | 4 | u32 = 3: header format version **[hypothesis; constant across the whole corpus]** |
| 0x21 | 8 | u64 = 0: identifier of the root object |
| 0x29 | 1 | `01`: slot "a" present |
| 0x2A | 4 | u32 = 0: value of slot "a" |
| 0x2E | 1 | `01`: field counter present |
| 0x2F | 4 | u32 `NFIELDS`: number of records of the root object (0x17 = 23 on specimen A; 0x14–0x15 on the LE specimens) |
| 0x33 | — | First record (key `subtype`…) |

Bytes `0x21`–`0x32` exactly reproduce the structure of a **container
item** (see § 6.3): `[u64 id][01][u32 a][01][u32 nf]`. In other words,
the entire document is serialized as an item object with identifier 0
owning `NFIELDS` root properties **[verified structurally; greedy
reading of the records starting at 0x33 is consistent with this
count]**.

Annotated dump of the header (observed, specimen A₂, big-endian):

```
0000: A2 4B 65 79 47 0A 0D 0A   magic "KeyG"
0008: 00                        endianness = big-endian
0009: 00 00 00 C8               save counter = 200 (0xB7=183 in the
                                previous save of the same project)
000D: 66 92 08 20  28 C4  11 D7 UUID: 66920820-28C4-11D7-
0015: 8A E5  00 30 65 EC FE 98        8AE5-003065ECFE98
001D: 00 00 00 03               header version = 3
0021: 00 00 00 00 00 00 00 00   u64: root object id = 0
0029: 01 00 00 00 00            slot a present, a = 0
002E: 01 00 00 00 17            nfields present, 23 root properties
0033: 07 73 75 62 74 79 70 65…  1st record: key "subtype" (len 7)
```

The same header in little-endian (observed, specimen B) differs only in
byte 0x08 (`01`), the byte order of the integers, and the order of the
first three fields of the UUID (`20 08 92 66  C4 28  D7 11  8A E5 00 30 65 EC FE
98`, i.e. the same UUID).

### 2.3 The header UUID: a format signature, not a document GUID

The 16 bytes at offset 0x0D form a version 1 UUID:
`66920820-28C4-11D7-8AE5-003065ECFE98`.

A v1 UUID encodes a timestamp and the MAC address of the machine that
generated it. Here:

- timestamp: **January 15, 2003** (development period of FCP 4);
- node: MAC address `00:30:65:EC:FE:98`, OUI `00:30:65` = **Apple
  Computer**.

Crucial point: this UUID is **identical in all six files of the corpus**,
even though they come from different machines, years and
architectures. It is therefore **not** a document GUID: it is a constant
generated once and for all on an Apple machine in 2003 and embedded in
the application — in effect, a **secondary signature of the format** (or of
its 2003 revision) **[verified: constant across 6 independent files; the
exact role remains a hypothesis]**. An identification tool may use it as
a confirmation criterion, taking into account the field byte-swapping in
little-endian.

The *actually* unique GUIDs (documents, clips, instances) appear
further on in the body of the file, as ASCII strings
`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (type 0x23, § 4.4) or as 16 raw
bytes in annotations (§ 5).

---

## 3. Endianness

### 3.1 Two variants of the same format

The format exists in two byte orders, determined by the architecture of
the machine that **created** the project **[verified]**:

- **big-endian**: PowerPC projects (observed: 2008);
- **little-endian**: Intel Mac projects (observed: 2009).

The grammar is strictly identical; only the u16/u32/u64/f64 values are
byte-swapped, along with the first three fields of the header UUID. String
lengths, version bytes and flags (u8) are unchanged.

### 3.2 Detection

Two methods, to be combined:

1. **Header byte 0x08**: `00` = BE, `01` = LE. Simple, but verified
   only on six files — to be treated as a hint **[hypothesis]**.

2. **Statistical probing of the pattern of a known record** **[verified,
   robust method]**: the Pascal key `duration` followed by type 0x04
   (double) appears many times in any project. Count the
   occurrences of the two possible encodings of the type:

   ```
   BE : 08 "duration" 00 00 00 04
   LE : 08 "duration" 04 00 00 00
   ```

   The more frequent one wins. As a fallback (a file with no `duration`
   key), count the type-0x1F string-definition patterns:
   `00 00 00 1F 01 01` (BE) versus `1F 00 00 00 01 01` (LE).

---

## 4. General data model: a serialized property tree

### 4.1 Overview

The body of the file is a single **property tree** serialized
depth-first: a root object (id 0, § 2.2) containing records,
some of which are containers containing objects (*items*)
which themselves contain records, recursively. There is neither an offset
table nor an index: the file is read sequentially, and the position of a
piece of data is known only by parsing everything that precedes it. (One
partial exception: the element table, § 8, provides a *logical* index — but
in identifiers, not in offsets.)

### 4.2 The record

```
record := [key] [type:u32] [payload] [annotation]
```

- **key**: two encodings **[verified]**:

  ```
  [len:u8 > 0][len ASCII bytes]      named key    e.g.  05 "width"
  [00][id:u32]                       numeric key  e.g.  00 00 00 00 1D
  ```

  Named keys are short Pascal strings (observed length
  ≤ 0x1C, printable ASCII characters: letters, digits, `_`, space).
  Numeric keys reference an interned name (§ 7); their useful
  values fit in 16 bits, but the field is indeed 4 bytes.

- **type**: u32, designates the payload type (§ 4.3).

- **payload**: depends on the type. Most scalars begin with a
  **version** byte (`ver`) that modulates the semantic interpretation of
  the value (see the ver-01/ver-02 doubles, § 9.3).

- **annotation**: present after *every* value (§ 5). At minimum a
  `00` byte.

### 4.3 Type system

Observed types **[verified for the structure; the semantics of 0x03, 0x08,
0x0C and 0x0E are partial]**:

| Type | Payload | Description |
|------|---------|-------------|
| 0x00 | see § 6 | container / object / object reference |
| 0x01 | `[ver:u8][i32]` | signed 32-bit integer |
| 0x03 | `[ver:u8][8 bytes]` | 64-bit value (role not determined) |
| 0x04 | `[ver:u8][f64]` | double — used for all times, in frames |
| 0x05 | `[ver:u8][u8]` | boolean |
| 0x08 | `[ver:u8][u32]` | unsigned integer (role not determined) |
| 0x0B | `[ver:u8][len:u32][bytes]` | "legacy" string, MacRoman/ASCII |
| 0x0C | `[f1:u8][f2:u8][u32][u32]` | pair of integers |
| 0x0E | `[ver:u8][4 × u32]` | rectangle (4 coordinates) |
| 0x1F | see § 4.4 | interned UTF-8 string (definition or reference) |
| 0x23 | see § 4.4 | GUID string (`XXXXXXXX-XXXX-…`), interned |

Any u32 greater than 0x30 encountered in type position signals a
parser desynchronization (resynchronization heuristic, § 13.2).

### 4.4 Strings: two generations, and a definition/reference mechanism

- **Type 0x0B** (classic Mac OS legacy): `[ver][len:u32][bytes]`,
  MacRoman or ASCII encoding. Used for legacy values
  (e.g. the render quality `"final"`).

- **Type 0x1F** (modern string): UTF-8 encoding (the accented characters
  of French effect names — « Fondu enchaîné », « Séquence » — are encoded
  there in UTF-8) **[verified]**. Two forms:

  ```
  [01][01][len:u32][UTF-8 bytes]     definition — the string is interned
                                     and consumes a persistent id (§ 7)
  [01][00][u32 ref]                  reference to an already interned string
  ```

- **Type 0x23** (GUID string): the value is a GUID serialized as ASCII
  (36 characters + variants). Observed forms:

  ```
  [00|01][01][u32][len:u32][GUID text]    inline (definition)
  [01][00][u32 ref]                       reference
  [00][00]…                               empty/null
  ```

In practice, a robust string-decoding strategy is: try
UTF-8, then MacRoman, then Latin-1 with replacement.

### 4.5 Annotated examples

**Integer record, numeric key (reconstructed — framebase = 25 fps, PAL):**

```
00                 numeric key
00 00 00 1B        key id = 0x1B ("framebase" in this file, cf. § 7)
00 00 00 01        type 0x01 = int32
01                 value version
00 00 00 19        value = 25
00                 no annotation
```

**Double record, named key, with annotation (observed, specimen A, offset
0x1AE):**

```
08 64 75 72 61 74 69 6F 6E    Pascal key: len 8, "duration"
00 00 00 04                   type 0x04 = double
01                            version 01
40 C2 7A 80 00 00 00 00       f64 = 9461.0   (frames; 9461/25 → 6'18"11)
01                            annotation present
00 00 00 01                   n = 1
00 00 00 18                   annotation class = 0x18
00                            flag 0: "id reference" form
00 00 00 17                   → numeric id 0x17: this is how the
                              file binds "duration" ↔ key 0x17 (§ 5, § 7)
```

**0x1F string record, numeric key (reconstructed — clip name):**

```
00                 numeric key
00 00 00 1D        id = 0x1D ("name" role in this file)
00 00 00 1F        type 0x1F = UTF-8 string
01 01              definition (interned string: consumes a persistent id)
00 00 00 0C        length = 12
49 4E 54 45 52 56 49 45 57 5F 30 31    "INTERVIEW_01"
00                 no annotation
```

---

## 5. Value annotations

Every payload is followed by an annotation block **[verified]**:

```
annotation := [00]                                   none
            | [01][u32 n][u32 class][attached]       annotation present

attached   := [00][u32 ref]                          "reference" form
            | [01][ver:u8][16-byte GUID][container]  "inline object" form
```

The only class observed is `0x18`. The `n` field is 1 in all cases
analyzed. **[the precise semantics of n and class remain a hypothesis]**

The two forms have distinct roles:

1. **Reference form** `[00][u32 X]`: X is an identifier in the file's
   persistent id space (§ 7). This is the mechanism that binds a
   **named key to its numeric id**: the `duration` record of the example
   in § 4.5 is annotated `→ 0x17`, and thereafter the file uses the
   numeric key `[00][00 00 00 17]` to mean "duration". These annotations
   also serve as **anchors** between an element and its identifier range
   in the project table (§ 8.3).

   Observed example (specimen A, offset 0x1A0):

   ```
   01              annotation present
   00 00 00 01     n = 1
   00 00 00 18     class 0x18
   00              reference form
   00 00 00 15     id 0x15 (binds the preceding key to id 0x15)
   ```

2. **Inline object form** `[01][ver][16-byte GUID][container]`: an
   auxiliary object is attached to the value, identified by a GUID of 16
   raw bytes (here in binary, unlike the GUID strings of type 0x23),
   followed by a complete container (§ 6) carrying the body of the object.

The binary pattern of the reference form is an excellent anchoring point for
a scanner: `01 00 00 00 01 00 00 00 18 00` in BE,
`01 01 00 00 00 18 00 00 00 00` in LE.

---

## 6. Containers and objects

### 6.1 Forms of type 0x00

A record of type 0x00 introduces a container, with four forms
**[verified]**:

```
container := [01][00][u32 ref]                       reference to an existing
                                                     object (persistent id)
           | [01][01][u32 n>0]  n × item             list of n items
           | [01][01][u32 0][01][u32 class]          typed empty object
           | [01][01][u32 0][00][u32 x]              null object / reference

then, in all cases, optional slots:
             [fa:u8]  if fa=01: [u32 a2]
             [fb:u8]  if fb=01: [u32 nf2] then nf2 records
```

### 6.2 The reference form `[01][00]`

`[01][00][u32 R]` designates an object already defined elsewhere, via the
persistent id space (§ 7). This is notably the form of the **track
references** of clipitems (§ 9.3): all clips of the same track of a
sequence carry a container-reference record with the same `R` **[verified
in BE; different in LE, see § 12]**.

### 6.3 Items

Each item of a list `[01][01][u32 n]` has the form **[verified]**:

```
item := [00]                        item absent (null slot)
      | [01]                        item present:
        [u64 local-id]              64-bit identifier local to the stream
        [f1:u8] if f1=01: [u32 a]   optional slot "a"
        [f2:u8] if f2=01: [u32 nf]  optional field counter
        nf × record                 the object's properties
```

Important points:

- The **u64 item ids are local**: they do not participate in the
  persistent u32 id space used by `[01 00]` references and
  annotations. The two identifier spaces are disjoint **[verified]**.
- `nf` (NFIELDS) gives the exact number of records in the item body —
  this is what allows bounded recursive parsing. The root object of the
  file follows exactly this form (§ 2.2).
- The end of a list of records read "greedily" (without a known nf) is
  detected by parse failure: the next byte does not form a valid
  key/type.

### 6.4 Example: start of the `clipList` container (observed, specimen A)

```
08 63 6C 69 70 4C 69 73 74     Pascal key "clipList" (len 8)
00 00 00 00                    type 0x00 = container
01 01                          list form
00 00 00 01                    n = 1 item
00                             (preamble bytes whose exact interpretation
00 00 00 20                     has not been settled; byte 0x20 and the
                                u32 that follows systematically precede
                                the entry counter)              [hypothesis]
00 00 03 76                    number of table entries = 886
01 00 00 00 18                 string: definition, length 0x18 = 24
32 32 43 50 72 6F 6A 65 63 74  "22CProjectItemTableEntry"
49 74 65 6D 54 61 62 6C 65      (C++ class name prefixed by its decimal
45 6E 74 72 79                   length "22", in the manner of name
…                                mangling)
                               continuation of the 1st entry (§ 8.2)
```

---

## 7. The identifier system: dynamic ids, persistent ids, interning

This is the most counter-intuitive point of the format, and the main cause
of failure of a naive parser.

### 7.1 Numeric key ids are specific to each file

Numeric keys (`[00][u32 id]`) are **not** a fixed vocabulary of the
format: they are **references to key names interned as the file is
written**. The first time a property is written, it is
written under its named key (Pascal string), with an annotation
`→ id` (§ 5); subsequent writes use the numeric key. The id
assigned therefore depends on the **write order**, which depends on the
project's history **[verified]**.

Measured example: the key carrying the master GUID of a clipitem is **0x7E**
in one save of a project, **0xD9** in the next save of the
*same* project, and **0xCA** in a 2009 little-endian project. Likewise the
"element name" role is 0x1D in specimen A but other values
elsewhere.

Consequence: **no numeric key constant should ever be
hard-coded**. An extractor must either reconstruct the name→id table by
following the binding annotations (§ 5), or discover the ids **by
statistical role** (§ 11). The id tables given in § 9 are therefore
*per-file examples*, not constants of the format.

### 7.2 The persistent id space

The u32 references (`[01 00]` strings, container references,
reference-form annotations) live in a space of **persistent ids**,
allocated over the whole life of the project, with each definition
(`[01 01]` of a 0x1F/0x23 string, an annotation's inline object…)
consuming an id. These ids **cannot be reconstructed by simply
counting** the definitions in the file: ids are "burned" by deleted
objects, undo regions, copies — the space has holes **[verified: naive
counting diverges rapidly]**.

The practical resolution of a reference goes through the project element
table, which delimits id ranges per element (§ 8).

### 7.3 Summary of the definition/reference pattern

| Context | Definition (consumes an id) | Reference |
|----------|------------------------------|-----------|
| 0x1F string | `[01][01][len][text]` | `[01][00][u32]` |
| 0x23 GUID string | `[0x][01][u32][len][text]` | `[01][00][u32]` |
| 0x00 container | `[01][01][n]…` | `[01][00][u32]` |
| annotation | `[01][ver][GUID][container]` | `[00][u32]` |

---

## 8. The `CProjectItemTableEntry` table and reference resolution

### 8.1 Role

The root record `clipList` (§ 6.4) contains the table of the project's
elements (clips, sequences, bins): one `CProjectItemTableEntry` entry per
element, plus `CProjectItemNestEntry` entries for nestings
(sequence within sequence) **[verified]**. This table serves as a *logical*
index: it associates each element with a **range of the persistent id
space**.

### 8.2 Structure of an entry

Each entry is written as follows **[verified for the v1/v2 fields; the 4
intermediate bytes are interpreted as flags/version]**:

```
01 [u32 = 0x18] "22CProjectItemTableEntry"   class name (24 bytes),
                                             1st occurrence; subsequent
                                             ones may be references
[u16][u16]                                   flags/version (values 0/1)
[f1:u8][u32 v1]                              if f1=01: v1 null/absent
[f2:u8][u32 v2]                              if f2=01: v2 null/absent
```

`v1` and `v2` are two positions in the persistent id space.
First observed entry of specimen A: `v1 = 0x10`, `v2 = 0x37`.

### 8.3 Semantics: hierarchical id ranges

**[verified by multiple cross-checks]**:

- a "narrow" entry (0 < v2 − v1 < ~500) marks the **start of the id
  range** of a leaf element (clip, sequence). By sorting the narrow v1s
  in increasing order, element i owns the interval `[v1_i, v1_{i+1})`;
- "wide" entries (e.g. a bin covering (10, 2100)) **enclose**
  the ranges of their children: the table encodes the
  bin → elements hierarchy by interval inclusion;
- an element's interval is **anchored to its name** by the
  reference-form annotations `[01][u32 1][u32 0x18][00][u32 X]` present
  in its record: the X values observed in the window following an
  element's name record fall within that element's interval. A majority
  vote (several annotations per element) makes the anchoring robust.

### 8.4 Reference-resolution algorithm

To resolve a persistent reference R (a clip's master, a referenced name,
a transition…) to an element name:

```
1. Collect the v1 values of the narrow entries of the table; sort →
   interval bounds.
2. For each element name record ("name" role, § 11), scan the following
   window (~1500 bytes) for the annotations [ … 0x18][00][u32 X];
   assign by vote the interval containing X to the name.
   (Exclude reverse-DNS identifier strings "com.apple.…" which are
   not element names.)
3. resolve(R) = name of the interval containing R
   (binary search over the bounds).
```

Validations performed **[verified]**: the masters referenced by the clips
of a sequence `SEQ_INTERVIEW_01` resolve to the source clip
`INTERVIEW_01_CAM2` of the bin; the references carried by the transitions
resolve to the effect "Cross fade 0 dB"; nested sequences
resolve to the correct child sequence.

---

## 9. Semantic structure of the elements

### 9.1 Organization of the item stream

The main item stream serializes, in order **[verified]**:

1. the **masters**: the bin's clips, each accompanied by approximately
   three viewer-state pseudo-clips;
2. the **sequences**, each followed by its **clipitems** (~1 KB per clip).

The assignment of a clipitem to its sequence is done by position in the
stream: the last sequence header encountered. This rule is reliable but
must be **validated by consistency** coverage ≈ duration (§ 13.3), since
undo regions and internal copies can cause foreign clips to spill into a
sequence's window **[verified, with this caveat]**.

### 9.2 Element properties and sequence header

Property ids recorded on specimen A (reminder § 7.1: values specific
to this file):

| id (specimen A) | role | type |
|------|------|------|
| 0x11 | in (frames) | 0x04 |
| 0x16 | out (frames) | 0x04 |
| 0x17 | duration (frames) | 0x04 |
| 0x1B | timebase (25 = PAL) | 0x01 |
| 0x1D | element name | 0x1F |
| 0x22 | sequence-header marker (int ver-00) | 0x01 |
| 0x23 | state (1500 for a sequence) | 0x01 |
| 0x25 | render quality (`"final"`) | 0x0B |
| 0x2A | width | 0x01 |
| 0x2B | height | 0x01 |

A **sequence header** follows the pattern (specimen A ids) **[verified]**:

```
[0x1D sequence name]
[0x22 int, version 00]            ← discriminating marker (§ 11)
[0x23 state = 1500]
[0x25 "final"]                    render quality
[0x2A width][0x2B height]         e.g. 720 × 576
[0x2C container][0x2F u64 item]   timeline object (nf fields)
[0x11 = -1][0x16 = -1]            in/out undefined at the sequence level
[0x17 total duration in frames]
[0x18][0x19][0x1A]
[0x1B framebase][0x1C]
```

A time of −1 means "undefined". Durations/times are f64 values in
frames; the timecode is obtained by dividing by the base (`framebase`,
25 in PAL).

Named keys observed at the root and in the elements: `subtype`,
`NOUNDO`, `RUNTIME`, `viewers`, `children`, `browser_where`, `mainDict`
(subkeys `in`/`out`/`duration`/`marked`/`position`/`tcbase`/`framebase`/
`ntscrate`/`name`), `media`, `vidm` (`width`/`height`), `track`, `clip`,
`filters`, `masterClips`, `master` (GUID), `file`, `reader` (`"QTMRead"`),
`sequence_count`, `clipList`.

### 9.3 Clipitems

A clipitem (an occurrence of a clip in a timeline) carries **[verified]**:

- **timeline start / end**: two **version 01** doubles, in frames;
- **source in / out**: two **version 02** doubles (position within the
  source media), written as a consecutive pair;
- **source media duration**: one version 01 double;
- **framebase**: int;
- **instance GUID**: type 0x23, inline at the first occurrence then by
  reference. Caution: this GUID identifies the clip's **instance** in the
  timeline, not the master. The master is obtained via the associated
  persistent reference (resolution § 8.4) or via the referenced name;
- **track reference**: a container-reference record `[01 00][u32
  track-id]` — all clips of the same track share the same id (BE);
- miscellaneous: a project GUID reference, a 0x0C pair, four consecutive
  ints of undetermined role.

The **version byte of the doubles carries semantics**: it is what
distinguishes timeline times (ver 01) from source times (ver 02), and it is
the most stable invariant of the format across the years and the
endiannesses **[verified]** — hence its use as a calibration anchor (§ 11).

Comparative table of observed ids (illustrates § 7.1 — same roles, same
types, same order, different ids):

| role | specimen A (BE, 2008) | specimen B (LE, 2009) |
|------|------------------------|------------------------|
| timeline start | 0x11 (double ver 01) | 0x0B |
| timeline end | 0x16 (double ver 01) | 0x10 |
| source in | 0xBB (double ver 02) | 0x32 |
| source out | 0xBC (double ver 02) | 0x33 |
| media duration | 0x17 (double ver 01) | 0x11 (!) |
| framebase | 0x1B (int) | 0x15 |
| instance GUID | 0xD9 (type 0x23) | 0xCA |
| sequence marker | 0x22 (int ver 00) | 0x1C (0x21 on specimen C) |

The "0x11" that means *timeline start* in one file and *media duration*
in another shows that a table of constants is doomed to fail.

### 9.4 Transitions, effects, generators

Transitions are timeline elements with no source in/out; their
references resolve to the name of the effect (e.g. "Cross fade 0 dB",
"Fondu enchaîné") via the table (§ 8.4). Transition definitions
embed the **complete FXScript source code** of the effect (script
identifier and program body, e.g. "Cross Dissolve"); this code is
extractable as-is from the file, but being proprietary Apple source
code, it is not reproduced in this specification **[verified for its
presence; contents not reproduced]**.

### 9.5 Ancillary data

- **Interface**: the bin column definitions (`lognote`,
  `scene`, `take`, `comment1`–`comment6`, `good`, `labelColor`…) are
  stored, repeated per open window.
- **Render files**: "render file" streams list the names of the
  render files attached to the sequences (e.g.
  `sequence_v1-FIN-0000043a`).
- **sequence_count**: root counter of the number of sequences.

---

## 10. Media references: Mac OS AliasRecords

### 10.1 Context

Each linked media file is described by a classic Mac OS **AliasRecord**
(version 2) — the system structure used by the Finder for aliases, with
multiple resolution paths (volume/file identifiers, HFS and POSIX paths).
The record is preceded by the type/creator pair of the target file
**[verified]**:

```
[type 4cc][creator 4cc][00 01][00 02] …alias body…
```

### 10.2 Alias body: tagged entries

After a short fixed part, the alias is a series of entries
`[tag:u16][len:u16][data][pad to 2 bytes]`, terminated by the tag `0xFFFF`.
Tags observed in the projects **[verified]**:

| tag | contents |
|-----|---------|
| 0x0000 | parent folder name (Pascal string) |
| 0x0001 | folder identifiers (u32) |
| 0x0002 | absolute HFS path `Volume:folder:file` (MacRoman) |
| 0x000E | file name in UTF-16 |
| 0x000F | volume name in UTF-16 |
| 0x0010, 0x0011 | dates (Mac epoch: seconds since 1904-01-01) |
| 0x0012 | POSIX path — **often relative to the volume** |
| 0x0013 | POSIX mount point (`/Volumes/…`) |
| 0xFFFF | end of the alias |

Example (reconstructed):

```
tag 0x0002, len 0x1E : "DISK01:RUSHES:INTERVIEW_01.mov"
tag 0x0012, len 0x17 : "RUSHES/INTERVIEW_01.mov"
tag 0x0013, len 0x0F : "/Volumes/DISK01"
```

**Reconstructing the full path**: if the POSIX path (0x12) does not begin
with `/Volumes`, concatenate it with the mount point (0x13) that follows
it within the same alias (paired within ~300 bytes):
`/Volumes/DISK01` + `RUSHES/INTERVIEW_01.mov` **[verified: paths produced
were accepted for relinking by third-party software]**.

### 10.3 Observed types and creators

| type/creator | meaning |
|--------------|---------------|
| `MooV`/`TVOD` | QuickTime movie (QuickTime Player) |
| `MooV`/`KeyG` | QuickTime movie exported by Final Cut Pro |
| `MooV`/`pRiz` | movie rendered by After Effects |
| `AIFF`/`stlu` | AIFF audio (Soundtrack) |
| `KGWV`/`KeyG` | "KeyGrip WaVe" waveform cache |
| `ATLd`/`pRiz` | linked After Effects project (`.ipr`) |

The `KeyG` creator confirms, independently of the magic, the KeyGrip
lineage.

---

## 11. Automatic identifier-calibration method

Since property ids vary per file (§ 7.1), a generic extractor
must **discover them by statistical role**. The following method
is validated on both endiannesses and the whole corpus **[verified]**.

### 11.1 Global role ids

1. **master id (GUID)**: among the numeric keys of type 0x23, the one
   carrying the most inline GUIDs. The positions of these GUIDs then
   serve as landmarks ("master positions").

2. **name id**: among the numeric keys of type 0x1F in definition
   form, the one that maximizes `frequency × (1 + proximity)`, proximity
   being the number of occurrences followed by a master within 1500
   bytes. (A clip's name immediately precedes its GUID.)

3. **track id** (BE): among the numeric keys of type 0x00 in reference
   form `[01 00]`, the one whose occurrence volume is comparable to the
   number of masters (0.15× to 1.5×) and which appears most often in the
   1500 bytes *preceding* a master — that is, within the body of the
   clipitems. Accepted if proximity > 30%, otherwise absent (LE case,
   § 12).

4. **sequence-marker id**: among the version-00 ints, the one that
   follows a name record within 80 bytes, with the score
   **votes² / global frequency** — the square favors regularity, the
   denominator discards very frequent "noise" ids.

### 11.2 Clipitem temporal ids: anchoring on the ver-02 pairs

The anchor is the most invariant pattern of the format: the **pairs of
version 02 doubles** (source in/out), written consecutively (< 120 bytes
apart):

```
for each ver-02 pair (in, out):
    the 2 preceding ver-01 doubles → candidates (timeline start, end)
    the 1st following ver-01 double → candidate (media duration)
    vote for the quintuple (start, end, in, out, duration)
the majority quintuple gives the file's 5 temporal ids
```

This calibration automatically recovers the columns of the table in § 9.3
on every file, without any file-specific constant.

### 11.3 Timeline reconstruction

Once the ids are calibrated, a simple linear scan of the events (names,
sequence markers, temporal doubles, master GUIDs/references, track
references) sorted by offset suffices:

- a name record followed closely (< 80 bytes) by a sequence marker opens
  a sequence; the first "media duration" following the header (< 900
  bytes, before any clip) is the sequence's duration;
- a "timeline start" ≥ 0 opens a clipitem; end, source in/out,
  master/references aggregate into it (first value of each role); the
  track reference closes the clip;
- plausibility filters: end > start, start < 10⁷ frames, a clip is
  retained only if it has a source in point or a master.

On specimen A, this pipeline names ~59% of the extracted clips; the rest
corresponds to instance GUIDs with no resolvable reference and to
transitions (§ 12).

---

## 12. Unresolved areas and open questions

This section explicitly delimits what the reverse engineering has **not**
established.

1. **Audio clips in little-endian**: in the 2009 LE projects, audio
   clips have a partially different layout (residues of clips without
   source in/out). Video timelines are reliable; LE audio is incomplete.

2. **Track grouping in LE**: in BE, the clips of a track share
   the same track reference; in LE 2009, the observed reference is an id
   **per clip** — either the semantics changed, or the true grouping id
   has not been identified. Export must then reconstruct tracks by
   partitioning the overlaps.

3. **Instance GUIDs without a name-ref**: ~41% of specimen A's clipitems
   carry neither a resolvable master nor a referenced name — only their
   instance GUID. The instance → master link is missing for these clips
   (viewer states, undo copies, transition elements?).

4. **Root section / interface**: the grammar of the large
   interface-state regions (windows, `browser_where`, viewers) is only
   partially parsed; the full recursive parser still relies on heuristic
   resynchronization in those regions.

5. **Header fields**: exact role of the u32 at offset 0x09 (probable
   save counter); precise meaning of the constant UUID (§ 2.3).

6. **Types 0x03, 0x08, 0x0C, 0x0E**: structure known, semantics
   unknown or partial. Likewise for annotation class 0x18 and the
   `a`/`a2` slots of containers and items.

7. **Local u64 item ids**: their allocation rule and any
   cross-referencing use have not been elucidated.

8. **Persistent id allocation**: the space has holes (deleted
   objects, undo) and cannot be reconstructed by counting; only
   interval-based resolution (§ 8) is reliable.

9. **Early versions**: the corpus covers FCP ~5/6 (2008) and 7 (2009).
   FCP 1–3 projects (Mac OS 9) were not examined; the magic and the
   general grammar are probably identical (the format never
   broke backward compatibility), but this is a **[hypothesis]**.

10. **NTSC / drop-frame**: the corpus is entirely PAL (framebase 25).
    The handling of `ntscrate` and drop-frame has not been observed.

---

## 13. Appendix: reference tools and methodology

### 13.1 Tools published with this specification

Standalone Python 3 scripts (no external dependencies), in order of
complexity:

| script | role |
|--------|------|
| `fcp_extract.py` | header, named-key scalar records, numeric-key strings, element table, AliasRecords/media |
| `fcp_items.py` | list of named elements and their properties (durations, dimensions, framebase); identifies the sequences |
| `fcp_full.py` | recursive parser of the complete grammar (containers, items, annotations), with resynchronization; work in progress on the UI regions |
| `fcp_timelines.py` | **reference extractor**: BE + LE (auto-detection), role-based id calibration (§ 11), reference resolution via the table (§ 8), CSV/JSON export |
| `fcp_export_xml.py` | XMEML v4 export ("Final Cut Pro 7 XML") importable into DaVinci Resolve / Premiere Pro: sequences → tracks (greedy partitioning of the overlaps) → clipitems; `<pathurl>` filled in when the AliasRecord provides a path (scan of tags 0x12/0x13); clips without media exported "offline", relinkable |
| `process_vault.sh` | batch processing of an Autosave Vault (last autosave of each project → CSV + XML) |

### 13.2 Reverse-engineering methodology employed

1. **Differential analysis between saves**: comparing two successive
   saves of the same project (Autosave Vault) isolates the stable regions
   (grammar) from the moving regions (counters, ids) — this is how the
   dynamic nature of the numeric keys was discovered (§ 7.1: same
   property, id 0x7E then 0xD9).

2. **Contrasting specimens**: a 2008 PowerPC project and 2009 Intel
   projects revealed the dual endianness and made it possible to separate
   the format's invariants (types, version bytes, role order) from its
   variables (ids, partial layout).

3. **Anchoring on the deepest invariants**: rather than the keys,
   latch onto what the serializer cannot change — the value version
   bytes (ver-01/ver-02 doubles), the definition/reference
   patterns, the C++ class names in cleartext
   (`22CProjectItemTableEntry`).

4. **Resilient parsing**: the full parser logs every failure with
   its hexadecimal context and resynchronizes forward (searching for the
   next point where key+type parse); every skipped region is a documented
   grammar work item.

5. **Validation by internal consistency**: for each extracted sequence,
   compare the clip coverage (max of the end points) to the declared
   duration; an overflow > 25% signals a contaminated clip→sequence
   assignment (undo regions).

6. **External validation**: XMEML export of the timelines then import
   into current editing software; correct durations, positions and
   relink paths constitute the end-to-end proof.

### 13.3 Quick identification recipe (for archiving tools)

```
1. read 8 bytes; require A2 4B 65 79 47 0A 0D 0A            → FCP 1–7 project
2. byte 0x08: 00 → big-endian, 01 → little-endian (confirm with the
   "duration" probe, § 3.2)
3. UUID at 0x0D = 66920820-28C4-11D7-8AE5-003065ECFE98
   (fields byte-swapped in LE)                              → confirmation
4. native u32 at 0x1D = 3                                   → confirmation
```

---

*This specification is provided "as is", for preservation and
interoperability purposes. Final Cut Pro, QuickTime and Mac OS are
trademarks of Apple Inc. No proprietary Apple code or resource is
reproduced in this document.*
