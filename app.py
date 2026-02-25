from __future__ import annotations

import html as html_lib
import io
import json
import os
import random
import re
import string
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12 MB upload guard

SUPPORTED_EXTENSIONS = (".txt", ".md", ".rtf", ".doc", ".docx")
MAX_REMOTE_DOWNLOAD_BYTES = 10 * 1024 * 1024
REMOTE_USER_AGENT = "NarrativeSentimentWorkbench/1.0"


POSITIVE_WORDS = {
    "admire",
    "adore",
    "amaze",
    "amazing",
    "appeal",
    "assure",
    "authentic",
    "beautiful",
    "beloved",
    "blessing",
    "bold",
    "brave",
    "brilliant",
    "calm",
    "care",
    "celebrate",
    "charm",
    "comfort",
    "compassion",
    "confidence",
    "courage",
    "delight",
    "dream",
    "ease",
    "empathy",
    "encourage",
    "enjoy",
    "excited",
    "faith",
    "favorable",
    "flourish",
    "freedom",
    "friend",
    "gain",
    "gentle",
    "glad",
    "glory",
    "good",
    "grace",
    "grateful",
    "great",
    "growth",
    "happy",
    "harmony",
    "heal",
    "heart",
    "hope",
    "ideal",
    "improve",
    "inspire",
    "joy",
    "kind",
    "laugh",
    "light",
    "love",
    "loyal",
    "luck",
    "mercy",
    "miracle",
    "noble",
    "optimistic",
    "passion",
    "peace",
    "pleased",
    "positive",
    "praise",
    "prosper",
    "protect",
    "proud",
    "relief",
    "renew",
    "rescue",
    "respect",
    "reward",
    "safe",
    "satisfy",
    "serene",
    "shine",
    "smile",
    "solid",
    "strong",
    "support",
    "survive",
    "thrive",
    "trust",
    "victory",
    "warm",
    "welcome",
    "whole",
    "wonder",
}

NEGATIVE_WORDS = {
    "abandon",
    "afraid",
    "agony",
    "anger",
    "anguish",
    "anxious",
    "ashamed",
    "attack",
    "awkward",
    "bad",
    "betray",
    "bleak",
    "blood",
    "broken",
    "burden",
    "chaos",
    "cold",
    "conflict",
    "crash",
    "cruel",
    "cry",
    "damage",
    "danger",
    "dark",
    "death",
    "debt",
    "defeat",
    "deny",
    "despair",
    "destroy",
    "difficult",
    "doubt",
    "dread",
    "enemy",
    "fear",
    "fight",
    "fragile",
    "gloom",
    "grief",
    "guilt",
    "hate",
    "hollow",
    "hostile",
    "hurt",
    "injustice",
    "injury",
    "isolate",
    "jealous",
    "kill",
    "loss",
    "lonely",
    "mad",
    "mess",
    "misery",
    "mourn",
    "negative",
    "nightmare",
    "pain",
    "panic",
    "poor",
    "pressure",
    "rage",
    "regret",
    "reject",
    "risk",
    "rough",
    "ruin",
    "sad",
    "scared",
    "scar",
    "shame",
    "shock",
    "sorrow",
    "stress",
    "struggle",
    "suffer",
    "tense",
    "threat",
    "tired",
    "tragedy",
    "trap",
    "ugly",
    "uncertain",
    "unfair",
    "worry",
    "wound",
}

CHARACTER_STOPWORDS = {
    "A",
    "About",
    "After",
    "All",
    "Also",
    "An",
    "And",
    "Any",
    "As",
    "At",
    "Before",
    "But",
    "By",
    "Chapter",
    "Day",
    "For",
    "From",
    "He",
    "Her",
    "Here",
    "His",
    "I",
    "If",
    "In",
    "Into",
    "It",
    "Its",
    "Later",
    "More",
    "Morning",
    "Night",
    "No",
    "Not",
    "Now",
    "Of",
    "On",
    "One",
    "Or",
    "Our",
    "Scene",
    "She",
    "So",
    "Some",
    "The",
    "Their",
    "Then",
    "There",
    "They",
    "This",
    "Through",
    "To",
    "Today",
    "Tomorrow",
    "We",
    "When",
    "Where",
    "With",
    "You",
}

THEME_KEYWORDS: dict[str, set[str]] = {
    "Love & Relationships": {
        "love",
        "heart",
        "romance",
        "relationship",
        "marriage",
        "family",
        "friendship",
        "care",
        "trust",
        "betrayal",
        "bond",
    },
    "Conflict & Power": {
        "war",
        "battle",
        "fight",
        "conflict",
        "enemy",
        "threat",
        "power",
        "control",
        "resistance",
        "violence",
        "army",
    },
    "Mystery & Crime": {
        "mystery",
        "crime",
        "detective",
        "clue",
        "investigation",
        "evidence",
        "suspect",
        "killer",
        "police",
        "secret",
        "case",
    },
    "Growth & Identity": {
        "identity",
        "self",
        "dream",
        "purpose",
        "change",
        "growth",
        "journey",
        "future",
        "discover",
        "become",
        "learn",
    },
    "Politics & Society": {
        "government",
        "policy",
        "rights",
        "justice",
        "society",
        "community",
        "law",
        "freedom",
        "protest",
        "nation",
        "election",
    },
    "Technology & Innovation": {
        "technology",
        "digital",
        "software",
        "internet",
        "machine",
        "data",
        "algorithm",
        "ai",
        "robot",
        "platform",
        "innovation",
    },
    "Health & Wellbeing": {
        "health",
        "disease",
        "medical",
        "doctor",
        "hospital",
        "mental",
        "stress",
        "recovery",
        "treatment",
        "wellness",
        "therapy",
    },
    "Business & Economy": {
        "market",
        "economy",
        "finance",
        "money",
        "trade",
        "investment",
        "company",
        "profit",
        "cost",
        "industry",
        "business",
    },
    "Environment & Climate": {
        "climate",
        "environment",
        "nature",
        "pollution",
        "sustainability",
        "earth",
        "energy",
        "carbon",
        "wildlife",
        "conservation",
        "ecology",
    },
    "Adventure & Survival": {
        "journey",
        "travel",
        "expedition",
        "survive",
        "danger",
        "rescue",
        "forest",
        "mountain",
        "ocean",
        "quest",
        "wild",
    },
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
FULL_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,})\s+([A-Z][a-z]{1,})\b")
TITLE_NAME_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr|Prof)\.?\s+([A-Z][a-z]{1,})(?:\s+([A-Z][a-z]{1,}))?\b")
CONJUNCTION_WORDS = {
    "and",
    "but",
    "or",
    "nor",
    "for",
    "so",
    "yet",
    "after",
    "although",
    "as",
    "because",
    "before",
    "if",
    "once",
    "since",
    "than",
    "that",
    "though",
    "till",
    "unless",
    "until",
    "when",
    "whenever",
    "where",
    "whereas",
    "wherever",
    "whether",
    "while",
}
CHARACTER_STOPWORDS_LOWER = {word.lower() for word in CHARACTER_STOPWORDS}
THEME_TERMS = {term.lower() for words in THEME_KEYWORDS.values() for term in words}
NON_PERSON_TERMS = {
    "chapter",
    "section",
    "article",
    "figure",
    "table",
    "appendix",
    "introduction",
    "conclusion",
    "analysis",
    "report",
    "study",
    "paper",
    "journal",
    "news",
    "media",
    "internet",
    "website",
    "platform",
    "project",
    "program",
    "system",
    "model",
    "method",
    "result",
    "results",
    "government",
    "company",
    "university",
    "department",
    "committee",
    "board",
    "agency",
    "court",
    "bank",
    "market",
    "industry",
    "policy",
    "climate",
    "technology",
    "economy",
    "society",
    "community",
    "team",
    "group",
    "school",
    "state",
    "city",
    "county",
    "nation",
    "country",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
NON_PERSON_TERMS_LOWER = THEME_TERMS | NON_PERSON_TERMS | CHARACTER_STOPWORDS_LOWER
ORG_SUFFIX_HINTS = {
    "inc",
    "corp",
    "ltd",
    "llc",
    "university",
    "college",
    "department",
    "agency",
    "committee",
    "council",
    "bank",
    "company",
    "ministry",
    "institute",
    "foundation",
}
PERSON_CONTEXT_HINTS = {
    "said",
    "says",
    "told",
    "asked",
    "replied",
    "wrote",
    "spoke",
    "noted",
    "argued",
    "explained",
    "met",
    "him",
    "her",
    "his",
    "hers",
    "he",
    "she",
}
GENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GENAI_MAX_CHARS = 12000


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="ignore")


def normalize_web_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Web link must start with http:// or https://")
    return candidate


def has_supported_extension(path_or_url: str) -> bool:
    path = urlparse(path_or_url).path.lower() if "://" in path_or_url else path_or_url.lower()
    return any(path.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def infer_filename_from_url(url: str, fallback: str = "remote.txt") -> str:
    path = urlparse(url).path
    if not path or path.endswith("/"):
        return fallback
    name = path.rsplit("/", 1)[-1]
    return name or fallback


def fetch_remote_resource(
    source_url: str,
    max_bytes: int = MAX_REMOTE_DOWNLOAD_BYTES,
) -> tuple[str, str, bytes]:
    safe_url = normalize_web_url(source_url)
    req = Request(safe_url, headers={"User-Agent": REMOTE_USER_AGENT})
    try:
        with urlopen(req, timeout=18) as response:
            final_url = response.geturl()
            content_type = (response.headers.get("Content-Type") or "").lower()
            raw = response.read(max_bytes + 1)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise ValueError(f"Could not fetch web link: {exc}") from exc

    if len(raw) > max_bytes:
        raise ValueError("Remote content is too large. Limit is 10 MB.")

    return final_url, content_type, raw


class AnchorLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = href.strip()
        self._label_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is None:
            return
        text = data.strip()
        if text:
            self._label_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        label = " ".join(self._label_parts).strip()
        self.links.append((self._href, label))
        self._href = None
        self._label_parts = []


def extract_visible_html_text(raw: bytes) -> str:
    page = decode_bytes(raw)
    page = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>", "\n", page)
    page = re.sub(r"(?i)</?(p|div|h[1-6]|li|tr|section|article|blockquote)[^>]*>", "\n", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    page = html_lib.unescape(page)
    return normalize_text(page)


def extract_docx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml_data = archive.read("word/document.xml")

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ET.fromstring(xml_data)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        fragments = [node.text for node in paragraph.findall(".//w:t", ns) if node.text]
        if fragments:
            paragraphs.append("".join(fragments))
    return "\n\n".join(paragraphs)


def extract_rtf_text(raw: bytes) -> str:
    text = decode_bytes(raw)

    def _hex_replace(match: re.Match[str]) -> str:
        code = match.group(1)
        return bytes.fromhex(code).decode("cp1252", errors="ignore")

    text = re.sub(r"\\'([0-9a-fA-F]{2})", _hex_replace, text)
    text = re.sub(r"\\par[d]? ?", "\n", text)
    text = re.sub(r"\\tab ?", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    return text


def extract_legacy_doc_text(raw: bytes) -> str:
    # Best-effort fallback for binary .doc files without external tooling.
    chunks = re.findall(rb"[A-Za-z][A-Za-z0-9 ,;:'\"?!\-\(\)\n]{5,}", raw)
    if not chunks:
        return ""
    merged = " ".join(chunk.decode("cp1252", errors="ignore") for chunk in chunks)
    return merged


def extract_upload_text(filename: str, raw: bytes) -> tuple[str, str | None]:
    lower = filename.lower()
    warning: str | None = None

    if lower.endswith(".docx"):
        text = extract_docx_text(raw)
    elif lower.endswith(".rtf"):
        text = extract_rtf_text(raw)
    elif lower.endswith(".doc"):
        text = extract_legacy_doc_text(raw)
        warning = "Legacy .doc extraction is best-effort. Converting to .docx improves accuracy."
    else:
        text = decode_bytes(raw)

    return normalize_text(text), warning


def extract_remote_text(source_url: str, source_mode: str = "auto") -> tuple[str, str | None, str]:
    final_url, content_type, raw = fetch_remote_resource(source_url)
    content_type_base = content_type.split(";", 1)[0].strip()
    filename_hint = infer_filename_from_url(final_url)
    use_webpage_mode = source_mode == "webpage"

    warning: str | None = None
    if use_webpage_mode and "html" in content_type_base:
        text = extract_visible_html_text(raw)
        warning = "Analyzed visible text extracted from webpage HTML."
    elif has_supported_extension(final_url) or has_supported_extension(source_url):
        text, warning = extract_upload_text(filename_hint, raw)
    elif "officedocument.wordprocessingml.document" in content_type_base:
        text, warning = extract_upload_text("remote.docx", raw)
    elif "rtf" in content_type_base:
        text, warning = extract_upload_text("remote.rtf", raw)
    elif "html" in content_type_base:
        text = extract_visible_html_text(raw)
        warning = "Analyzed visible text extracted from webpage HTML."
    else:
        text = normalize_text(decode_bytes(raw))
        if content_type_base and content_type_base != "text/plain":
            warning = f"Parsed remote content as plain text ({content_type_base})."

    if not text:
        raise ValueError("Could not extract readable text from the provided web link.")

    return text, warning, final_url


def discover_remote_files(source_url: str) -> tuple[str, list[dict[str, str]]]:
    final_url, content_type, raw = fetch_remote_resource(source_url, max_bytes=5 * 1024 * 1024)
    if has_supported_extension(final_url):
        return final_url, [
            {
                "url": final_url,
                "label": infer_filename_from_url(final_url, fallback="remote-file"),
            }
        ]

    if "html" not in content_type and b"<a" not in raw.lower():
        return final_url, []

    parser = AnchorLinkParser()
    parser.feed(decode_bytes(raw))

    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, label in parser.links:
        if not href:
            continue
        resolved = urljoin(final_url, href).split("#", 1)[0].strip()
        parsed = urlparse(resolved)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not has_supported_extension(resolved):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(
            {
                "url": resolved,
                "label": label or infer_filename_from_url(resolved, fallback="remote-file"),
            }
        )

    return final_url, candidates


def tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in WORD_RE.findall(text)]
    return [token for token in tokens if token not in CONJUNCTION_WORDS]


def scene_split(text: str, target_words: int = 130) -> list[str]:
    chapter_parts = re.split(r"\n\s*(?:chapter|scene)\b[^\n]*\n", text, flags=re.IGNORECASE)
    chapter_parts = [part.strip() for part in chapter_parts if part.strip()]
    if len(chapter_parts) >= 4:
        return chapter_parts

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return [text]

    scenes: list[str] = []
    buffer: list[str] = []
    words = 0

    for paragraph in paragraphs:
        p_words = len(WORD_RE.findall(paragraph))
        buffer.append(paragraph)
        words += p_words
        if words >= target_words:
            scenes.append("\n\n".join(buffer))
            buffer = []
            words = 0

    if buffer:
        scenes.append("\n\n".join(buffer))

    if len(scenes) == 1:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        fallback: list[str] = []
        sentence_buffer: list[str] = []
        for sentence in sentences:
            if sentence.strip():
                sentence_buffer.append(sentence.strip())
            if len(sentence_buffer) >= 5:
                fallback.append(" ".join(sentence_buffer))
                sentence_buffer = []
        if sentence_buffer:
            fallback.append(" ".join(sentence_buffer))
        if len(fallback) > 1:
            return fallback
    return scenes


def sentiment_score(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    positives = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negatives = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    total_hits = positives + negatives
    if total_hits == 0:
        return 0.0
    return round((positives - negatives) / total_hits, 4)


def classify_sentiment(score: float) -> str:
    if score > 0.15:
        return "positive"
    if score < -0.15:
        return "negative"
    return "neutral"


def detect_theme(tokens: list[str]) -> dict[str, Any]:
    theme_scores: list[dict[str, Any]] = []
    for theme, keywords in THEME_KEYWORDS.items():
        hits = sum(1 for token in tokens if token in keywords)
        if hits > 0:
            theme_scores.append({"theme": theme, "hits": hits})

    if not theme_scores:
        return {
            "primary": "General / Mixed",
            "confidence": 0.0,
            "top_themes": [],
        }

    theme_scores.sort(key=lambda item: (-item["hits"], item["theme"]))
    total_hits = sum(item["hits"] for item in theme_scores)
    primary = theme_scores[0]
    confidence = round(primary["hits"] / total_hits, 3) if total_hits else 0.0

    return {
        "primary": primary["theme"],
        "confidence": confidence,
        "top_themes": theme_scores[:4],
    }


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_person_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    cleaned = cleaned.strip(" ,.;:-")
    return cleaned


def person_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def is_likely_non_person_label(name: str) -> bool:
    words = re.findall(r"[A-Za-z]+", name)
    if not words:
        return True

    lowered = [word.lower() for word in words]
    if len(words) == 1:
        single = lowered[0]
        if single in NON_PERSON_TERMS_LOWER or single in CONJUNCTION_WORDS:
            return True
        if len(single) <= 2:
            return True

    if all(word in NON_PERSON_TERMS_LOWER for word in lowered):
        return True
    if any(word in {"chapter", "section", "figure", "table", "appendix"} for word in lowered):
        return True
    if lowered[-1] in ORG_SUFFIX_HINTS:
        return True
    return False


def sanitize_theme(theme: Any) -> dict[str, Any] | None:
    if not isinstance(theme, dict):
        return None
    primary = str(theme.get("primary") or "").strip()
    if not primary:
        return None

    try:
        confidence = float(theme.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    top_themes: list[dict[str, Any]] = []
    raw_top = theme.get("top_themes")
    if isinstance(raw_top, list):
        for item in raw_top[:6]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("theme") or "").strip()
            if not label:
                continue
            try:
                hits = int(item.get("hits", 0))
            except (TypeError, ValueError):
                hits = 0
            top_themes.append({"theme": label, "hits": max(0, hits)})

    return {
        "primary": primary,
        "confidence": round(confidence, 3),
        "top_themes": top_themes,
    }


def sanitize_people_profiles(
    raw_profiles: list[dict[str, Any]],
    top_n: int = 8,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue
        raw_name = normalize_person_name(str(item.get("name") or ""))
        if not raw_name or is_likely_non_person_label(raw_name):
            continue

        key = person_key(raw_name)
        if not key:
            continue

        aliases_raw = item.get("aliases")
        aliases_iter = aliases_raw if isinstance(aliases_raw, list) else []
        alias_set: set[str] = set()
        for alias in [raw_name, *aliases_iter]:
            alias_name = normalize_person_name(str(alias or ""))
            if not alias_name:
                continue
            if is_likely_non_person_label(alias_name) and alias_name != raw_name:
                continue
            alias_set.add(alias_name)
        if not alias_set:
            alias_set = {raw_name}

        try:
            weight = int(item.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1

        existing = merged.get(key)
        if not existing:
            merged[key] = {
                "name": raw_name,
                "aliases": set(alias_set),
                "weight": max(1, weight),
            }
            continue

        existing["aliases"].update(alias_set)
        existing["weight"] += max(1, weight)
        current_name = existing["name"]
        if raw_name.count(" ") > current_name.count(" "):
            existing["name"] = raw_name
        elif len(raw_name) > len(current_name) and raw_name.split(" ")[0] == current_name.split(" ")[0]:
            existing["name"] = raw_name

    alias_owner: dict[str, set[str]] = defaultdict(set)
    for key, item in merged.items():
        for alias in item["aliases"]:
            alias_owner[person_key(alias)].add(key)

    profiles: list[dict[str, Any]] = []
    for key, item in merged.items():
        canonical = item["name"]
        filtered_aliases = []
        for alias in item["aliases"]:
            alias_key = person_key(alias)
            if alias == canonical:
                filtered_aliases.append(alias)
                continue
            if " " in alias:
                filtered_aliases.append(alias)
                continue
            if len(alias_owner[alias_key]) == 1:
                filtered_aliases.append(alias)

        if canonical not in filtered_aliases:
            filtered_aliases.append(canonical)
        filtered_aliases = sorted(set(filtered_aliases), key=lambda value: (-len(value), value))
        profiles.append(
            {
                "name": canonical,
                "aliases": filtered_aliases,
                "weight": item["weight"],
            }
        )

    profiles.sort(key=lambda item: (-item["weight"], -item["name"].count(" "), item["name"].lower()))
    return profiles[:top_n]


def extract_theme_people_with_genai(
    text: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, str | None]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, None, "GenAI requested but OPENAI_API_KEY is not set; local analysis was used."

    body = {
        "model": GENAI_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract article theme and real human people only. "
                    "Merge name variations that refer to the same person. "
                    "Exclude organizations, locations, section labels, and repetitive terms. "
                    "Return strict JSON with keys: "
                    "{"
                    "\"theme\": {\"primary\": string, \"confidence\": number, "
                    "\"top_themes\": [{\"theme\": string, \"hits\": number}]}, "
                    "\"people\": [{\"name\": string, \"aliases\": [string]}]"
                    "}."
                ),
            },
            {"role": "user", "content": text[:GENAI_MAX_CHARS]},
        ],
    }

    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=28) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception as exc:  # noqa: BLE001 - network/runtime failures should gracefully fallback
        return None, None, f"GenAI request failed ({exc}); local analysis was used."

    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception:  # noqa: BLE001 - malformed response should gracefully fallback
        return None, None, "GenAI returned an invalid payload; local analysis was used."

    theme = sanitize_theme(parsed.get("theme"))
    people_raw = parsed.get("people")
    people = (
        sanitize_people_profiles(people_raw, top_n=12)
        if isinstance(people_raw, list)
        else None
    )
    return theme, people, None


def extract_people_profiles(text: str, top_n: int = 8) -> list[dict[str, Any]]:
    sentences = [line.strip() for line in re.split(r"(?<=[.!?])\s+", text) if line.strip()]
    sentence_lowers = [line.lower() for line in sentences]

    token_candidates = NAME_RE.findall(text)
    token_counts = Counter(
        token
        for token in token_candidates
        if token.lower() not in CHARACTER_STOPWORDS_LOWER
        and token.lower() not in CONJUNCTION_WORDS
    )

    full_counter = Counter()
    for left, right in FULL_NAME_RE.findall(text):
        full_name = normalize_person_name(f"{left} {right}")
        if is_likely_non_person_label(full_name):
            continue
        full_counter[full_name] += 1

    titled_tokens: set[str] = set()
    titled_fulls: set[str] = set()
    for left, right in TITLE_NAME_RE.findall(text):
        if right:
            full_name = normalize_person_name(f"{left} {right}")
            if not is_likely_non_person_label(full_name):
                titled_fulls.add(full_name)
                titled_tokens.add(left)
                titled_tokens.add(right)
        else:
            if not is_likely_non_person_label(left):
                titled_tokens.add(left)

    first_to_full: dict[str, set[str]] = defaultdict(set)
    last_to_full: dict[str, set[str]] = defaultdict(set)
    for full_name in full_counter:
        parts = full_name.split(" ")
        if len(parts) != 2:
            continue
        first, last = parts
        first_to_full[first].add(full_name)
        last_to_full[last].add(full_name)
    unique_first = {name: next(iter(matches)) for name, matches in first_to_full.items() if len(matches) == 1}
    unique_last = {name: next(iter(matches)) for name, matches in last_to_full.items() if len(matches) == 1}

    profile_map: dict[str, dict[str, Any]] = {}

    def upsert_profile(name: str, aliases: list[str], weight: int) -> None:
        canonical = normalize_person_name(name)
        if not canonical or is_likely_non_person_label(canonical):
            return
        key = person_key(canonical)
        if not key:
            return
        entry = profile_map.setdefault(
            key,
            {"name": canonical, "aliases": set(), "weight": 0},
        )
        if canonical.count(" ") > entry["name"].count(" "):
            entry["name"] = canonical
        entry["aliases"].update(aliases)
        entry["aliases"].add(canonical)
        entry["weight"] += max(1, weight)

    for full_name, count in full_counter.items():
        parts = full_name.split(" ")
        upsert_profile(full_name, [full_name, *parts], weight=count * 2)

    for full_name in titled_fulls:
        parts = full_name.split(" ")
        upsert_profile(full_name, [full_name, *parts], weight=4)

    for token, count in token_counts.items():
        token_lower = token.lower()
        if token_lower in NON_PERSON_TERMS_LOWER or is_likely_non_person_label(token):
            continue

        canonical = unique_first.get(token) or unique_last.get(token) or token
        ambiguous_token = (
            (token in first_to_full and len(first_to_full[token]) > 1)
            or (token in last_to_full and len(last_to_full[token]) > 1)
        )
        if ambiguous_token and canonical == token:
            continue
        context_hits = 0
        token_pattern = re.compile(rf"\b{re.escape(token.lower())}\b")
        for sentence_lower in sentence_lowers:
            if not token_pattern.search(sentence_lower):
                continue
            if any(re.search(rf"\b{hint}\b", sentence_lower) for hint in PERSON_CONTEXT_HINTS):
                context_hits += 1

        is_strong = (
            count >= 2
            or token in titled_tokens
            or canonical in full_counter
            or context_hits >= 1
        )
        if not is_strong:
            continue

        aliases = [token]
        if canonical != token:
            aliases.append(canonical)
        upsert_profile(canonical, aliases, weight=count + context_hits)

    raw_profiles = []
    for entry in profile_map.values():
        raw_profiles.append(
            {
                "name": entry["name"],
                "aliases": sorted(entry["aliases"], key=lambda value: (-len(value), value)),
                "weight": entry["weight"],
            }
        )
    return sanitize_people_profiles(raw_profiles, top_n=top_n)


def extract_characters(text: str, top_n: int = 8) -> list[str]:
    return [item["name"] for item in extract_people_profiles(text, top_n=top_n)]


def build_summary(theme: dict[str, Any], people: list[dict[str, Any]]) -> str:
    primary_theme = theme.get("primary", "General / Mixed")
    if not people:
        return (
            f"Primary theme appears to be {primary_theme}. "
            "No repeated person names were detected for reliable people-level sentiment."
        )

    most_positive = max(people, key=lambda item: item["score"])
    most_negative = min(people, key=lambda item: item["score"])
    return (
        f"Primary theme: {primary_theme}. "
        f"Most positive person sentiment: {most_positive['name']} ({most_positive['score']:+.2f}). "
        f"Most negative person sentiment: {most_negative['name']} ({most_negative['score']:+.2f})."
    )


def build_one_sentence_summary(theme: dict[str, Any], people: list[dict[str, Any]]) -> str:
    primary_theme = theme.get("primary", "General / Mixed")
    if not people:
        return (
            f"The primary theme appears to be {primary_theme}, but repeated person names were too limited for reliable people-level sentiment."
        )

    most_positive = max(people, key=lambda item: item["score"])
    most_negative = min(people, key=lambda item: item["score"])
    if most_positive["name"] == most_negative["name"]:
        return (
            f"The primary theme is {primary_theme}, and {most_positive['name']} carries the overall people sentiment at {most_positive['score']:+.2f}."
        )

    return (
        f"The primary theme is {primary_theme}, with {most_positive['name']} showing the most positive sentiment ({most_positive['score']:+.2f}) while {most_negative['name']} shows the most negative sentiment ({most_negative['score']:+.2f})."
    )


def analyze_text(text: str, use_genai: bool = False) -> tuple[dict[str, Any], str | None]:
    segments = scene_split(text)
    segment_sources = {index + 1: scene for index, scene in enumerate(segments)}
    tokens = tokenize(text)
    theme = detect_theme(tokens)
    analysis_warning: str | None = None

    heuristic_people = extract_people_profiles(text, top_n=12)
    people = heuristic_people
    genai_applied = False
    if use_genai:
        genai_theme, genai_people, genai_warning = extract_theme_people_with_genai(text)
        if genai_theme:
            theme = genai_theme
            genai_applied = True
        if genai_people:
            people = sanitize_people_profiles([*genai_people, *heuristic_people], top_n=12)
            genai_applied = True
        if genai_warning:
            analysis_warning = genai_warning

    people_data: list[dict[str, Any]] = []
    sentiment_distribution = defaultdict(int)

    for person in people:
        name = person["name"]
        aliases = person.get("aliases") or [name]
        alias_patterns = []
        for alias in aliases:
            escaped = re.escape(alias)
            if " " in alias:
                escaped = escaped.replace(r"\ ", r"\s+")
            alias_patterns.append(rf"\b{escaped}\b")
        pattern = re.compile("|".join(alias_patterns), flags=re.IGNORECASE)

        score_points: list[float] = []
        mention_count = 0
        evidence: list[str] = []
        trajectory: list[dict[str, Any]] = []

        for segment_index in range(1, len(segments) + 1):
            segment = segment_sources[segment_index]
            sentence_candidates = re.split(r"(?<=[.!?])\s+", segment)
            name_sentences = [line.strip() for line in sentence_candidates if pattern.search(line)]
            if not name_sentences:
                trajectory.append(
                    {
                        "scene_index": segment_index,
                        "score": None,
                        "present": False,
                    }
                )
                continue

            mention_count += len(name_sentences)
            if len(evidence) < 3:
                evidence.extend(name_sentences[: 3 - len(evidence)])

            score = sentiment_score(tokenize(" ".join(name_sentences)))
            score_points.append(score)
            trajectory.append(
                {
                    "scene_index": segment_index,
                    "score": score,
                    "present": True,
                }
            )

        if not score_points:
            continue

        avg_score = round(mean(score_points), 4)
        sentiment = classify_sentiment(avg_score)
        sentiment_distribution[sentiment] += 1
        people_data.append(
            {
                "name": name,
                "score": avg_score,
                "mentions": mention_count,
                "sentiment": sentiment,
                "trajectory": trajectory,
                "evidence": evidence[:2],
            }
        )

    people_data.sort(key=lambda item: (-item["mentions"], -abs(item["score"]), item["name"]))

    word_count = len(WORD_RE.findall(text))
    summary = build_summary(theme, people_data)
    one_sentence_summary = build_one_sentence_summary(theme, people_data)
    avg_people_sentiment = round(mean(item["score"] for item in people_data), 4) if people_data else 0.0

    return {
        "word_count": word_count,
        "segment_count": len(segments),
        "people_count": len(people_data),
        "avg_people_sentiment": avg_people_sentiment,
        "people_distribution": {
            "positive": sentiment_distribution["positive"],
            "neutral": sentiment_distribution["neutral"],
            "negative": sentiment_distribution["negative"],
        },
        "genai": {
            "requested": use_genai,
            "applied": genai_applied,
        },
        "theme": theme,
        "people_data": people_data,
        "character_data": people_data,
        "summary": summary,
        "one_sentence_summary": one_sentence_summary,
    }, analysis_warning


def make_submission_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{stamp}-{suffix}"


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/discover-files", methods=["POST"])
def discover_files() -> Any:
    body = request.get_json(silent=True) or {}
    source_url = (body.get("url") or "").strip()
    if not source_url:
        return jsonify({"error": "Provide a web link to discover files."}), 400

    try:
        resolved_url, files = discover_remote_files(source_url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "source_url": source_url,
            "resolved_url": resolved_url,
            "count": len(files),
            "files": files,
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze() -> Any:
    uploaded = request.files.get("file")
    pasted_text = (request.form.get("text") or "").strip()
    source_url = (request.form.get("source_url") or "").strip()
    source_mode = (request.form.get("source_mode") or "auto").strip().lower()
    use_genai = parse_bool(request.form.get("use_genai"))
    if source_mode not in {"auto", "webpage"}:
        source_mode = "auto"
    given_title = (request.form.get("title") or "").strip()

    text = ""
    warning = None
    source_name = "Pasted Text"

    if uploaded and uploaded.filename:
        raw = uploaded.read()
        text, warning = extract_upload_text(uploaded.filename, raw)
        source_name = uploaded.filename
    elif source_url:
        try:
            text, warning, source_name = extract_remote_text(source_url, source_mode=source_mode)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    elif pasted_text:
        text = normalize_text(pasted_text)

    if not text:
        return jsonify(
            {
                "error": "No readable text found. Upload a file, paste text, or provide a web link."
            }
        ), 400

    analysis, analysis_warning = analyze_text(text, use_genai=use_genai)
    warnings = [item for item in (warning, analysis_warning) if item]
    warning_text = " ".join(warnings) if warnings else None
    if source_name.startswith(("http://", "https://")):
        suggested_title = infer_filename_from_url(source_name, fallback="Web Link Submission")
    else:
        suggested_title = source_name
    title = given_title or suggested_title or "Untitled Submission"

    payload = {
        "id": make_submission_id(),
        "title": title,
        "source_name": source_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "warning": warning_text,
        "extracted_text": text,
        "analysis": analysis,
    }
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
