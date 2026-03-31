#!/usr/bin/env python3
"""CLI de Flashcards con FSRS-5 para aprendizaje de idiomas."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import tty
import termios
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fsrs

DECKS_DIR = Path(__file__).resolve().parent / "decks"
SESSIONS_FILE = DECKS_DIR / "sessions.json"
AUDIO_CACHE = Path(__file__).resolve().parent / ".audio_cache"
SCHEDULER = fsrs.Scheduler(desired_retention=0.9, enable_fuzzing=False)
RATING_MAP = {
    "1": fsrs.Rating.Again,
    "2": fsrs.Rating.Hard,
    "3": fsrs.Rating.Good,
    "4": fsrs.Rating.Easy,
}

# ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_GREEN = "\033[32m"
C_BLUE = "\033[34m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"

CSV_HEADER = "id;tipo;palabra_en;palabra_es;frase_en;frase_en_cloze;frase_es;pronunciacion_ipa;registro;colocaciones;acepciones;por_que_ahora;fuente"

ACCENT_TLD = {
    "us": "com",
    "uk": "co.uk",
    "au": "com.au",
    "in": "co.in",
}


def _load_sessions():
    if not SESSIONS_FILE.exists():
        return []
    return json.loads(SESSIONS_FILE.read_text())


def _save_session(data):
    sessions = _load_sessions()
    sessions.append(data)
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2))


def load_deck(name):
    path = DECKS_DIR / f"{name}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    for entry in data:
        entry["fsrs_card"] = fsrs.Card.from_dict(entry["fsrs_card"])
    return data


def save_deck(name, cards):
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    data = []
    for entry in cards:
        d = {**entry, "fsrs_card": entry["fsrs_card"].to_dict()}
        data.append(d)
    (DECKS_DIR / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_pipe_list(value):
    """Convert a pipe-separated string to a list, or return empty list."""
    value = value.strip()
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def cmd_import(args):
    path = Path(args.file)
    if not path.exists():
        print(f"{C_RED}Error: archivo '{path}' no encontrado.{C_RESET}")
        sys.exit(1)

    raw = path.read_text(encoding="utf-8")
    lines = raw.strip().splitlines()

    cards = load_deck(args.deck)
    existing_keys = {(c["id"], c["tipo"]) for c in cards if "id" in c and "tipo" in c}
    added = 0

    reader = csv.reader(lines, delimiter=";")
    for row in reader:
        # Skip header if present
        if row and row[0].strip().lower() == "id":
            continue
        if len(row) < 11:
            continue

        card_id = row[0].strip()
        tipo = row[1].strip().upper()
        palabra_en = row[2].strip()
        # Support 11-col (legacy), 12-col (palabra_es), 13-col (+ frase_en_cloze)
        if len(row) >= 13:
            palabra_es = row[3].strip()
            frase_en = row[4].strip()
            frase_en_cloze = row[5].strip()
            frase_es = row[6].strip()
            pronunciacion_ipa = row[7].strip()
            registro = row[8].strip()
            colocaciones = _parse_pipe_list(row[9])
            acepciones = _parse_pipe_list(row[10])
            por_que_ahora = row[11].strip()
            fuente = row[12].strip()
        elif len(row) >= 12:
            palabra_es = row[3].strip()
            frase_en_cloze = ""
            frase_en = row[4].strip()
            frase_es = row[5].strip()
            pronunciacion_ipa = row[6].strip()
            registro = row[7].strip()
            colocaciones = _parse_pipe_list(row[8])
            acepciones = _parse_pipe_list(row[9])
            por_que_ahora = row[10].strip()
            fuente = row[11].strip()
        else:
            palabra_es = ""
            frase_en_cloze = ""
            frase_en = row[3].strip()
            frase_es = row[4].strip()
            pronunciacion_ipa = row[5].strip()
            registro = row[6].strip()
            colocaciones = _parse_pipe_list(row[7])
            acepciones = _parse_pipe_list(row[8])
            por_que_ahora = row[9].strip()
            fuente = row[10].strip()

        if not card_id or not tipo or not palabra_en:
            continue

        key = (card_id, tipo)
        if key in existing_keys:
            continue

        cards.append({
            "id": card_id,
            "tipo": tipo,
            "palabra_en": palabra_en,
            "palabra_es": palabra_es,
            "frase_en": frase_en,
            "frase_en_cloze": frase_en_cloze,
            "frase_es": frase_es,
            "pronunciacion_ipa": pronunciacion_ipa,
            "registro": registro,
            "colocaciones": colocaciones,
            "acepciones": acepciones,
            "por_que_ahora": por_que_ahora,
            "fuente": fuente,
            "fsrs_card": fsrs.Card(),
            "reviews": [],
        })
        existing_keys.add(key)
        added += 1

    save_deck(args.deck, cards)
    print(f"{C_GREEN}Importadas {added} tarjetas al deck \"{args.deck}\" ({len(cards)} total).{C_RESET}")


def get_key():
    fd = sys.stdin.fileno()
    if not sys.stdin.isatty():
        ch = sys.stdin.read(1)
        return ch if ch else "q"
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def clear_screen():
    print("\033[2J\033[H", end="", flush=True)


def _speak(text, lang="en", tld="com"):
    """Play TTS audio for text using gTTS + ffplay. Plays normal speed, then slow (0.75x via ffplay)."""
    try:
        AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
        from gtts import gTTS

        key = hashlib.md5(f"{lang}:{tld}:{text}".encode()).hexdigest()
        cached = AUDIO_CACHE / f"{key}.mp3"

        if not cached.exists():
            gTTS(text, lang=lang, tld=tld).save(str(cached))

        # Normal speed, wait for it to finish, then slow (0.75x via atempo filter)
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(cached)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
             "-af", "atempo=0.5", str(cached)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Audio is best-effort, never block the review


def _highlight_in_phrase(phrase, word):
    """Highlight word/expression within phrase using case-insensitive match."""
    import re
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(lambda m: f"{C_RESET}{C_BOLD}{C_YELLOW}{m.group()}{C_RESET}{C_GREEN}", phrase)


def _render_front(card, deck_name, reviewed, total, w):
    """Render the front side of a card."""
    tipo = card.get("tipo", "A")
    dir_label = f"{C_MAGENTA}ES\u2192EN{C_RESET}" if tipo == "A" else f"{C_CYAN}EN\u2192ES{C_RESET}"

    clear_screen()
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")
    print(f"  {C_BOLD}{deck_name}{C_RESET}  {C_DIM}[{reviewed}/{total}]{C_RESET}  {dir_label}")
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")
    print()

    if tipo == "A":
        # Production: show Spanish phrase with target word highlighted
        frase_es = card.get("frase_es", "")
        palabra_es = card.get("palabra_es", "")
        if palabra_es:
            frase_es = _highlight_in_phrase(frase_es, palabra_es)
        print(f"  {C_BOLD}{frase_es}{C_RESET}")
        frase_en_cloze = card.get("frase_en_cloze", "")
        if frase_en_cloze:
            print()
            highlighted_cloze = frase_en_cloze.replace(
                "____", f"{C_RESET}{C_BOLD}{C_YELLOW}____{C_RESET}{C_DIM}"
            )
            print(f"  {C_DIM}\"{highlighted_cloze}\"{C_RESET}")
    else:
        # Comprehension: show English word + phrase
        print(f"  {C_BOLD}{card.get('palabra_en', '')}{C_RESET}")
        frase_en = card.get("frase_en", "")
        if frase_en:
            print(f"  {C_DIM}\"{frase_en}\"{C_RESET}")

    print()
    print(f"  {C_DIM}[ENTER] ver respuesta  [q] salir{C_RESET}")


def _render_back(card, deck_name, reviewed, total, w):
    """Render the back side of a card."""
    tipo = card.get("tipo", "A")
    dir_label = f"{C_MAGENTA}ES\u2192EN{C_RESET}" if tipo == "A" else f"{C_CYAN}EN\u2192ES{C_RESET}"
    sep = f"  {'\u2500' * w}"

    clear_screen()
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")
    print(f"  {C_BOLD}{deck_name}{C_RESET}  {C_DIM}[{reviewed}/{total}]{C_RESET}  {dir_label}")
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")
    print()

    ipa = card.get("pronunciacion_ipa", "")
    registro = card.get("registro", "")
    colocaciones = card.get("colocaciones", [])
    acepciones = card.get("acepciones", [])
    por_que_ahora = card.get("por_que_ahora", "")

    if tipo == "A":
        # Production: front was Spanish, reveal English
        frase_es = card.get("frase_es", "")
        palabra_es = card.get("palabra_es", "")
        if palabra_es:
            frase_es = _highlight_in_phrase(frase_es, palabra_es)
        print(f"  {C_DIM}{frase_es}{C_RESET}")
        print(sep)
        # Word + IPA on same line
        word_line = f"  {C_BOLD}{C_GREEN}{card.get('palabra_en', '')}{C_RESET}"
        if ipa:
            word_line += f"  {C_DIM}{ipa}{C_RESET}"
        print(word_line)
        frase_en = card.get("frase_en", "")
        if frase_en:
            print(f"  {C_GREEN}\"{frase_en}\"{C_RESET}")
        print(sep)
        if registro:
            print(f"  {C_DIM}Registro:{C_RESET} {registro}")
        if colocaciones:
            print(f"  {C_DIM}Colocaciones:{C_RESET} {' \u00b7 '.join(colocaciones)}")
        if acepciones:
            print(f"  {C_DIM}Acepciones:{C_RESET} {' \u00b7 '.join(acepciones)}")
    else:
        # Comprehension: front was English, reveal Spanish
        print(f"  {C_DIM}{card.get('palabra_en', '')}{C_RESET}")
        frase_en = card.get("frase_en", "")
        if frase_en:
            print(f"  {C_DIM}\"{frase_en}\"{C_RESET}")
        print(sep)
        # Spanish translation + IPA
        answer_line = f"  {C_BOLD}{C_GREEN}{card.get('frase_es', '')}{C_RESET}"
        if ipa:
            answer_line += f"  {C_DIM}{ipa}{C_RESET}"
        print(answer_line)
        print(sep)
        if registro:
            print(f"  {C_DIM}Registro:{C_RESET} {registro}")
        if colocaciones:
            print(f"  {C_DIM}Colocaciones:{C_RESET} {' \u00b7 '.join(colocaciones)}")
        if por_que_ahora:
            print(f"  {C_DIM}Por qu\u00e9 ahora:{C_RESET} {por_que_ahora}")

    print(sep)
    print(f"  {C_RED}[1] Again{C_RESET}  {C_YELLOW}[2] Hard{C_RESET}  {C_GREEN}[3] Good{C_RESET}  {C_BLUE}[4] Easy{C_RESET}")
    print(f"  {C_DIM}[d] Eliminar         [q] Salir{C_RESET}")


def _card_match_key(card):
    """Return the unique key for matching a card in the deck."""
    if "id" in card and "tipo" in card:
        return (card["id"], card["tipo"])
    return (card.get("front", ""), card.get("direction", "forward"))


def cmd_review(args):
    if args.deck:
        deck_names = [args.deck]
    else:
        if not DECKS_DIR.exists():
            print("No hay decks. Importa tarjetas primero.")
            return
        deck_names = [p.stem for p in sorted(DECKS_DIR.glob("*.json"))
                      if not p.stem.endswith(".backup") and p.stem != "sessions"]
        if not deck_names:
            print("No hay decks. Importa tarjetas primero.")
            return

    # Filter by tipo (A/B)
    tipo_filter = getattr(args, "tipo", None)

    now = datetime.now(timezone.utc)
    queue = []
    for dn in deck_names:
        cards = load_deck(dn)
        for i, entry in enumerate(cards):
            if tipo_filter and entry.get("tipo", "A") != tipo_filter:
                continue
            if entry["fsrs_card"].due <= now:
                queue.append((dn, i, entry))

    # Sort: review/relearning cards first, then new/learning
    queue.sort(key=lambda x: (
        x[2]["fsrs_card"].state == fsrs.State.Learning and x[2]["fsrs_card"].last_review is None,
        x[2]["fsrs_card"].due,
    ))

    if not queue:
        print(f"{C_GREEN}No hay tarjetas pendientes. \u00a1Buen trabajo!{C_RESET}")
        return

    total = len(queue)
    reviewed = 0
    deleted = 0
    session_ratings = {"Again": 0, "Hard": 0, "Good": 0, "Easy": 0}
    again_cards = []
    deck_cache = {}

    w = 43
    for deck_name, card_idx, entry in queue:
        if deck_name not in deck_cache:
            deck_cache[deck_name] = load_deck(deck_name)
        deck_cards = deck_cache[deck_name]

        match_key = _card_match_key(entry)
        actual = None
        actual_idx = None
        for j, dc in enumerate(deck_cards):
            if _card_match_key(dc) == match_key:
                actual = dc
                actual_idx = j
                break
        if actual is None:
            continue

        reviewed += 1

        # Show front
        _render_front(actual, deck_name, reviewed, total, w)

        key = get_key()
        if key == "q":
            reviewed -= 1
            break

        # Show back + play audio
        palabra_en = actual.get("palabra_en", actual.get("front", ""))
        if not getattr(args, "mute", False):
            accent = getattr(args, "accent", "us")
            tld = ACCENT_TLD.get(accent, "com")
            _speak(palabra_en, tld=tld)
        _render_back(actual, deck_name, reviewed, total, w)

        while True:
            key = get_key()
            if key == "q":
                reviewed -= 1
                for dn, dc in deck_cache.items():
                    save_deck(dn, dc)
                _print_summary(reviewed, deleted, session_ratings, again_cards)
                if reviewed > 0:
                    total_rated = sum(session_ratings.values())
                    accuracy = round((session_ratings["Good"] + session_ratings["Easy"]) / total_rated * 100, 1) if total_rated else 0
                    _save_session({
                        "date": datetime.now(timezone.utc).isoformat(),
                        "decks": deck_names,
                        "reviewed": reviewed,
                        "deleted": deleted,
                        "ratings": session_ratings,
                        "accuracy": accuracy,
                        "again_cards": again_cards,
                    })
                return
            if key == "d":
                print(f"\n  {C_YELLOW}\u00bfEliminar tarjeta? [s/n]{C_RESET} ", end="", flush=True)
                confirm = get_key()
                if confirm in ("s", "S"):
                    deck_cards.pop(actual_idx)
                    deleted += 1
                    print(f" {C_RED}Eliminada.{C_RESET}")
                    break
                else:
                    print(f" {C_DIM}Cancelado.{C_RESET}")
                    continue
            if key in RATING_MAP:
                rating = RATING_MAP[key]
                new_card, log = SCHEDULER.review_card(actual["fsrs_card"], rating)
                actual["fsrs_card"] = new_card
                actual["reviews"].append({
                    "date": datetime.now(timezone.utc).isoformat(),
                    "rating": rating.name,
                })
                session_ratings[rating.name] += 1
                if rating == fsrs.Rating.Again:
                    palabra = actual.get("palabra_en", "")
                    if palabra:
                        again_cards.append(palabra)
                break

    for dn, dc in deck_cache.items():
        save_deck(dn, dc)
    _print_summary(reviewed, deleted, session_ratings, again_cards)
    if reviewed > 0:
        total_rated = sum(session_ratings.values())
        accuracy = round((session_ratings["Good"] + session_ratings["Easy"]) / total_rated * 100, 1) if total_rated else 0
        _save_session({
            "date": datetime.now(timezone.utc).isoformat(),
            "decks": deck_names,
            "reviewed": reviewed,
            "deleted": deleted,
            "ratings": session_ratings,
            "accuracy": accuracy,
            "again_cards": again_cards,
        })


def _print_summary(reviewed, deleted, ratings, again_cards=None):
    print()
    w = 43
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")
    print(f"  {C_BOLD}Resumen de sesi\u00f3n{C_RESET}")
    print(f"  {'\u2500' * w}")
    print(f"  Revisadas: {C_BOLD}{reviewed}{C_RESET}")
    if deleted:
        print(f"  Eliminadas: {C_RED}{deleted}{C_RESET}")
    print()
    if any(ratings.values()):
        print(f"  {C_RED}Again: {ratings['Again']}{C_RESET}  {C_YELLOW}Hard: {ratings['Hard']}{C_RESET}  {C_GREEN}Good: {ratings['Good']}{C_RESET}  {C_BLUE}Easy: {ratings['Easy']}{C_RESET}")
        total_rated = sum(ratings.values())
        if total_rated:
            pct_good = (ratings["Good"] + ratings["Easy"]) / total_rated * 100
            color = C_GREEN if pct_good >= 80 else C_YELLOW if pct_good >= 60 else C_RED
            print(f"  Aciertos (Good+Easy): {color}{pct_good:.0f}%{C_RESET}")
    if again_cards:
        print(f"  {C_RED}Again: {' \u00b7 '.join(again_cards)}{C_RESET}")
    print(f"{C_BOLD}{'\u2550' * w}{C_RESET}")


def cmd_stats(args):
    if not DECKS_DIR.exists():
        print("No hay decks.")
        return

    now = datetime.now(timezone.utc)
    total_cards = 0
    total_due = 0
    total_reviews = 0

    for path in sorted(DECKS_DIR.glob("*.json")):
        if path.stem.endswith(".backup") or path.stem == "sessions":
            continue
        cards = load_deck(path.stem)
        due = sum(1 for c in cards if c["fsrs_card"].due <= now)
        reviews = sum(len(c["reviews"]) for c in cards)
        new = sum(1 for c in cards if c["fsrs_card"].last_review is None)
        learning = sum(1 for c in cards if c["fsrs_card"].state == fsrs.State.Learning and c["fsrs_card"].last_review is not None)
        review = sum(1 for c in cards if c["fsrs_card"].state == fsrs.State.Review)
        tipo_a = sum(1 for c in cards if c.get("tipo", "A") == "A")
        tipo_b = sum(1 for c in cards if c.get("tipo") == "B")

        total_cards += len(cards)
        total_due += due
        total_reviews += reviews

        print(f"  {C_BOLD}{path.stem}{C_RESET}")
        print(f"    Tarjetas: {len(cards)}  ({C_MAGENTA}{tipo_a} A (ES\u2192EN){C_RESET}, {C_CYAN}{tipo_b} B (EN\u2192ES){C_RESET})")
        print(f"    Estado: nuevas: {new}, aprendiendo: {learning}, repaso: {review}")
        print(f"    Pendientes: {C_YELLOW}{due}{C_RESET}  |  Reviews totales: {reviews}")
        print()

    if total_cards:
        print(f"  {C_BOLD}TOTAL: {total_cards} tarjetas, {total_due} pendientes, {total_reviews} reviews{C_RESET}")


def cmd_decks(args):
    if not DECKS_DIR.exists():
        print("No hay decks.")
        return
    paths = sorted(p for p in DECKS_DIR.glob("*.json") if not p.stem.endswith(".backup") and p.stem != "sessions")
    if not paths:
        print("No hay decks.")
        return
    now = datetime.now(timezone.utc)
    for p in paths:
        cards = load_deck(p.stem)
        due = sum(1 for c in cards if c["fsrs_card"].due <= now)
        print(f"  {C_BOLD}{p.stem}{C_RESET} \u2014 {len(cards)} tarjetas ({C_YELLOW}{due} pendientes{C_RESET})")


def cmd_merge(args):
    all_cards = []
    seen = set()
    for deck_name in args.decks:
        cards = load_deck(deck_name)
        if not cards:
            print(f"{C_YELLOW}Aviso: deck '{deck_name}' no encontrado o vac\u00edo.{C_RESET}")
            continue
        for c in cards:
            key = _card_match_key(c)
            if key not in seen:
                all_cards.append(c)
                seen.add(key)

    if not all_cards:
        print(f"{C_RED}No se encontraron tarjetas para combinar.{C_RESET}")
        return

    target = args.into
    existing = load_deck(target)
    existing_keys = {_card_match_key(c) for c in existing}
    added = 0
    for c in all_cards:
        key = _card_match_key(c)
        if key not in existing_keys:
            existing.append(c)
            existing_keys.add(key)
            added += 1

    save_deck(target, existing)
    print(f"{C_GREEN}Combinados {len(args.decks)} decks \u2192 \"{target}\" ({added} nuevas, {len(existing)} total).{C_RESET}")


def cmd_history(args):
    sessions = _load_sessions()
    if not sessions:
        print("No hay sesiones registradas.")
        return

    w = 43
    today = datetime.now(timezone.utc).date()

    # Build per-day aggregation for last 14 days
    days = {}
    for s in sessions:
        d = datetime.fromisoformat(s["date"]).date()
        if d not in days:
            days[d] = {"reviewed": 0, "accuracy_sum": 0, "session_count": 0, "again_cards": []}
        days[d]["reviewed"] += s["reviewed"]
        days[d]["accuracy_sum"] += s.get("accuracy", 0)
        days[d]["session_count"] += 1
        days[d]["again_cards"].extend(s.get("again_cards", []))

    print()
    print(f"  {C_BOLD}Historial de sesiones (últimos 14 días){C_RESET}")
    print(f"  {'─' * w}")

    MONTH_ABBR = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
    }

    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        label = f"{MONTH_ABBR[d.month]} {d.day:2d}"
        if d in days:
            info = days[d]
            avg_acc = info["accuracy_sum"] / info["session_count"]
            color = C_GREEN if avg_acc >= 80 else C_YELLOW if avg_acc >= 60 else C_RED
            print(f"  {label}   {info['reviewed']:3d} tarjetas   {color}{avg_acc:.0f}%{C_RESET}")
            if info["again_cards"]:
                again_str = " · ".join(dict.fromkeys(info["again_cards"]))
                print(f"           {C_RED}Again: {again_str}{C_RESET}")
        else:
            print(f"  {label}   {C_DIM}—{C_RESET}")

    print(f"  {'─' * w}")

    # Streaks
    current_streak = 0
    d = today
    while d in days:
        current_streak += 1
        d -= timedelta(days=1)

    best_streak = 0
    streak = 0
    all_dates = sorted(days.keys())
    for i, d in enumerate(all_dates):
        if i == 0 or d == all_dates[i - 1] + timedelta(days=1):
            streak += 1
        else:
            streak = 1
        best_streak = max(best_streak, streak)

    total_sessions = len(sessions)
    total_reviews = sum(s["reviewed"] for s in sessions)

    print(f"  Racha actual: {C_BOLD}{current_streak} días{C_RESET}")
    print(f"  Mejor racha:  {C_BOLD}{best_streak} días{C_RESET}")
    print(f"  Total sesiones: {total_sessions}")
    print(f"  Total reviews:  {total_reviews}")

    # Leeches: words appearing in again_cards of 2+ distinct sessions
    word_sessions = Counter()
    for s in sessions:
        unique_words = set(s.get("again_cards", []))
        for w_word in unique_words:
            word_sessions[w_word] += 1

    leeches = [(word, count) for word, count in word_sessions.most_common() if count >= 2]
    if leeches:
        print(f"  {'─' * w}")
        print(f"  {C_BOLD}Palabras que más cuestan:{C_RESET}")
        for word, count in leeches:
            print(f"    {C_RED}{word:20s}{C_RESET} — {count} sesiones")

    print()


def main():
    parser = argparse.ArgumentParser(description="Flashcards CLI con FSRS-5")
    sub = parser.add_subparsers(dest="command")

    p_import = sub.add_parser("import", help="Importar tarjetas desde CSV")
    p_import.add_argument("file", help="Archivo CSV (11 columnas, separador ;)")
    p_import.add_argument("--deck", required=True, help="Nombre del deck")

    p_review = sub.add_parser("review", help="Sesi\u00f3n de repaso")
    p_review.add_argument("--deck", help="Deck espec\u00edfico (opcional)")
    tipo_group = p_review.add_mutually_exclusive_group()
    tipo_group.add_argument("--tipo-a", dest="tipo", action="store_const", const="A", help="Solo tarjetas A (ES\u2192EN)")
    tipo_group.add_argument("--tipo-b", dest="tipo", action="store_const", const="B", help="Solo tarjetas B (EN\u2192ES)")
    p_review.add_argument("--mute", action="store_true", help="Desactivar audio")
    p_review.add_argument("--accent", default="us", choices=["us", "uk", "au", "in"],
                          help="Acento del audio: us (americano), uk (británico), au (australiano), in (indio). Default: us")

    sub.add_parser("stats", help="Ver estad\u00edsticas")
    sub.add_parser("decks", help="Listar decks")
    sub.add_parser("history", help="Ver historial de sesiones")

    p_merge = sub.add_parser("merge", help="Combinar decks en uno")
    p_merge.add_argument("--decks", nargs="+", required=True, help="Decks a combinar")
    p_merge.add_argument("--into", required=True, help="Nombre del deck destino")

    args = parser.parse_args()

    if args.command == "import":
        cmd_import(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "decks":
        cmd_decks(args)
    elif args.command == "merge":
        cmd_merge(args)
    elif args.command == "history":
        cmd_history(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
