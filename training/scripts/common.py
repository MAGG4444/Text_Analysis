from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[A-Za-z']+")

PSYCHOLOGY_LEXICON: dict[str, set[str]] = {
    "confident": {
        "bold",
        "brave",
        "certain",
        "confident",
        "decisive",
        "determined",
        "focused",
        "resolute",
        "steady",
        "sure",
    },
    "anxious": {
        "afraid",
        "anxious",
        "fear",
        "hesitant",
        "nervous",
        "panic",
        "scared",
        "uncertain",
        "uneasy",
        "worried",
    },
    "angry": {
        "angry",
        "annoyed",
        "furious",
        "hate",
        "hostile",
        "irritated",
        "rage",
        "resent",
        "upset",
        "violent",
    },
    "joyful": {
        "celebrate",
        "cheerful",
        "delight",
        "glad",
        "happy",
        "joy",
        "laugh",
        "pleased",
        "relieved",
        "smile",
    },
    "sad": {
        "cry",
        "depressed",
        "despair",
        "grief",
        "lonely",
        "loss",
        "mourn",
        "sad",
        "sorrow",
        "tear",
    },
    "calm": {
        "calm",
        "gentle",
        "peace",
        "quiet",
        "rest",
        "safe",
        "serene",
        "soft",
        "stable",
        "tranquil",
    },
}

ATMOSPHERE_LEXICON: dict[str, set[str]] = {
    "tense": {
        "alarm",
        "battle",
        "conflict",
        "danger",
        "fight",
        "pressure",
        "risk",
        "strain",
        "threat",
        "urgent",
    },
    "dark": {
        "bleak",
        "blood",
        "cold",
        "dark",
        "death",
        "despair",
        "gloom",
        "grim",
        "nightmare",
        "ruin",
    },
    "warm": {
        "care",
        "comfort",
        "family",
        "friend",
        "gentle",
        "kind",
        "love",
        "safe",
        "smile",
        "support",
    },
    "hopeful": {
        "believe",
        "chance",
        "dream",
        "future",
        "growth",
        "heal",
        "hope",
        "improve",
        "renew",
        "victory",
    },
    "neutral": set(),
}

FALLBACK_CHARACTER_STOPWORDS = {
    "A",
    "An",
    "And",
    "As",
    "At",
    "But",
    "By",
    "For",
    "From",
    "He",
    "Her",
    "His",
    "I",
    "If",
    "In",
    "Into",
    "It",
    "Its",
    "Later",
    "No",
    "Not",
    "Now",
    "Of",
    "On",
    "One",
    "Or",
    "Our",
    "She",
    "So",
    "Some",
    "The",
    "Their",
    "Then",
    "There",
    "They",
    "This",
    "To",
    "We",
    "What",
    "When",
    "Where",
    "Who",
    "Why",
    "With",
    "You",
}


def normalize_text(text: str) -> str:
    try:
        from app import normalize_text as app_normalize_text

        return app_normalize_text(text)
    except Exception:
        return re.sub(r"\s+", " ", text or "").strip()


def iter_txt_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.txt") if path.is_file())


def read_text(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))


def split_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    pieces = [chunk.strip() for chunk in SENTENCE_SPLIT_RE.split(text) if chunk.strip()]
    if pieces:
        return pieces
    return [text]


def split_scenes(text: str, sentences_per_scene: int = 6) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    scenes: list[str] = []
    chunk: list[str] = []
    for sentence in sentences:
        chunk.append(sentence)
        if len(chunk) >= sentences_per_scene:
            scenes.append(" ".join(chunk))
            chunk = []

    if chunk:
        scenes.append(" ".join(chunk))

    return scenes


def keyword_label(text: str, lexicon: dict[str, set[str]], default: str = "neutral") -> str:
    tokens = [token.lower() for token in WORD_RE.findall(text)]
    token_counter = Counter(tokens)

    scores: list[tuple[int, str]] = []
    for label, keywords in lexicon.items():
        if not keywords:
            continue
        score = sum(token_counter.get(word, 0) for word in keywords)
        scores.append((score, label))

    if not scores:
        return default

    best_score = max(score for score, _ in scores)
    if best_score <= 0:
        return default

    winners = sorted(label for score, label in scores if score == best_score)
    return winners[0] if winners else default


def _fallback_people_profiles(text: str, top_n: int = 12) -> list[dict[str, Any]]:
    name_re = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")
    counts = Counter(
        name
        for name in name_re.findall(text)
        if name not in FALLBACK_CHARACTER_STOPWORDS and len(name) > 1
    )

    results: list[dict[str, Any]] = []
    for name, count in counts.most_common(top_n):
        results.append({"name": name, "aliases": [name], "weight": count})
    return results


def extract_people_profiles(text: str, top_n: int = 12) -> list[dict[str, Any]]:
    try:
        from app import extract_people_profiles as app_extract_people_profiles

        profiles = app_extract_people_profiles(text, top_n=top_n)
        if profiles:
            return profiles
    except Exception:
        pass

    return _fallback_people_profiles(text, top_n=top_n)


def alias_regex(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)


def sentence_mentions_aliases(sentence: str, aliases: list[str]) -> bool:
    for alias in aliases:
        if alias and alias_regex(alias).search(sentence):
            return True
    return False
