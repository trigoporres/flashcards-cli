🇪🇸 [Leer en español](README.es.md)

# Flashcards CLI — Language learning with spaced repetition

A terminal-based spaced repetition system (FSRS-5) for learning vocabulary from any audio/video source (TV shows, YouTube, TED Talks, podcasts, etc.).

## Full workflow

### 1. Get the transcript

Obtain subtitles or a transcript from the source. It can be:
- YouTube subtitles
- A downloaded .srt file
- A transcript pasted as plain text

### 2. Generate cards with Claude

1. Open a conversation with Claude (or any LLM)
2. Paste the contents of `prompt.txt`
3. Fill in the `[TU NIVEL]`, `[IDENTIFICADOR]`, and `[PEGAR TRANSCRIPCIÓN AQUÍ]` fields
4. Claude returns a CSV ready to import

Save the CSV in `csvs/` to keep things organised. The generated format is:

```csv
id;tipo;palabra_en;palabra_es;frase_en;frase_es;pronunciacion_ipa;registro;colocaciones;acepciones;por_que_ahora;fuente
001;A;to hang on;esperar;Hang on.;Espera un momento.;/hæŋ ɒn/;coloquial;hang on a second|hang on tight;esperar|agarrarse fuerte;;TBBT S01E01
001;B;to hang on;esperar;Hang on.;Espera un momento.;/hæŋ ɒn/;coloquial;hang on a second|hang on tight;esperar|agarrarse fuerte;Phrasal verb frecuente en conversación;TBBT S01E01
```

Each entry generates two cards:
- **Type A (ES→EN)**: Production — you see the Spanish sentence and produce the English
- **Type B (EN→ES)**: Comprehension — you see the English word/phrase and produce the Spanish

### 3. Import into a deck

```bash
python3 flashcards.py import csvs/TBBT_S01E01.csv --deck "TBBT S01E01"
```

Duplicate cards (same `id` + `tipo`) are silently ignored.

### 4. Review

```bash
# Review a specific deck
python3 flashcards.py review --deck "TBBT S01E01"

# Review all decks with due cards
python3 flashcards.py review

# Type A cards only (production ES→EN)
python3 flashcards.py review --tipo-a

# Type B cards only (comprehension EN→ES)
python3 flashcards.py review --tipo-b

# Mute audio
python3 flashcards.py review --mute

# British accent
python3 flashcards.py review --accent uk

# Australian accent
python3 flashcards.py review --accent au
```

When the answer is revealed, the English word/phrase plays automatically twice: first at normal speed, then at 50%. Audio is cached in `.audio_cache/` so it is never downloaded twice.

Available accents (`--accent`):
- `us` — American (default)
- `uk` — British
- `au` — Australian
- `in` — Indian

During a review session:
- **ENTER** — reveal the answer
- **1** — Again (didn't know it)
- **2** — Hard (struggled)
- **3** — Good (got it)
- **4** — Easy (trivial)
- **n** — add/edit a personal note on the card
- **d** — delete card
- **q** — quit

### Enriched cards

Cards display additional linguistic information when the answer is revealed:

- **IPA pronunciation** next to the word
- **Register** (formal, neutral, colloquial, vulgar)
- **Common collocations**
- **Main meanings** (type A)
- **Why now** — usefulness justification (type B)
- **Personal note** — shown if you added one with `n`

### 5. Repeat

Daily reviews take just a few minutes. Difficult cards appear more often; easy ones are spaced further apart.

```bash
python3 flashcards.py review
```

## Other commands

```bash
# Show statistics by deck
python3 flashcards.py stats

# List all decks
python3 flashcards.py decks

# Merge several decks into one (e.g. all episodes of a season)
python3 flashcards.py merge --decks "TBBT S01E01" "TBBT S01E02" --into "TBBT Season 1"

# Show session history, streak, and leeches
python3 flashcards.py history

# Show per-word progress (reviews, state, next review date)
python3 flashcards.py word-stats
python3 flashcards.py word-stats --deck "TBBT S01E01"
```

Merge does not delete the source decks — it copies cards (without duplicating) into the target deck.

### Per-word statistics

`word-stats` shows a table with each word in the deck: how many times it has been reviewed (types A and B separately), learning state, and when it is next due.

- **Nueva** (grey) — never reviewed
- **Aprend.** (yellow) — in the initial learning phase
- **Repaso** (green) — in the spaced repetition cycle (mature)
- **Reapren.** (red) — forgotten, relearning

A word is considered **mature** when both its type A and type B cards are in the Repaso state.

### History and leeches

`history` shows a table with the last 14 days of activity (cards reviewed and accuracy %), current and best streak, and the **leeches**: words marked Again in 2 or more distinct sessions, sorted by frequency.

## CSV format

Separator: `;` (semicolon). 13 columns:

| Column | Description |
|--------|-------------|
| `id` | Sequential number (001, 002, ...) |
| `tipo` | `A` (ES→EN) or `B` (EN→ES) |
| `palabra_en` | English word, phrasal verb, or expression |
| `palabra_es` | The Spanish word as it appears in `frase_es` (used for highlighting) |
| `frase_en` | Sentence from the source where the word appears |
| `frase_en_cloze` | Same sentence with `palabra_en` replaced by `____` |
| `frase_es` | Natural Spanish translation |
| `pronunciacion_ipa` | IPA pronunciation |
| `registro` | formal / neutro / coloquial / vulgar |
| `colocaciones` | Pipe-separated (`\|`) collocations |
| `acepciones` | Pipe-separated (`\|`) meanings |
| `por_que_ahora` | Type B only, empty for type A |
| `fuente` | Source identifier |

## Dependencies

```bash
pip install fsrs gTTS
```

`ffplay` (part of ffmpeg) is used to play audio. It comes pre-installed on most Linux distros.

## File structure

```
flashcards/
├── flashcards.py        # Main script
├── prompt.txt           # Prompt for generating CSVs with Claude
├── README.md
├── README.es.md
├── TODO.md
├── csvs/                # Generated CSVs (not included in public repo)
│   └── *.csv
├── decks/               # Card data and progress (not included in public repo)
│   ├── *.json           # Card decks
│   └── sessions.json    # Review session log
└── .audio_cache/        # TTS audio cache (auto-generated)
```

> `csvs/` and `decks/` contain your personal study data. It is recommended to back them up in a private repo or backup service.
