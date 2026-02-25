from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import joblib
    from sklearn.dummy import DummyClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependencies. Run `pip install -r requirements.txt` before training."
    ) from exc

from common import (
    ATMOSPHERE_LEXICON,
    PSYCHOLOGY_LEXICON,
    extract_people_profiles,
    iter_txt_files,
    keyword_label,
    read_text,
    sentence_mentions_aliases,
    split_scenes,
    split_sentences,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_DIR = ROOT / "training" / "data" / "raw" / "train"
DEFAULT_VAL_DIR = ROOT / "training" / "data" / "raw" / "val"
DEFAULT_MODELS_DIR = ROOT / "training" / "models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train local story-analysis models from txt files."
    )
    parser.add_argument("--train-dir", type=Path, default=DEFAULT_TRAIN_DIR)
    parser.add_argument("--val-dir", type=Path, default=DEFAULT_VAL_DIR)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--sentences-per-scene", type=int, default=6)
    parser.add_argument("--top-characters", type=int, default=120)
    return parser.parse_args()


def load_story_texts(folder: Path) -> list[tuple[Path, str]]:
    stories: list[tuple[Path, str]] = []
    for txt_path in iter_txt_files(folder):
        text = read_text(txt_path)
        if text:
            stories.append((txt_path, text))
    return stories


def build_character_catalog(
    stories: list[tuple[Path, str]], top_characters: int
) -> dict[str, Any]:
    name_counts: Counter[str] = Counter()
    alias_map: defaultdict[str, set[str]] = defaultdict(set)

    for _, text in stories:
        for profile in extract_people_profiles(text, top_n=24):
            name = str(profile.get("name") or "").strip()
            if not name:
                continue
            weight = int(profile.get("weight") or 1)
            aliases = [alias for alias in profile.get("aliases", []) if alias]

            name_counts[name] += max(1, weight)
            alias_map[name].add(name)
            for alias in aliases:
                alias_map[name].add(alias)

    catalog = []
    for name, count in name_counts.most_common(max(1, top_characters)):
        catalog.append(
            {
                "name": name,
                "weight": count,
                "aliases": sorted(alias_map[name], key=lambda item: (-len(item), item))[:10],
            }
        )

    return {
        "version": "v1",
        "size": len(catalog),
        "characters": catalog,
    }


def collect_psychology_samples(
    stories: list[tuple[Path, str]],
) -> tuple[list[str], list[str]]:
    samples: list[str] = []
    labels: list[str] = []

    for _, text in stories:
        profiles = extract_people_profiles(text, top_n=18)
        alias_groups = [
            [str(alias) for alias in profile.get("aliases", []) if alias]
            or [str(profile.get("name") or "")]
            for profile in profiles
        ]

        for sentence in split_sentences(text):
            has_person_mention = any(
                sentence_mentions_aliases(sentence, aliases)
                for aliases in alias_groups
                if aliases
            )
            if not has_person_mention:
                continue

            label = keyword_label(sentence, PSYCHOLOGY_LEXICON, default="neutral")
            samples.append(sentence)
            labels.append(label)

    if not samples:
        for _, text in stories:
            for sentence in split_sentences(text):
                label = keyword_label(sentence, PSYCHOLOGY_LEXICON, default="neutral")
                samples.append(sentence)
                labels.append(label)

    if not samples:
        samples = ["neutral context"]
        labels = ["neutral"]

    return samples, labels


def collect_atmosphere_samples(
    stories: list[tuple[Path, str]],
    sentences_per_scene: int,
) -> tuple[list[str], list[str]]:
    samples: list[str] = []
    labels: list[str] = []

    for _, text in stories:
        for scene in split_scenes(text, sentences_per_scene=sentences_per_scene):
            label = keyword_label(scene, ATMOSPHERE_LEXICON, default="neutral")
            samples.append(scene)
            labels.append(label)

    if not samples:
        samples = ["neutral atmosphere"]
        labels = ["neutral"]

    return samples, labels


def train_text_classifier(samples: list[str], labels: list[str]) -> Pipeline:
    classes = set(labels)
    if len(classes) >= 2:
        clf = LogisticRegression(max_iter=400, class_weight="balanced")
    else:
        clf = DummyClassifier(strategy="most_frequent")

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=30000)),
            ("clf", clf),
        ]
    )
    pipeline.fit(samples, labels)
    return pipeline


def evaluate_model(
    model: Pipeline,
    samples: list[str],
    labels: list[str],
) -> float | None:
    if not samples or not labels:
        return None
    if len(samples) != len(labels):
        return None
    try:
        return float(model.score(samples, labels))
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    train_stories = load_story_texts(args.train_dir)
    val_stories = load_story_texts(args.val_dir)

    if not train_stories:
        raise SystemExit(
            f"No training txt found under: {args.train_dir}\n"
            "Place .txt files there and run again."
        )

    args.models_dir.mkdir(parents=True, exist_ok=True)

    character_catalog = build_character_catalog(train_stories, top_characters=args.top_characters)

    psych_x_train, psych_y_train = collect_psychology_samples(train_stories)
    atm_x_train, atm_y_train = collect_atmosphere_samples(
        train_stories,
        sentences_per_scene=args.sentences_per_scene,
    )

    psych_model = train_text_classifier(psych_x_train, psych_y_train)
    atmosphere_model = train_text_classifier(atm_x_train, atm_y_train)

    psych_val_score = None
    atmosphere_val_score = None
    if val_stories:
        psych_x_val, psych_y_val = collect_psychology_samples(val_stories)
        atm_x_val, atm_y_val = collect_atmosphere_samples(
            val_stories,
            sentences_per_scene=args.sentences_per_scene,
        )
        psych_val_score = evaluate_model(psych_model, psych_x_val, psych_y_val)
        atmosphere_val_score = evaluate_model(atmosphere_model, atm_x_val, atm_y_val)

    psych_model_path = args.models_dir / "psychology_model.joblib"
    atmosphere_model_path = args.models_dir / "atmosphere_model.joblib"
    characters_path = args.models_dir / "character_catalog.json"
    report_path = args.models_dir / "training_report.json"

    joblib.dump(psych_model, psych_model_path)
    joblib.dump(atmosphere_model, atmosphere_model_path)
    characters_path.write_text(
        json.dumps(character_catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "train": {
            "files": len(train_stories),
            "psychology_samples": len(psych_x_train),
            "atmosphere_samples": len(atm_x_train),
            "psychology_labels": dict(Counter(psych_y_train)),
            "atmosphere_labels": dict(Counter(atm_y_train)),
        },
        "validation": {
            "files": len(val_stories),
            "psychology_accuracy": psych_val_score,
            "atmosphere_accuracy": atmosphere_val_score,
        },
        "artifacts": {
            "psychology_model": str(psych_model_path),
            "atmosphere_model": str(atmosphere_model_path),
            "character_catalog": str(characters_path),
        },
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Training complete.")
    print(f"- Train files: {len(train_stories)}")
    print(f"- Psychology samples: {len(psych_x_train)}")
    print(f"- Atmosphere samples: {len(atm_x_train)}")
    print(f"- Saved: {psych_model_path}")
    print(f"- Saved: {atmosphere_model_path}")
    print(f"- Saved: {characters_path}")
    print(f"- Report: {report_path}")


if __name__ == "__main__":
    main()
