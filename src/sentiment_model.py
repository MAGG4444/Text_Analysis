import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple


TONE_POSITIVE_THRESHOLD = 0.2
TONE_NEGATIVE_THRESHOLD = -0.2

EMOTION_LEXICON = {
    "joy": {
        "hope",
        "joy",
        "glad",
        "grateful",
        "happy",
        "laugh",
        "laughed",
        "laughing",
        "love",
        "relief",
        "relieved",
        "smile",
        "smiled",
        "smiling",
        "warmth",
    },
    "sadness": {
        "alone",
        "cried",
        "crying",
        "despair",
        "empty",
        "grief",
        "lonely",
        "regret",
        "sad",
        "sorrow",
        "tearful",
        "tears",
        "tired",
        "unhappy",
        "weep",
    },
    "anger": {
        "angry",
        "bitter",
        "furious",
        "fury",
        "mad",
        "rage",
        "resentment",
        "shouted",
        "tense",
        "yelled",
    },
    "fear": {
        "afraid",
        "anxious",
        "fear",
        "frightened",
        "nervous",
        "panic",
        "panicked",
        "scared",
        "terrified",
        "trembled",
        "uncertain",
        "worried",
    },
}

POSITIVE_WORDS = {
    "bright",
    "calm",
    "comfort",
    "fragile",
    "good",
    "grace",
    "happy",
    "hope",
    "hopeful",
    "joy",
    "kind",
    "laughed",
    "laughing",
    "love",
    "peace",
    "relief",
    "relieved",
    "safe",
    "smile",
    "smiled",
    "smiling",
    "warm",
}

NEGATIVE_WORDS = {
    "afraid",
    "angry",
    "bitter",
    "broken",
    "bruise",
    "cold",
    "damage",
    "dark",
    "fear",
    "grief",
    "hurt",
    "loss",
    "lost",
    "sad",
    "sadness",
    "shout",
    "shouted",
    "tense",
    "tired",
    "uncertain",
    "worry",
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _tone_label_from_score(score: float) -> str:
    if score >= TONE_POSITIVE_THRESHOLD:
        return "positive"
    if score <= TONE_NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


class NarrativeEmotionAnalyzer:
    """Baseline analyzer with optional local-model support and safe fallbacks."""

    def __init__(self, models_dir: str | Path = "models", logger: logging.Logger | None = None) -> None:
        self.models_dir = Path(models_dir)
        self.logger = logger or logging.getLogger(__name__)
        self.sentiment_pipeline, self.sentiment_source = self._load_sentiment_pipeline()
        self.emotion_pipeline, self.emotion_source = self._load_emotion_pipeline()
        self.vader_analyzer = self._load_vader_analyzer()

    def _load_sentiment_pipeline(self):
        try:
            from transformers import pipeline

            candidates = []
            local_model = self.models_dir / "sentiment"
            if local_model.exists():
                candidates.append(str(local_model))
            candidates.append("distilbert-base-uncased-finetuned-sst-2-english")

            for candidate in candidates:
                try:
                    sentiment_pipeline = pipeline(
                        "sentiment-analysis",
                        model=candidate,
                        tokenizer=candidate,
                        local_files_only=True,
                    )
                    self.logger.info("Loaded transformer sentiment model from %s", candidate)
                    return sentiment_pipeline, f"transformer:{candidate}"
                except Exception as exc:
                    self.logger.info("Sentiment model unavailable at %s: %s", candidate, exc)
        except Exception as exc:
            self.logger.info("Transformers not available for sentiment analysis: %s", exc)

        self.logger.info("Using lexicon-based scene tone fallback.")
        return None, "lexicon"

    def _load_emotion_pipeline(self):
        try:
            from transformers import pipeline

            candidates = []
            local_model = self.models_dir / "emotion"
            if local_model.exists():
                candidates.append(str(local_model))
            candidates.append("j-hartmann/emotion-english-distilroberta-base")

            for candidate in candidates:
                try:
                    emotion_pipeline = pipeline(
                        "text-classification",
                        model=candidate,
                        tokenizer=candidate,
                        local_files_only=True,
                        top_k=None,
                    )
                    self.logger.info("Loaded transformer emotion model from %s", candidate)
                    return emotion_pipeline, f"transformer:{candidate}"
                except Exception as exc:
                    self.logger.info("Emotion model unavailable at %s: %s", candidate, exc)
        except Exception as exc:
            self.logger.info("Transformers not available for emotion analysis: %s", exc)

        self.logger.info("Using rule-based character emotion fallback.")
        return None, "rule_based"

    def _load_vader_analyzer(self):
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self.logger.info("Loaded VADER sentiment fallback.")
            return SentimentIntensityAnalyzer()
        except Exception as exc:
            self.logger.info("VADER unavailable, using handcrafted tone lexicon: %s", exc)
            return None

    def _score_with_transformer(self, text: str) -> float:
        truncated_text = text[:2048]
        result = self.sentiment_pipeline(truncated_text)[0]
        label = str(result.get("label", "")).lower()
        confidence = float(result.get("score", 0.0))

        if "positive" in label or label.startswith("pos"):
            return _clamp(confidence, -1.0, 1.0)
        if "negative" in label or label.startswith("neg"):
            return _clamp(-confidence, -1.0, 1.0)

        if "1" in label or "2" in label:
            return _clamp(-(confidence or 0.5), -1.0, 1.0)
        if "4" in label or "5" in label:
            return _clamp(confidence or 0.5, -1.0, 1.0)
        return 0.0

    def _score_with_lexicon(self, text: str) -> float:
        if self.vader_analyzer is not None:
            return float(self.vader_analyzer.polarity_scores(text)["compound"])

        tokens = _tokenize(text)
        if not tokens:
            return 0.0

        positive_hits = sum(1 for token in tokens if token in POSITIVE_WORDS)
        negative_hits = sum(1 for token in tokens if token in NEGATIVE_WORDS)
        score = (positive_hits - negative_hits) / max(len(tokens), 1)
        return _clamp(score * 4.0, -1.0, 1.0)

    def score_tone(self, text: str) -> float:
        try:
            if self.sentiment_pipeline is not None:
                return self._score_with_transformer(text)
        except Exception as exc:
            self.logger.warning("Transformer tone scoring failed, falling back: %s", exc)
        return self._score_with_lexicon(text)

    def analyze_scene_tones(self, scenes: List[Dict[str, str | int | list[int]]]) -> List[Dict[str, str | float | int]]:
        results: List[Dict[str, str | float | int]] = []

        for scene in scenes:
            scene_id = int(scene["scene_id"])
            text = str(scene["text"])
            tone_score = round(self.score_tone(text), 4)
            results.append(
                {
                    "scene_id": scene_id,
                    "tone_label": _tone_label_from_score(tone_score),
                    "tone_score": tone_score,
                }
            )

        return results

    def _extract_character_context(self, scene_text: str, character: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", scene_text.strip())
        if not sentences:
            return scene_text

        pattern = re.compile(rf"\b{re.escape(character)}\b", flags=re.IGNORECASE)
        matching_indices = [index for index, sentence in enumerate(sentences) if pattern.search(sentence)]

        if not matching_indices:
            return scene_text

        selected_sentences: List[str] = []
        seen_indices = set()
        for index in matching_indices:
            for offset in (-1, 0, 1):
                candidate_index = index + offset
                if 0 <= candidate_index < len(sentences) and candidate_index not in seen_indices:
                    selected_sentences.append(sentences[candidate_index])
                    seen_indices.add(candidate_index)

        return " ".join(selected_sentences).strip()

    def _map_emotion_label(self, raw_label: str) -> str:
        label = raw_label.lower()
        if "joy" in label or label in {"love", "optimism", "amusement", "admiration", "excitement"}:
            return "joy"
        if "sad" in label or label in {"grief", "disappointment", "remorse"}:
            return "sadness"
        if "anger" in label or label in {"annoyance", "disapproval", "disgust"}:
            return "anger"
        if "fear" in label or label in {"nervousness"}:
            return "fear"
        return "neutral"

    def _analyze_emotion_with_model(self, character: str, context_text: str) -> Tuple[str, float]:
        model_input = f"Character: {character}. Context: {context_text[:1500]}"
        outputs = self.emotion_pipeline(model_input)
        if outputs and isinstance(outputs[0], list):
            outputs = outputs[0]

        if not outputs:
            return "neutral", 0.0

        best_output = max(outputs, key=lambda item: float(item.get("score", 0.0)))
        label = self._map_emotion_label(str(best_output.get("label", "neutral")))
        score = float(best_output.get("score", 0.0))
        if label == "neutral":
            score = min(score, 0.5)
        return label, round(_clamp(score, 0.0, 1.0), 4)

    def _analyze_emotion_rule_based(self, context_text: str) -> Tuple[str, float]:
        tokens = _tokenize(context_text)
        counts = {emotion: 0 for emotion in EMOTION_LEXICON}
        last_seen = {emotion: -1 for emotion in EMOTION_LEXICON}

        for index, token in enumerate(tokens):
            for emotion, lexicon in EMOTION_LEXICON.items():
                if token in lexicon:
                    counts[emotion] += 1
                    last_seen[emotion] = index

        total_hits = sum(counts.values())
        if total_hits == 0:
            tone_score = self._score_with_lexicon(context_text)
            if tone_score >= 0.25:
                return "joy", round(_clamp(abs(tone_score), 0.0, 1.0), 4)
            if tone_score <= -0.45:
                return "sadness", round(_clamp(abs(tone_score), 0.0, 1.0), 4)
            return "neutral", 0.0

        highest_count = max(counts.values())
        candidate_emotions = [emotion for emotion, count in counts.items() if count == highest_count]
        dominant_emotion = max(candidate_emotions, key=lambda emotion: last_seen.get(emotion, -1))
        confidence = counts[dominant_emotion] / total_hits
        return dominant_emotion, round(_clamp(confidence, 0.0, 1.0), 4)

    def analyze_character_emotions(
        self,
        scenes: List[Dict[str, str | int | list[int]]],
        scene_character_map: Dict[int, List[str]],
    ) -> List[Dict[str, str | float | int]]:
        results: List[Dict[str, str | float | int]] = []

        for scene in scenes:
            scene_id = int(scene["scene_id"])
            scene_text = str(scene["text"])
            characters = scene_character_map.get(scene_id, [])

            for character in characters:
                context_text = self._extract_character_context(scene_text, character)
                try:
                    if self.emotion_pipeline is not None:
                        label, score = self._analyze_emotion_with_model(character, context_text)
                    else:
                        label, score = self._analyze_emotion_rule_based(context_text)
                except Exception as exc:
                    self.logger.warning(
                        "Emotion analysis failed for %s in scene %s, using fallback: %s",
                        character,
                        scene_id,
                        exc,
                    )
                    label, score = self._analyze_emotion_rule_based(context_text)

                results.append(
                    {
                        "scene_id": scene_id,
                        "character": character,
                        "emotion_label": label,
                        "emotion_score": round(_clamp(score, 0.0, 1.0), 4),
                    }
                )

        return results
