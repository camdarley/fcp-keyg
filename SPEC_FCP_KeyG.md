# Spécification du format binaire « KeyG » — projets Final Cut Pro 1 à 7

> **Documentation indépendante** — non affiliée à Apple Inc., ni approuvée ou
> sponsorisée par elle. « Final Cut Pro » et « Apple » sont des marques
> d'Apple Inc., citées uniquement pour désigner le format concerné. Cette
> spécification a été établie exclusivement par analyse de fichiers de
> données (aucune décompilation de logiciel, aucun contournement de mesure
> technique de protection), à des fins d'interopérabilité et de préservation
> numérique. Texte sous licence CC BY-SA 4.0.


**Statut : rétro-ingénierie indépendante — juillet 2026**
**Version du document : 1.0**

---

## Avant-propos et conventions

Ce document décrit le format binaire des fichiers de projet de Final Cut Pro
versions 1 à 7 (extension `.fcp`, magic interne « KeyG »). Ce format
propriétaire d'Apple n'a jamais été documenté publiquement. La présente
spécification est le résultat d'une rétro-ingénierie menée sur un corpus de
projets réels : des projets créés en 2008 sur PowerPC (big-endian) et des
projets créés en 2009 sur Mac Intel (little-endian), incluant plusieurs
sauvegardes successives des mêmes projets (Autosave Vault), ce qui a permis
une analyse différentielle.

Elle est publiée à destination de la communauté de la préservation numérique
et de l'archivage audiovisuel : des dizaines de milliers de projets de montage
de la période 1999–2011 ne sont aujourd'hui lisibles par aucun logiciel
maintenu, et l'objectif premier est de permettre l'extraction des timelines
(séquences, clips, points d'entrée/sortie, références médias) vers des formats
ouverts.

### Conventions de notation

- Tous les offsets et constantes sont en hexadécimal, préfixés `0x` ;
  les octets bruts sont notés `A2 4B 65 79`.
- `u8`, `u16`, `u32`, `u64` : entiers non signés de 1, 2, 4, 8 octets ;
  `i32` : entier signé 32 bits ; `f64` : flottant IEEE 754 double précision.
  Sauf mention contraire, ces champs sont dans l'endianness **native du
  fichier** (voir § 3).
- `4cc` : code de quatre caractères ASCII (FourCC), p. ex. `MooV`.
- Chaque affirmation est qualifiée :
  - **[validé]** : vérifié sur plusieurs fichiers indépendants, souvent
    recoupé par un import réussi du résultat dans un logiciel tiers ;
  - **[hypothèse]** : interprétation cohérente avec les observations mais
    non confirmée par recoupement indépendant.
- Les exemples hexadécimaux sont soit transcrits de fichiers réels
  (mention « observé »), soit **reconstruits** à l'identique de structure
  avec des données génériques anonymisées (mention « reconstruit ») :
  noms de clips `INTERVIEW_01`, volumes `DISK01`, etc.
- Les spécimens du corpus sont désignés de façon anonyme :
  - **spécimen A** : projet 2008, PowerPC, big-endian (deux sauvegardes
    successives A₁ et A₂ du même projet) ;
  - **spécimen B** : projet 2009, Mac Intel, little-endian (deux autosaves) ;
  - **spécimens C, D** : autres projets little-endian 2009 issus d'un
    Autosave Vault.

---

## 1. Introduction et contexte historique

### 1.1 De KeyGrip à Final Cut Pro

Final Cut est né chez Macromedia au milieu des années 1990 sous le nom de
code **KeyGrip**. Le projet a été racheté par Apple en 1998 et publié sous le
nom Final Cut Pro 1.0 en 1999. Le nom de code originel a survécu dans le
format de fichier : le magic des projets contient la chaîne « `KeyG` », et le
cache de formes d'onde audio porte le type de fichier `KGWV`
(« **K**ey**G**rip **W**a**V**e »).

Le format « KeyG » a été utilisé sans rupture par toutes les versions de
Final Cut Pro « classique » (1.0, 1999 → 7.0.3, 2009, maintenu jusqu'en
2011), sur Mac OS 8/9 puis Mac OS X, sur PowerPC puis Intel. Final Cut Pro X
(2011) a abandonné entièrement ce format au profit d'une base de données
incompatible ; Apple n'a fourni aucun outil de migration au-delà de FCP X
10.x, et aucun logiciel actuel ne lit les `.fcp` binaires.

### 1.2 Pourquoi ce format compte pour l'archivage

Un fichier `.fcp` contient l'intégralité de la valeur intellectuelle d'un
montage : la liste des médias sources avec leurs chemins d'origine, les
séquences (timelines), la position de chaque plan, les points d'entrée/sortie
dans les rushes, les transitions et effets, les métadonnées de dérushage
(log notes, scènes, prises). Les médias eux-mêmes sont généralement
conservés ; c'est le *montage* qui devient illisible. La possibilité d'en
extraire une EDL ou un XML d'échange (XMEML) rend à nouveau exploitables des
fonds entiers de production des années 2000.

### 1.3 Ce que couvre cette spécification

- l'identification et l'en-tête du fichier (§ 2) ;
- les deux variantes d'endianness et leur détection (§ 3) ;
- la grammaire de sérialisation générale — un arbre de propriétés typées
  (§ 4 à § 6) ;
- le système d'identifiants dynamiques et l'internement des chaînes (§ 7) ;
- la table des éléments du projet et la résolution des références (§ 8) ;
- la structure sémantique des éléments : clips, séquences, clipitems (§ 9) ;
- les références médias (AliasRecords Mac OS) (§ 10) ;
- une méthode de calibration automatique des identifiants, indispensable car
  ceux-ci varient d'un fichier à l'autre (§ 11).

La couverture n'est pas exhaustive (§ 12 liste les zones non résolues), mais
elle suffit à extraire les timelines complètes et à produire un XMEML v4
importable dans des logiciels de montage actuels — ce qui a servi de
validation croisée.

---

## 2. Identification du fichier

### 2.1 Magic

Un projet Final Cut Pro 1–7 commence par les 8 octets suivants **[validé]** :

```
A2 4B 65 79 47 0A 0D 0A
│  └─────────┘ └──────┘
│   "KeyG"      \n \r \n
└─ 0xA2 (octet non ASCII, protège contre les conversions de fins de ligne,
   à la manière du magic PNG)
```

La séquence `0A 0D 0A` (LF CR LF) joue le même rôle que dans le magic PNG :
un fichier transféré en mode texte serait corrompu de façon détectable.

**Attention** : l'extension `.fcp` ne garantit rien. Le corpus contenait un
fichier `.fcp` qui était en réalité un flux vidéo QuickTime brut (frames
codec Animation/RLE sans atome `moov`) mal nommé. Tout outil doit vérifier
le magic avant de parser.

### 2.2 En-tête (51 octets)

L'en-tête occupe les octets `0x00`–`0x32` ; le premier enregistrement de
données commence à l'offset `0x33` **[validé sur les 6 spécimens]**.

| Offset | Taille | Contenu |
|--------|--------|---------|
| 0x00 | 8 | Magic `A2 4B 65 79 47 0A 0D 0A` |
| 0x08 | 1 | Indicateur d'endianness : `00` = big-endian, `01` = little-endian **[validé sur 6 fichiers ; voir § 3]** |
| 0x09 | 4 | u32 natif, variable entre sauvegardes du même projet (croissant : 0xB7 puis 0xC8 sur les deux sauvegardes du spécimen A) — compteur de sauvegarde/sérialisation **[hypothèse]** |
| 0x0D | 16 | UUID, champs stockés en endianness native (u32, u16, u16, puis 8 octets bruts) — voir § 2.3 |
| 0x1D | 4 | u32 = 3 : version du format d'en-tête **[hypothèse ; constant sur tout le corpus]** |
| 0x21 | 8 | u64 = 0 : identifiant de l'objet racine |
| 0x29 | 1 | `01` : slot « a » présent |
| 0x2A | 4 | u32 = 0 : valeur du slot « a » |
| 0x2E | 1 | `01` : compteur de champs présent |
| 0x2F | 4 | u32 `NFIELDS` : nombre d'enregistrements de l'objet racine (0x17 = 23 sur le spécimen A ; 0x14–0x15 sur les spécimens LE) |
| 0x33 | — | Premier enregistrement (clé `subtype`…) |

Les octets `0x21`–`0x32` reproduisent exactement la structure d'un **item de
conteneur** (voir § 6.3) : `[u64 id][01][u32 a][01][u32 nf]`. Autrement dit,
le document entier est sérialisé comme un objet-item d'identifiant 0
possédant `NFIELDS` propriétés racine **[validé structurellement ; la
lecture gloutonne des enregistrements à partir de 0x33 est cohérente avec ce
compte]**.

Dump commenté de l'en-tête (observé, spécimen A₂, big-endian) :

```
0000: A2 4B 65 79 47 0A 0D 0A   magic "KeyG"
0008: 00                        endianness = big-endian
0009: 00 00 00 C8               compteur de sauvegarde = 200 (0xB7=183 dans
                                la sauvegarde précédente du même projet)
000D: 66 92 08 20  28 C4  11 D7 UUID : 66920820-28C4-11D7-
0015: 8A E5  00 30 65 EC FE 98         8AE5-003065ECFE98
001D: 00 00 00 03               version d'en-tête = 3
0021: 00 00 00 00 00 00 00 00   u64 : id de l'objet racine = 0
0029: 01 00 00 00 00            slot a présent, a = 0
002E: 01 00 00 00 17            nfields présent, 23 propriétés racine
0033: 07 73 75 62 74 79 70 65…  1er record : clé "subtype" (len 7)
```

Le même en-tête en little-endian (observé, spécimen B) ne diffère que par
l'octet 0x08 (`01`), l'ordre des octets des entiers, et l'ordre des trois
premiers champs de l'UUID (`20 08 92 66  C4 28  D7 11  8A E5 00 30 65 EC FE
98`, soit le même UUID).

### 2.3 L'UUID d'en-tête : une signature de format, pas un GUID de document

Les 16 octets à l'offset 0x0D forment un UUID version 1 :
`66920820-28C4-11D7-8AE5-003065ECFE98`.

Un UUID v1 encode un horodatage et l'adresse MAC de la machine qui l'a
généré. Ici :

- horodatage : **15 janvier 2003** (période de développement de FCP 4) ;
- nœud : adresse MAC `00:30:65:EC:FE:98`, OUI `00:30:65` = **Apple
  Computer**.

Point crucial : cet UUID est **identique dans les six fichiers du corpus**,
qui proviennent pourtant de machines, d'années et d'architectures
différentes. Ce n'est donc **pas** un GUID de document : c'est une constante
générée une fois pour toutes sur une machine Apple en 2003 et incorporée à
l'application — de fait, une **signature secondaire du format** (ou de sa
révision 2003) **[validé : constant sur 6 fichiers indépendants ; le rôle
exact reste une hypothèse]**. Un outil d'identification peut l'utiliser comme
critère de confirmation, en tenant compte de l'inversion des champs en
little-endian.

Les GUID *réellement* uniques (documents, clips, instances) apparaissent
plus loin dans le corps du fichier, sous forme de chaînes ASCII
`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (type 0x23, § 4.4) ou de 16 octets
bruts dans les annotations (§ 5).

---

## 3. Endianness

### 3.1 Deux variantes du même format

Le format existe en deux ordres d'octets, déterminés par l'architecture de
la machine qui a **créé** le projet **[validé]** :

- **big-endian** : projets PowerPC (observé : 2008) ;
- **little-endian** : projets Mac Intel (observé : 2009).

La grammaire est strictement identique ; seuls les u16/u32/u64/f64 sont
inversés, ainsi que les trois premiers champs de l'UUID d'en-tête. Les
tailles de chaînes, les octets de version et les flags (u8) sont inchangés.

### 3.2 Détection

Deux méthodes, à combiner :

1. **Octet 0x08 de l'en-tête** : `00` = BE, `01` = LE. Simple, mais validé
   seulement sur six fichiers — à traiter comme un indice **[hypothèse]**.

2. **Sondage statistique du motif d'un enregistrement connu** **[validé,
   méthode robuste]** : la clé Pascal `duration` suivie du type 0x04
   (double) apparaît de nombreuses fois dans tout projet. On compte les
   occurrences des deux encodages possibles du type :

   ```
   BE : 08 "duration" 00 00 00 04
   LE : 08 "duration" 04 00 00 00
   ```

   Le plus fréquent gagne. En secours (fichier sans clé `duration`), on
   compte les motifs de définition de chaîne type 0x1F :
   `00 00 00 1F 01 01` (BE) contre `1F 00 00 00 01 01` (LE).

---

## 4. Modèle de données général : arbre de propriétés sérialisé

### 4.1 Vue d'ensemble

Le corps du fichier est un unique **arbre de propriétés** sérialisé en
profondeur : un objet racine (id 0, § 2.2) contenant des enregistrements
(*records*), dont certains sont des conteneurs contenant des objets (*items*)
qui contiennent eux-mêmes des records, récursivement. Il n'y a ni table
d'offsets ni index : le fichier se lit séquentiellement, et la position d'une
donnée n'est connue qu'en parsant tout ce qui la précède. (Une exception
partielle : la table des éléments, § 8, fournit un index *logique* — mais en
identifiants, pas en offsets.)

### 4.2 L'enregistrement (record)

```
record := [clé] [type:u32] [payload] [annotation]
```

- **clé** : deux encodages **[validé]** :

  ```
  [len:u8 > 0][len octets ASCII]     clé nommée   ex.  05 "width"
  [00][id:u32]                       clé numérique ex. 00 00 00 00 1D
  ```

  Les clés nommées sont des chaînes Pascal courtes (longueur observée
  ≤ 0x1C, caractères ASCII imprimables : lettres, chiffres, `_`, espace).
  Les clés numériques référencent un nom interné (§ 7) ; leurs valeurs
  utiles tiennent sur 16 bits, mais le champ fait bien 4 octets.

- **type** : u32, désigne le type du payload (§ 4.3).

- **payload** : dépend du type. La plupart des scalaires commencent par un
  octet de **version** (`ver`) qui module l'interprétation sémantique de la
  valeur (voir les doubles ver-01/ver-02, § 9.3).

- **annotation** : présente après *chaque* valeur (§ 5). Au minimum un
  octet `00`.

### 4.3 Système de types

Types observés **[validé pour la structure ; la sémantique de 0x03, 0x08,
0x0C et 0x0E est partielle]** :

| Type | Payload | Description |
|------|---------|-------------|
| 0x00 | voir § 6 | conteneur / objet / référence d'objet |
| 0x01 | `[ver:u8][i32]` | entier 32 bits signé |
| 0x03 | `[ver:u8][8 octets]` | valeur 64 bits (rôle non déterminé) |
| 0x04 | `[ver:u8][f64]` | double — utilisé pour tous les temps, en frames |
| 0x05 | `[ver:u8][u8]` | booléen |
| 0x08 | `[ver:u8][u32]` | entier non signé (rôle non déterminé) |
| 0x0B | `[ver:u8][len:u32][octets]` | chaîne « ancienne », MacRoman/ASCII |
| 0x0C | `[f1:u8][f2:u8][u32][u32]` | paire d'entiers |
| 0x0E | `[ver:u8][4 × u32]` | rectangle (4 coordonnées) |
| 0x1F | voir § 4.4 | chaîne UTF-8 internée (définition ou référence) |
| 0x23 | voir § 4.4 | chaîne-GUID (`XXXXXXXX-XXXX-…`), internée |

Tout u32 de type > 0x30 rencontré en position de type signale une
désynchronisation du parseur (heuristique de resynchronisation, § 13.2).

### 4.4 Chaînes : deux générations, et un mécanisme définition/référence

- **Type 0x0B** (héritage Mac OS classique) : `[ver][len:u32][octets]`,
  encodage MacRoman ou ASCII. Utilisé pour des valeurs anciennes
  (ex. la qualité de rendu `"final"`).

- **Type 0x1F** (chaîne moderne) : encodage UTF-8 (les accents des noms
  français d'effets — « Fondu enchaîné », « Séquence » — y sont encodés en
  UTF-8) **[validé]**. Deux formes :

  ```
  [01][01][len:u32][octets UTF-8]    définition — la chaîne est internée
                                     et consomme un id persistant (§ 7)
  [01][00][u32 réf]                  référence à une chaîne déjà internée
  ```

- **Type 0x23** (chaîne-GUID) : la valeur est un GUID sérialisé en ASCII
  (36 caractères + variantes). Formes observées :

  ```
  [00|01][01][u32][len:u32][texte GUID]   inline (définition)
  [01][00][u32 réf]                       référence
  [00][00]…                               vide/nulle
  ```

En pratique, une stratégie de décodage robuste des chaînes est : tenter
UTF-8, puis MacRoman, puis Latin-1 avec remplacement.

### 4.5 Exemples commentés

**Record entier, clé numérique (reconstruit — framebase = 25 i/s, PAL) :**

```
00                 clé numérique
00 00 00 1B        id de clé = 0x1B ("framebase" dans ce fichier, cf. § 7)
00 00 00 01        type 0x01 = int32
01                 version de la valeur
00 00 00 19        valeur = 25
00                 pas d'annotation
```

**Record double, clé nommée, avec annotation (observé, spécimen A, offset
0x1AE) :**

```
08 64 75 72 61 74 69 6F 6E    clé Pascal : len 8, "duration"
00 00 00 04                   type 0x04 = double
01                            version 01
40 C2 7A 80 00 00 00 00       f64 = 9461.0   (frames ; 9461/25 → 6'18"11)
01                            annotation présente
00 00 00 01                   n = 1
00 00 00 18                   classe d'annotation = 0x18
00                            flag 0 : forme « référence d'id »
00 00 00 17                   → id numérique 0x17 : c'est ainsi que le
                              fichier lie "duration" ↔ clé 0x17 (§ 5, § 7)
```

**Record chaîne 0x1F, clé numérique (reconstruit — nom de clip) :**

```
00                 clé numérique
00 00 00 1D        id = 0x1D (rôle "nom" dans ce fichier)
00 00 00 1F        type 0x1F = chaîne UTF-8
01 01              définition (chaîne internée : consomme un id persistant)
00 00 00 0C        longueur = 12
49 4E 54 45 52 56 49 45 57 5F 30 31    "INTERVIEW_01"
00                 pas d'annotation
```

---

## 5. Annotations de valeur

Chaque payload est suivi d'un bloc d'annotation **[validé]** :

```
annotation := [00]                                   aucune
            | [01][u32 n][u32 classe][attaché]       annotation présente

attaché    := [00][u32 réf]                          forme « référence »
            | [01][ver:u8][GUID 16 octets][conteneur] forme « objet inline »
```

La seule classe observée est `0x18`. Le champ `n` vaut 1 dans tous les cas
analysés. **[la sémantique précise de n et classe reste une hypothèse]**

Les deux formes ont des rôles distincts :

1. **Forme référence** `[00][u32 X]` : X est un identifiant dans l'espace
   d'ids persistants du fichier (§ 7). C'est le mécanisme qui relie une
   **clé nommée à son id numérique** : le record `duration` de l'exemple
   § 4.5 est annoté `→ 0x17`, et par la suite le fichier utilisera la clé
   numérique `[00][00 00 00 17]` pour dire « duration ». Ces annotations
   servent aussi d'**ancres** entre un élément et sa plage d'identifiants
   dans la table du projet (§ 8.3).

   Exemple observé (spécimen A, offset 0x1A0) :

   ```
   01              annotation présente
   00 00 00 01     n = 1
   00 00 00 18     classe 0x18
   00              forme référence
   00 00 00 15     id 0x15 (lie la clé précédente à l'id 0x15)
   ```

2. **Forme objet inline** `[01][ver][GUID 16 octets][conteneur]` : un objet
   annexe est attaché à la valeur, identifié par un GUID de 16 octets bruts
   (ici en binaire, contrairement aux GUID-chaînes du type 0x23), suivi d'un
   conteneur complet (§ 6) portant le corps de l'objet.

Le motif binaire de la forme référence est un excellent point d'ancrage pour
un scanner : `01 00 00 00 01 00 00 00 18 00` en BE,
`01 01 00 00 00 18 00 00 00 00` en LE.

---

## 6. Conteneurs et objets

### 6.1 Formes du type 0x00

Un record de type 0x00 introduit un conteneur, avec quatre formes
**[validé]** :

```
conteneur := [01][00][u32 réf]                       référence à un objet
                                                     existant (id persistant)
           | [01][01][u32 n>0]  n × item             liste de n items
           | [01][01][u32 0][01][u32 classe]         objet vide typé
           | [01][01][u32 0][00][u32 x]              objet nul / référence

puis, dans tous les cas, slots optionnels :
             [fa:u8]  si fa=01 : [u32 a2]
             [fb:u8]  si fb=01 : [u32 nf2] puis nf2 records
```

### 6.2 La forme référence `[01][00]`

`[01][00][u32 R]` désigne un objet déjà défini ailleurs, via l'espace d'ids
persistants (§ 7). C'est notamment la forme des **références de piste** des
clipitems (§ 9.3) : tous les clips d'une même piste d'une séquence portent
un record conteneur-référence avec le même `R` **[validé en BE ; différent
en LE, voir § 12]**.

### 6.3 Items

Chaque item d'une liste `[01][01][u32 n]` a la forme **[validé]** :

```
item := [00]                        item absent (slot nul)
      | [01]                        item présent :
        [u64 id-local]              identifiant 64 bits local au flux
        [f1:u8] si f1=01 : [u32 a]  slot « a » optionnel
        [f2:u8] si f2=01 : [u32 nf] compteur de champs optionnel
        nf × record                 les propriétés de l'objet
```

Points importants :

- Les **id u64 des items sont locaux** : ils ne participent pas à l'espace
  d'ids persistants u32 utilisé par les références `[01 00]` et les
  annotations. Les deux espaces d'identifiants sont disjoints **[validé]**.
- `nf` (NFIELDS) donne le nombre exact de records du corps de l'item —
  c'est ce qui permet un parsing récursif borné. L'objet racine du fichier
  suit exactement cette forme (§ 2.2).
- La fin d'une liste de records lue « gloutonnement » (sans nf connu) se
  détecte par échec de parsing : l'octet suivant ne forme pas une clé/type
  valide.

### 6.4 Exemple : début du conteneur `clipList` (observé, spécimen A)

```
08 63 6C 69 70 4C 69 73 74     clé Pascal "clipList" (len 8)
00 00 00 00                    type 0x00 = conteneur
01 01                          forme liste
00 00 00 01                    n = 1 item
00                             (octets de préambule dont l'interprétation
00 00 00 20                     exacte n'est pas arrêtée ; l'octet 0x20 et
                                le u32 qui suit précèdent systématiquement
                                le compteur d'entrées)          [hypothèse]
00 00 03 76                    nombre d'entrées de table = 886
01 00 00 00 18                 chaîne : définition, longueur 0x18 = 24
32 32 43 50 72 6F 6A 65 63 74  "22CProjectItemTableEntry"
49 74 65 6D 54 61 62 6C 65      (nom de classe C++ préfixé par sa longueur
45 6E 74 72 79                   décimale "22", à la façon du name mangling)
…                              suite de la 1re entrée (§ 8.2)
```

---

## 7. Le système d'identifiants : ids dynamiques, ids persistants, internement

C'est le point le plus contre-intuitif du format, et la principale cause
d'échec d'un parseur naïf.

### 7.1 Les ids de clés numériques sont propres à chaque fichier

Les clés numériques (`[00][u32 id]`) ne sont **pas** un vocabulaire fixe du
format : ce sont des **références vers des noms de clés internés au fil de
l'écriture du fichier**. La première fois qu'une propriété est écrite, elle
l'est sous sa clé nommée (chaîne Pascal), avec une annotation
`→ id` (§ 5) ; les écritures suivantes utilisent la clé numérique. L'id
attribué dépend donc de **l'ordre d'écriture**, qui dépend de l'historique
du projet **[validé]**.

Exemple mesuré : la clé portant le GUID master d'un clipitem vaut **0x7E**
dans une sauvegarde d'un projet, **0xD9** dans la sauvegarde suivante du
*même* projet, et **0xCA** dans un projet little-endian de 2009. De même le
rôle « nom d'élément » vaut 0x1D dans le spécimen A mais d'autres valeurs
ailleurs.

Conséquence : **aucune constante de clé numérique ne doit être codée en
dur**. Un extracteur doit soit reconstruire la table nom→id en suivant les
annotations de liaison (§ 5), soit découvrir les ids **par rôle
statistique** (§ 11). Les tables d'ids données au § 9 sont donc des
*exemples par fichier*, pas des constantes du format.

### 7.2 L'espace d'ids persistants

Les références u32 (chaînes `[01 00]`, conteneurs-références, annotations
forme référence) vivent dans un espace d'**ids persistants**, alloués sur
toute la vie du projet, chaque définition (`[01 01]` d'une chaîne 0x1F/0x23,
objet inline d'annotation…) consommant un id. Ces ids **ne sont pas
reconstructibles par simple comptage** des définitions dans le fichier : des
ids sont « brûlés » par des objets supprimés, des zones d'undo, des copies —
l'espace est troué **[validé : le comptage naïf diverge rapidement]**.

La résolution pratique d'une référence passe par la table des éléments du
projet, qui délimite des plages d'ids par élément (§ 8).

### 7.3 Résumé du motif définition/référence

| Contexte | Définition (consomme un id) | Référence |
|----------|------------------------------|-----------|
| chaîne 0x1F | `[01][01][len][texte]` | `[01][00][u32]` |
| chaîne-GUID 0x23 | `[0x][01][u32][len][texte]` | `[01][00][u32]` |
| conteneur 0x00 | `[01][01][n]…` | `[01][00][u32]` |
| annotation | `[01][ver][GUID][conteneur]` | `[00][u32]` |

---

## 8. La table `CProjectItemTableEntry` et la résolution des références

### 8.1 Rôle

Le record racine `clipList` (§ 6.4) contient la table des éléments du projet
(clips, séquences, chutiers) : une entrée `CProjectItemTableEntry` par
élément, plus des entrées `CProjectItemNestEntry` pour les imbrications
(séquence dans séquence) **[validé]**. Cette table sert d'index *logique* :
elle associe à chaque élément une **plage de l'espace d'ids persistants**.

### 8.2 Structure d'une entrée

Chaque entrée est écrite ainsi **[validé pour les champs v1/v2 ; les 4
octets intermédiaires sont interprétés comme flags/version]** :

```
01 [u32 = 0x18] "22CProjectItemTableEntry"   nom de classe (24 octets),
                                             1re occurrence ; les suivantes
                                             peuvent être des références
[u16][u16]                                   flags/version (valeurs 0/1)
[f1:u8][u32 v1]                              si f1=01 : v1 nul/absent
[f2:u8][u32 v2]                              si f2=01 : v2 nul/absent
```

`v1` et `v2` sont deux positions dans l'espace d'ids persistants.
Première entrée observée du spécimen A : `v1 = 0x10`, `v2 = 0x37`.

### 8.3 Sémantique : plages d'ids hiérarchiques

**[validé par recoupement multiple]** :

- une entrée « fine » (0 < v2 − v1 < ~500) marque le **début de la plage
  d'ids** d'un élément feuille (clip, séquence). En triant les v1 fins
  croissants, l'élément i possède l'intervalle `[v1_i, v1_{i+1})` ;
- les entrées « larges » (ex. un chutier couvrant (10, 2100)) **englobent**
  les plages de leurs enfants : la table encode la hiérarchie
  chutier → éléments par inclusion d'intervalles ;
- l'intervalle d'un élément est **ancré à son nom** par les annotations de
  forme référence `[01][u32 1][u32 0x18][00][u32 X]` présentes dans son
  enregistrement : les X observés dans la fenêtre qui suit le record-nom
  d'un élément tombent dans l'intervalle de cet élément. Un vote majoritaire
  (plusieurs annotations par élément) rend l'ancrage robuste.

### 8.4 Algorithme de résolution d'une référence

Pour résoudre une référence persistante R (master d'un clip, nom référencé,
transition…) vers un nom d'élément :

```
1. Collecter les v1 des entrées fines de la table ; trier → bornes
   d'intervalles.
2. Pour chaque record-nom d'élément (rôle « nom », § 11), scanner la fenêtre
   suivante (~1500 octets) pour les annotations [ … 0x18][00][u32 X] ;
   attribuer par vote l'intervalle contenant X au nom.
   (Exclure les chaînes de type identifiant inverse « com.apple.… » qui ne
   sont pas des noms d'éléments.)
3. résoudre(R) = nom de l'intervalle contenant R
   (recherche dichotomique sur les bornes).
```

Validations effectuées **[validé]** : les masters référencés par les clips
d'une séquence `SEQ_INTERVIEW_01` se résolvent vers le clip source
`INTERVIEW_01_CAM2` du chutier ; les références portées par les transitions
se résolvent vers l'effet « Cross fade 0 dB » ; les séquences imbriquées se
résolvent vers la séquence fille correcte.

---

## 9. Structure sémantique des éléments

### 9.1 Organisation du flux d'items

Le flux principal d'items sérialise, dans l'ordre **[validé]** :

1. les **masters** : les clips du chutier, chacun accompagné d'environ
   trois pseudo-clips d'état de visionneuse (viewer) ;
2. les **séquences**, chacune suivie de ses **clipitems** (~1 Ko par clip).

L'attribution d'un clipitem à sa séquence se fait par la position dans le
flux : dernier en-tête de séquence rencontré. Cette règle est fiable mais
doit être **validée par cohérence** couverture ≈ durée (§ 13.3), car les
zones d'undo et les copies internes peuvent faire déborder des clips
étrangers dans la fenêtre d'une séquence **[validé, avec cette réserve]**.

### 9.2 Propriétés d'élément et en-tête de séquence

Ids de propriétés relevés sur le spécimen A (rappel § 7.1 : valeurs propres
à ce fichier) :

| id (spécimen A) | rôle | type |
|------|------|------|
| 0x11 | in (frames) | 0x04 |
| 0x16 | out (frames) | 0x04 |
| 0x17 | durée (frames) | 0x04 |
| 0x1B | base de temps (25 = PAL) | 0x01 |
| 0x1D | nom de l'élément | 0x1F |
| 0x22 | marqueur d'en-tête de séquence (int ver-00) | 0x01 |
| 0x23 | state (1500 pour une séquence) | 0x01 |
| 0x25 | qualité de rendu (`"final"`) | 0x0B |
| 0x2A | largeur | 0x01 |
| 0x2B | hauteur | 0x01 |

Un **en-tête de séquence** suit le motif (ids du spécimen A) **[validé]** :

```
[0x1D nom de la séquence]
[0x22 int, version 00]            ← marqueur discriminant (§ 11)
[0x23 state = 1500]
[0x25 "final"]                    qualité de rendu
[0x2A largeur][0x2B hauteur]      ex. 720 × 576
[0x2C conteneur][0x2F item u64]   objet timeline (nf champs)
[0x11 = -1][0x16 = -1]            in/out non définis au niveau séquence
[0x17 durée totale en frames]
[0x18][0x19][0x1A]
[0x1B framebase][0x1C]
```

Un temps à −1 signifie « non défini ». Les durées/temps sont des f64 en
frames ; le timecode s'obtient en divisant par la base (`framebase`,
25 en PAL).

Clés nommées observées à la racine et dans les éléments : `subtype`,
`NOUNDO`, `RUNTIME`, `viewers`, `children`, `browser_where`, `mainDict`
(sous-clés `in`/`out`/`duration`/`marked`/`position`/`tcbase`/`framebase`/
`ntscrate`/`name`), `media`, `vidm` (`width`/`height`), `track`, `clip`,
`filters`, `masterClips`, `master` (GUID), `file`, `reader` (`"QTMRead"`),
`sequence_count`, `clipList`.

### 9.3 Clipitems

Un clipitem (occurrence d'un clip dans une timeline) porte **[validé]** :

- **début / fin timeline** : deux doubles **version 01**, en frames ;
- **in / out source** : deux doubles **version 02** (position dans le
  média source), écrits en paire consécutive ;
- **durée du média** source : un double version 01 ;
- **framebase** : int ;
- **GUID d'instance** : type 0x23, inline à la première occurrence puis par
  référence. Attention : ce GUID identifie **l'instance** du clip dans la
  timeline, pas le master. Le master s'obtient par la référence persistante
  associée (résolution § 8.4) ou par le nom référencé ;
- **référence de piste** : record conteneur-référence `[01 00][u32
  id-piste]` — tous les clips d'une même piste partagent le même id (BE) ;
- divers : une référence GUID du projet, une paire 0x0C, quatre ints
  consécutifs de rôle non déterminé.

L'octet de **version des doubles est porteur de sémantique** : c'est lui qui
distingue les temps timeline (ver 01) des temps source (ver 02), et c'est
l'invariant le plus stable du format à travers les années et les
endianness **[validé]** — d'où son usage comme ancre de calibration (§ 11).

Tableau comparatif des ids observés (illustre § 7.1 — mêmes rôles, mêmes
types, même ordre, ids différents) :

| rôle | spécimen A (BE, 2008) | spécimen B (LE, 2009) |
|------|------------------------|------------------------|
| début timeline | 0x11 (double ver 01) | 0x0B |
| fin timeline | 0x16 (double ver 01) | 0x10 |
| in source | 0xBB (double ver 02) | 0x32 |
| out source | 0xBC (double ver 02) | 0x33 |
| durée média | 0x17 (double ver 01) | 0x11 (!) |
| framebase | 0x1B (int) | 0x15 |
| GUID d'instance | 0xD9 (type 0x23) | 0xCA |
| marqueur séquence | 0x22 (int ver 00) | 0x1C (0x21 sur le spécimen C) |

Le « 0x11 » qui signifie *début timeline* dans un fichier et *durée média*
dans un autre montre qu'une table de constantes est vouée à l'échec.

### 9.4 Transitions, effets, générateurs

Les transitions sont des éléments de timeline sans in/out source ; leurs
références se résolvent vers le nom de l'effet (ex. « Cross fade 0 dB »,
« Fondu enchaîné ») via la table (§ 8.4). Les définitions de transitions
embarquent le **code source FXScript complet** de l'effet (identifiant de
script et corps du programme, ex. « Cross Dissolve ») ; ce code est
extractible tel quel du fichier, mais étant un code source propriétaire
d'Apple, il n'est pas reproduit dans cette spécification **[validé pour la
présence ; contenu non reproduit]**.

### 9.5 Données annexes

- **Interface** : les définitions de colonnes du chutier (`lognote`,
  `scene`, `take`, `comment1`–`comment6`, `good`, `labelColor`…) sont
  stockées, répétées par fenêtre ouverte.
- **Fichiers de rendu** : des flux « render file » listent les noms des
  fichiers de rendu rattachés aux séquences (ex.
  `sequence_v1-FIN-0000043a`).
- **sequence_count** : compteur racine du nombre de séquences.

---

## 10. Références médias : AliasRecords Mac OS

### 10.1 Contexte

Chaque média lié est décrit par un **AliasRecord** Mac OS classique
(version 2) — la structure système utilisée par le Finder pour les alias, à
résolution multiple (identifiants de volume/fichier, chemins HFS et POSIX).
Le record est précédé du couple type/créateur du fichier visé **[validé]** :

```
[type 4cc][creator 4cc][00 01][00 02] …corps de l'alias…
```

### 10.2 Corps de l'alias : entrées taguées

Après une courte partie fixe, l'alias est une suite d'entrées
`[tag:u16][len:u16][données][pad à 2 octets]`, terminée par le tag `0xFFFF`.
Tags observés dans les projets **[validé]** :

| tag | contenu |
|-----|---------|
| 0x0000 | nom du dossier parent (chaîne Pascal) |
| 0x0001 | identifiants de dossiers (u32) |
| 0x0002 | chemin HFS absolu `Volume:dossier:fichier` (MacRoman) |
| 0x000E | nom du fichier en UTF-16 |
| 0x000F | nom du volume en UTF-16 |
| 0x0010, 0x0011 | dates (epoch Mac : secondes depuis 1904-01-01) |
| 0x0012 | chemin POSIX — **souvent relatif au volume** |
| 0x0013 | point de montage POSIX (`/Volumes/…`) |
| 0xFFFF | fin de l'alias |

Exemple (reconstruit) :

```
tag 0x0002, len 0x1E : "DISK01:RUSHES:INTERVIEW_01.mov"
tag 0x0012, len 0x17 : "RUSHES/INTERVIEW_01.mov"
tag 0x0013, len 0x0F : "/Volumes/DISK01"
```

**Reconstruction du chemin complet** : si le chemin POSIX (0x12) ne commence
pas par `/Volumes`, le concaténer au point de montage (0x13) qui le suit
dans le même alias (apparié à moins de ~300 octets) :
`/Volumes/DISK01` + `RUSHES/INTERVIEW_01.mov` **[validé : chemins produits
acceptés au relink par des logiciels tiers]**.

### 10.3 Types et créateurs observés

| type/creator | signification |
|--------------|---------------|
| `MooV`/`TVOD` | film QuickTime (lecteur QuickTime Player) |
| `MooV`/`KeyG` | film QuickTime exporté par Final Cut Pro |
| `MooV`/`pRiz` | film rendu par After Effects |
| `AIFF`/`stlu` | audio AIFF (Soundtrack) |
| `KGWV`/`KeyG` | cache de forme d'onde « KeyGrip WaVe » |
| `ATLd`/`pRiz` | projet After Effects lié (`.ipr`) |

Le créateur `KeyG` confirme, indépendamment du magic, la filiation KeyGrip.

---

## 11. Méthode de calibration automatique des identifiants

Puisque les ids de propriétés varient par fichier (§ 7.1), un extracteur
générique doit les **découvrir par rôle statistique**. La méthode suivante
est validée sur les deux endianness et l'ensemble du corpus **[validé]**.

### 11.1 Ids de rôle globaux

1. **id master (GUID)** : parmi les clés numériques de type 0x23, celle qui
   porte le plus de GUID inline. Les positions de ces GUID servent ensuite
   de repères (« positions masters »).

2. **id nom** : parmi les clés numériques de type 0x1F en forme définition,
   celle qui maximise `fréquence × (1 + proximité)`, la proximité étant le
   nombre d'occurrences suivies d'un master à moins de 1500 octets. (Le nom
   d'un clip précède immédiatement son GUID.)

3. **id piste** (BE) : parmi les clés numériques de type 0x00 en forme
   référence `[01 00]`, celle dont le volume d'occurrences est comparable au
   nombre de masters (0,15× à 1,5×) et qui apparaît le plus souvent dans les
   1500 octets *précédant* un master — c'est-à-dire dans le corps des
   clipitems. Accepté si > 30 % de proximité, sinon absent (cas LE, § 12).

4. **id marqueur de séquence** : parmi les ints à version 00, celui qui
   suit un record-nom à moins de 80 octets, avec le score
   **votes² / fréquence globale** — le carré favorise la régularité, le
   dénominateur écarte les ids « bruit » très fréquents.

### 11.2 Ids temporels du clipitem : ancrage sur les paires ver-02

L'ancre est le motif le plus invariant du format : les **paires de doubles
version 02** (in/out source), écrites consécutivement (< 120 octets
d'écart) :

```
pour chaque paire ver-02 (in, out) :
    les 2 doubles ver-01 qui précèdent → candidats (début, fin timeline)
    le 1er double ver-01 qui suit      → candidat (durée média)
    vote pour le quintuplet (début, fin, in, out, durée)
le quintuplet majoritaire donne les 5 ids temporels du fichier
```

Cette calibration retrouve automatiquement les colonnes du tableau § 9.3
sur chaque fichier, sans aucune constante spécifique.

### 11.3 Reconstruction des timelines

Une fois les ids calibrés, un simple scan linéaire des événements (noms,
marqueurs de séquence, doubles temporels, GUID/références master, références
de piste) triés par offset suffit :

- un record-nom suivi de près (< 80 octets) d'un marqueur de séquence ouvre
  une séquence ; la première « durée média » qui suit l'en-tête (< 900
  octets, avant tout clip) est la durée de la séquence ;
- un « début timeline » ≥ 0 ouvre un clipitem ; fin, in/out source,
  master/références s'y agrègent (première valeur de chaque rôle) ; la
  référence de piste clôt le clip ;
- filtres de vraisemblance : fin > début, début < 10⁷ frames, clip retenu
  seulement s'il a un in source ou un master.

Sur le spécimen A, cette chaîne nomme ~59 % des clips extraits ; le reste
correspond à des GUID d'instance sans référence résoluble et aux
transitions (§ 12).

---

## 12. Zones non résolues et questions ouvertes

Cette section délimite explicitement ce que la rétro-ingénierie n'a **pas**
établi.

1. **Clips audio en little-endian** : dans les projets LE 2009, les clips
   audio ont un layout partiellement différent (résidus de clips sans in/out
   source). Les timelines vidéo sont fiables ; l'audio LE est incomplet.

2. **Groupement de pistes en LE** : en BE, les clips d'une piste partagent
   une même référence de piste ; en LE 2009, la référence observée est un id
   **par clip** — soit la sémantique a changé, soit le véritable id de
   groupement n'a pas été identifié. L'export doit alors reconstruire des
   pistes par partition des chevauchements.

3. **GUID d'instance sans name-ref** : ~41 % des clipitems du spécimen A ne
   portent ni master résoluble ni nom référencé — seulement leur GUID
   d'instance. Le chaînon instance → master manque pour ces clips (états de
   visionneuse, copies d'undo, éléments de transition ?).

4. **Section racine / interface** : la grammaire des grandes zones d'état de
   l'interface (fenêtres, `browser_where`, viewers) n'est parsée que
   partiellement ; le parseur récursif complet s'appuie encore sur une
   resynchronisation heuristique dans ces zones.

5. **Champs d'en-tête** : rôle exact du u32 à l'offset 0x09 (compteur de
   sauvegarde probable) ; signification précise de l'UUID constant (§ 2.3).

6. **Types 0x03, 0x08, 0x0C, 0x0E** : structure connue, sémantique
   inconnue ou partielle. Idem pour la classe d'annotation 0x18 et les
   slots `a`/`a2` des conteneurs et items.

7. **Ids u64 locaux des items** : leur règle d'allocation et leur éventuel
   usage croisé n'ont pas été élucidés.

8. **Allocation des ids persistants** : l'espace est troué (objets
   supprimés, undo) et non reconstructible par comptage ; seule la
   résolution par intervalles (§ 8) est fiable.

9. **Versions anciennes** : le corpus couvre FCP ~5/6 (2008) et 7 (2009).
   Les projets FCP 1–3 (Mac OS 9) n'ont pas été examinés ; le magic et la
   grammaire générale sont probablement identiques (le format n'a jamais
   cassé la compatibilité ascendante), mais c'est une **[hypothèse]**.

10. **NTSC / drop-frame** : le corpus est intégralement PAL (framebase 25).
    Le traitement de `ntscrate` et du drop-frame n'a pas été observé.

---

## 13. Annexe : outils de référence et méthodologie

### 13.1 Outils publiés avec cette spécification

Scripts Python 3 autonomes (aucune dépendance externe), dans l'ordre de
complexité :

| script | rôle |
|--------|------|
| `fcp_extract.py` | en-tête, enregistrements scalaires à clé nommée, chaînes à clé numérique, table des éléments, AliasRecords/médias |
| `fcp_items.py` | liste des éléments nommés et de leurs propriétés (durées, dimensions, framebase) ; repère les séquences |
| `fcp_full.py` | parseur récursif de la grammaire complète (conteneurs, items, annotations), avec resynchronisation ; en chantier sur les zones UI |
| `fcp_timelines.py` | **extracteur de référence** : BE + LE (auto-détection), calibration des ids par rôle (§ 11), résolution des références par la table (§ 8), export CSV/JSON |
| `fcp_export_xml.py` | export XMEML v4 (« XML Final Cut Pro 7 ») importable dans DaVinci Resolve / Premiere Pro : séquences → pistes (partition gloutonne des chevauchements) → clipitems ; `<pathurl>` renseigné quand l'AliasRecord fournit un chemin (scan des tags 0x12/0x13) ; clips sans média exportés « offline » relinkables |
| `process_vault.sh` | traitement en lot d'un Autosave Vault (dernier autosave de chaque projet → CSV + XML) |

### 13.2 Méthodologie de rétro-ingénierie employée

1. **Analyse différentielle entre sauvegardes** : comparer deux sauvegardes
   successives du même projet (Autosave Vault) isole les zones stables
   (grammaire) des zones mouvantes (compteurs, ids) — c'est ainsi qu'a été
   découverte la nature dynamique des clés numériques (§ 7.1 : même
   propriété, id 0x7E puis 0xD9).

2. **Spécimens contrastés** : un projet PowerPC 2008 et des projets Intel
   2009 ont révélé l'endianness double et permis de séparer les invariants
   du format (types, octets de version, ordre des rôles) de ses variables
   (ids, layout partiel).

3. **Ancrage sur les invariants les plus profonds** : plutôt que les clés,
   se caler sur ce que le sérialiseur ne peut pas changer — les octets de
   version des valeurs (doubles ver-01/ver-02), les motifs de
   définition/référence, les noms de classes C++ en clair
   (`22CProjectItemTableEntry`).

4. **Parsing résilient** : le parseur complet consigne chaque échec avec
   son contexte hexadécimal et resynchronise en avant (recherche du prochain
   point où clé+type parsent) ; chaque zone sautée est un chantier de
   grammaire documenté.

5. **Validation par cohérence interne** : pour chaque séquence extraite,
   comparer la couverture des clips (max des fins) à la durée déclarée ;
   un débordement > 25 % signale une attribution clip→séquence contaminée
   (zones d'undo).

6. **Validation externe** : export XMEML des timelines puis import dans des
   logiciels de montage actuels ; les durées, positions et chemins de
   relink corrects constituent la preuve de bout en bout.

### 13.3 Recette d'identification rapide (pour outils d'archivage)

```
1. lire 8 octets ; exiger A2 4B 65 79 47 0A 0D 0A          → projet FCP 1–7
2. octet 0x08 : 00 → big-endian, 01 → little-endian (confirmer par le
   sondage "duration", § 3.2)
3. UUID à 0x0D = 66920820-28C4-11D7-8AE5-003065ECFE98
   (champs inversés en LE)                                  → confirmation
4. u32 natif à 0x1D = 3                                     → confirmation
```

---

*Cette spécification est fournie « en l'état », à des fins de préservation
et d'interopérabilité. Final Cut Pro, QuickTime et Mac OS sont des marques
d'Apple Inc. Aucun code ni ressource propriétaire d'Apple n'est reproduit
dans ce document.*
