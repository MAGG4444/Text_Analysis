import logging
import re
from collections import Counter, defaultdict
from typing import DefaultDict, Dict, Iterable, List, Set, Tuple


COMMON_NON_NAMES = {
    "A",
    "After",
    "All",
    "An",
    "And",
    "As",
    "At",
    "Autumn",
    "But",
    "For",
    "Friday",
    "He",
    "Her",
    "His",
    "I",
    "If",
    "In",
    "It",
    "Later",
    "Monday",
    "Morning",
    "Night",
    "No",
    "On",
    "Saturday",
    "She",
    "Spring",
    "Summer",
    "Sunday",
    "The",
    "Then",
    "They",
    "Thursday",
    "Tuesday",
    "Wednesday",
    "We",
    "Winter",
    "Yes",
    "You",
}

TITLE_TOKENS = {"mr", "mrs", "ms", "dr", "prof", "sir", "lady"}
SPEAKER_VERBS = (
    "said",
    "asked",
    "replied",
    "cried",
    "shouted",
    "whispered",
    "yelled",
    "murmured",
    "called",
    "told",
)

NAME_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
    r"|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)


def _canonicalize_name(candidate: str) -> Tuple[str | None, Set[str]]:
    cleaned = re.sub(r"[^A-Za-z\s'-]", "", candidate).strip()
    if not cleaned:
        return None, set()

    raw_tokens = [token for token in cleaned.split() if token]
    tokens = [token for token in raw_tokens if token.lower().rstrip(".") not in TITLE_TOKENS]
    if not tokens:
        return None, set()

    canonical = tokens[0].title()
    if canonical in COMMON_NON_NAMES or len(canonical) < 2:
        return None, set()

    aliases = {canonical}
    aliases.add(" ".join(token.title() for token in tokens))
    if len(tokens) > 1:
        aliases.add(tokens[-1].title())
    return canonical, aliases


def _register_candidate(
    candidate: str,
    counts: Counter,
    aliases: DefaultDict[str, Set[str]],
    weight: int = 1,
) -> None:
    canonical, candidate_aliases = _canonicalize_name(candidate)
    if not canonical:
        return
    counts[canonical] += weight
    aliases[canonical].update(candidate_aliases)


def _extract_spacy_entities(
    text: str,
    logger: logging.Logger | None = None,
) -> Tuple[Counter, DefaultDict[str, Set[str]]]:
    counts: Counter = Counter()
    aliases: DefaultDict[str, Set[str]] = defaultdict(set)

    try:
        import spacy

        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception as exc:
            if logger:
                logger.info("spaCy installed but en_core_web_sm unavailable: %s", exc)
            return counts, aliases

        doc = nlp(text)
        for entity in doc.ents:
            if entity.label_ == "PERSON":
                _register_candidate(entity.text, counts, aliases, weight=2)
    except Exception as exc:
        if logger:
            logger.info("spaCy person extraction unavailable, using fallback: %s", exc)

    return counts, aliases


def _extract_rule_based_candidates(text: str) -> Tuple[Counter, DefaultDict[str, Set[str]]]:
    counts: Counter = Counter()
    aliases: DefaultDict[str, Set[str]] = defaultdict(set)

    for match in NAME_PATTERN.finditer(text):
        _register_candidate(match.group(0), counts, aliases, weight=1)

    speaker_pattern = re.compile(
        rf"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:{'|'.join(SPEAKER_VERBS)})\b"
        rf"|\b(?:{'|'.join(SPEAKER_VERBS)})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    )
    for match in speaker_pattern.finditer(text):
        candidate = match.group(1) or match.group(2)
        if candidate:
            _register_candidate(candidate, counts, aliases, weight=2)

    return counts, aliases


def _merge_alias_maps(
    destination: DefaultDict[str, Set[str]],
    source: Dict[str, Iterable[str]],
) -> None:
    for key, values in source.items():
        destination[key].update(values)


def extract_major_characters(
    paragraphs: List[Dict[str, str | int]],
    scenes: List[Dict[str, str | int | list[int]]],
    max_characters: int = 5,
    min_frequency: int = 2,
    logger: logging.Logger | None = None,
) -> Tuple[List[str], Dict[str, int], Dict[str, List[str]]]:
    """Extract major characters and the aliases used to find them."""
    full_text = "\n\n".join(str(paragraph["text"]) for paragraph in paragraphs)

    spacy_counts, spacy_aliases = _extract_spacy_entities(full_text, logger=logger)
    rule_counts, rule_aliases = _extract_rule_based_candidates(full_text)

    combined_counts: Counter = Counter()
    combined_aliases: DefaultDict[str, Set[str]] = defaultdict(set)
    combined_counts.update(rule_counts)
    combined_counts.update(spacy_counts)
    _merge_alias_maps(combined_aliases, rule_aliases)
    _merge_alias_maps(combined_aliases, spacy_aliases)

    if not combined_counts:
        if logger:
            logger.warning("No character candidates were detected.")
        return [], {}, {}

    major_characters = [
        character
        for character, count in combined_counts.most_common()
        if count >= min_frequency
    ][:max_characters]

    if not major_characters:
        major_characters = [character for character, _ in combined_counts.most_common(max_characters)]

    major_aliases = {
        character: sorted(combined_aliases.get(character, {character}))
        for character in major_characters
    }

    if logger:
        logger.info(
            "Selected major characters: %s",
            ", ".join(major_characters) if major_characters else "none",
        )

    return major_characters, dict(combined_counts), major_aliases


def associate_characters_to_scenes(
    scenes: List[Dict[str, str | int | list[int]]],
    major_characters: List[str],
    alias_map: Dict[str, List[str]],
) -> List[Dict[str, List[str] | int]]:
    """Assign major characters to scenes where they are explicitly mentioned."""
    associations: List[Dict[str, List[str] | int]] = []

    for scene in scenes:
        scene_text = str(scene["text"])
        found_characters: List[str] = []

        for character in major_characters:
            aliases = alias_map.get(character, [character])
            if any(re.search(rf"\b{re.escape(alias)}\b", scene_text, flags=re.IGNORECASE) for alias in aliases):
                found_characters.append(character)

        associations.append({"scene_id": int(scene["scene_id"]), "characters": found_characters})

    return associations
