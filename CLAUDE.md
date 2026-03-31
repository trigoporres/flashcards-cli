# Project conventions

## Language

- **README, issues, PRs, commit messages, code comments, docstrings** → always in English
- **`prompt.txt` and card content** (frase_es, acepciones, etc.) → Spanish, as it is the learning interface for a Spanish-speaking user
- **In-terminal UI text** (labels, hints, summaries) → Spanish, for the same reason

## Branching

- One branch per issue: `feature/<short-description>`
- Always branch from `master`
- Open a PR for every change — do not push directly to `master`

## CSV format

Current format: **14 columns**, semicolon-separated, no header row.

```
id;tipo;palabra_en;palabra_es;frase_en;frase_en_cloze;frase_en_alt;frase_es;pronunciacion_ipa;registro;colocaciones;acepciones;por_que_ahora;fuente
```

`cmd_import` is backwards-compatible with 11, 12, 13 and 14-column files.

## Decks

- `decks/sessions.json` is not a deck — exclude it from all deck listings
- `decks/*.backup.json` files should also be excluded

## Audio

- Only `palabra_en` is spoken (not the full sentence)
- Plays at normal speed, then again at 0.5x via `ffplay atempo=0.5`

## README

- `README.md` → English (default, shown on GitHub)
- `README.es.md` → Spanish translation (issue #16, not yet implemented)
- Any change to one must be reflected in the other
