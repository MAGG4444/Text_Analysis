from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import joblib
    import matplotlib.pyplot as plt
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependencies. Run `pip install -r requirements.txt` before analysis."
    ) from exc

from common import (
    extract_people_profiles,
    read_text,
    sentence_mentions_aliases,
    split_scenes,
    split_sentences,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_DIR = ROOT / "training" / "models"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze one story with local trained models and produce charts."
    )
    parser.add_argument("--input", type=Path, required=True, help="Path to one txt story file")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sentences-per-scene", type=int, default=6)
    parser.add_argument("--top-characters", type=int, default=8)
    return parser.parse_args()


def load_models(models_dir: Path) -> tuple[Any, Any, dict[str, Any]]:
    psychology_model_path = models_dir / "psychology_model.joblib"
    atmosphere_model_path = models_dir / "atmosphere_model.joblib"
    character_catalog_path = models_dir / "character_catalog.json"

    if not psychology_model_path.exists() or not atmosphere_model_path.exists():
        raise SystemExit(
            f"Missing model files in {models_dir}. Run train_models.py first."
        )

    psychology_model = joblib.load(psychology_model_path)
    atmosphere_model = joblib.load(atmosphere_model_path)

    if character_catalog_path.exists():
        catalog = json.loads(character_catalog_path.read_text(encoding="utf-8"))
    else:
        catalog = {"characters": []}

    return psychology_model, atmosphere_model, catalog


def build_character_pool(text: str, catalog: dict[str, Any], top_characters: int) -> list[dict[str, Any]]:
    extracted = extract_people_profiles(text, top_n=max(12, top_characters * 2))
    merged: dict[str, dict[str, Any]] = {}

    for profile in extracted:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        aliases = [str(alias).strip() for alias in profile.get("aliases", []) if alias]
        weight = int(profile.get("weight") or 1)
        merged[name] = {
            "name": name,
            "aliases": sorted(set(aliases + [name])),
            "weight": weight,
        }

    for item in catalog.get("characters", []):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        aliases = [str(alias).strip() for alias in item.get("aliases", []) if alias]
        aliases = sorted(set(aliases + [name]))

        mentioned = sentence_mentions_aliases(text, aliases)
        if not mentioned:
            continue

        if name not in merged:
            merged[name] = {
                "name": name,
                "aliases": aliases,
                "weight": int(item.get("weight") or 1),
            }

    ranked = sorted(merged.values(), key=lambda obj: (-obj["weight"], obj["name"]))
    return ranked[: max(1, top_characters)]


def majority_label(labels: list[str]) -> str | None:
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]


def model_predict_with_confidence(model: Any, texts: list[str]) -> tuple[list[str], list[float | None]]:
    labels = [str(label) for label in model.predict(texts)]

    confidences: list[float | None] = [None] * len(texts)
    if hasattr(model, "predict_proba"):
        try:
            probs = model.predict_proba(texts)
            confidences = [float(max(row)) for row in probs]
        except Exception:
            pass

    return labels, confidences


def plot_atmosphere_timeline(
    scene_labels: list[str],
    output_path: Path,
) -> None:
    if not scene_labels:
        return

    ordered_labels = sorted(set(scene_labels))
    y_map = {label: idx for idx, label in enumerate(ordered_labels)}

    x_vals = list(range(1, len(scene_labels) + 1))
    y_vals = [y_map[label] for label in scene_labels]

    plt.figure(figsize=(10, 4.5))
    plt.plot(x_vals, y_vals, marker="o", linewidth=2)
    plt.yticks(list(y_map.values()), list(y_map.keys()))
    plt.xticks(x_vals)
    plt.xlabel("Scene Index")
    plt.ylabel("Atmosphere")
    plt.title("Story Atmosphere Timeline")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close()


def plot_character_mentions(
    character_results: list[dict[str, Any]],
    total_scenes: int,
    output_path: Path,
) -> None:
    if not character_results or total_scenes <= 0:
        return

    x_vals = list(range(1, total_scenes + 1))

    plt.figure(figsize=(10, 4.5))
    for item in character_results:
        mentions = item.get("mentions_by_scene", [])
        if not mentions:
            continue
        if len(mentions) < total_scenes:
            mentions = mentions + [0] * (total_scenes - len(mentions))
        plt.plot(x_vals, mentions[:total_scenes], marker="o", linewidth=1.8, label=item["name"])

    plt.xticks(x_vals)
    plt.xlabel("Scene Index")
    plt.ylabel("Mentions")
    plt.title("Character Mentions by Scene")
    plt.grid(alpha=0.25)
    plt.legend(loc="upper right", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close()


def plot_character_psychology(
    character_results: list[dict[str, Any]],
    output_path: Path,
) -> None:
    if not character_results:
        return

    label_set: set[str] = set()
    for item in character_results:
        label_set.update(item.get("psychology_counts", {}).keys())
    labels = sorted(label_set)
    if not labels:
        return

    names = [item["name"] for item in character_results]
    x_vals = list(range(len(names)))
    bottoms = [0] * len(names)

    plt.figure(figsize=(10, 5))
    for label in labels:
        values = [int(item.get("psychology_counts", {}).get(label, 0)) for item in character_results]
        plt.bar(x_vals, values, bottom=bottoms, label=label)
        bottoms = [b + v for b, v in zip(bottoms, values)]

    plt.xticks(x_vals, names, rotation=25, ha="right")
    plt.ylabel("Sentence Count")
    plt.title("Character Psychology Distribution")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140)
    plt.close()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    psychology_model, atmosphere_model, catalog = load_models(args.models_dir)

    text = read_text(args.input)
    if not text:
        raise SystemExit("Input story is empty after text normalization.")

    scenes = split_scenes(text, sentences_per_scene=args.sentences_per_scene)
    characters = build_character_pool(text, catalog, top_characters=args.top_characters)

    scene_labels: list[str] = []
    scene_confidences: list[float | None] = []
    if scenes:
        scene_labels, scene_confidences = model_predict_with_confidence(atmosphere_model, scenes)

    character_results: list[dict[str, Any]] = []
    for character in characters:
        aliases = character.get("aliases", [character["name"]])
        mentions_by_scene: list[int] = []
        trajectory: list[dict[str, Any]] = []
        mentioned_sentences: list[str] = []

        for scene_index, scene_text in enumerate(scenes, start=1):
            scene_sentences = split_sentences(scene_text)
            matched = [
                sentence
                for sentence in scene_sentences
                if sentence_mentions_aliases(sentence, aliases)
            ]
            mentions_by_scene.append(len(matched))

            if matched:
                labels, _ = model_predict_with_confidence(psychology_model, matched)
                dominant = majority_label(labels)
                trajectory.append(
                    {
                        "scene_index": scene_index,
                        "mentions": len(matched),
                        "psychology": dominant,
                    }
                )
                mentioned_sentences.extend(matched)
            else:
                trajectory.append(
                    {
                        "scene_index": scene_index,
                        "mentions": 0,
                        "psychology": None,
                    }
                )

        if not mentioned_sentences:
            continue

        labels, _ = model_predict_with_confidence(psychology_model, mentioned_sentences)
        psych_counter = Counter(labels)

        character_results.append(
            {
                "name": character["name"],
                "aliases": aliases,
                "total_mentions": sum(mentions_by_scene),
                "dominant_psychology": majority_label(labels),
                "psychology_counts": dict(psych_counter),
                "mentions_by_scene": mentions_by_scene,
                "trajectory": trajectory,
            }
        )

    character_results.sort(
        key=lambda item: (-item.get("total_mentions", 0), item.get("name", ""))
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    atmosphere_chart = args.output_dir / "atmosphere_timeline.png"
    mentions_chart = args.output_dir / "character_mentions_timeline.png"
    psychology_chart = args.output_dir / "character_psychology_distribution.png"

    plot_atmosphere_timeline(scene_labels, atmosphere_chart)
    plot_character_mentions(character_results, len(scenes), mentions_chart)
    plot_character_psychology(character_results, psychology_chart)

    summary = {
        "story_file": str(args.input),
        "scene_count": len(scenes),
        "character_count": len(character_results),
        "characters": character_results,
        "atmosphere": [
            {
                "scene_index": idx + 1,
                "label": label,
                "confidence": scene_confidences[idx],
            }
            for idx, label in enumerate(scene_labels)
        ],
        "charts": {
            "atmosphere_timeline": str(atmosphere_chart),
            "character_mentions_timeline": str(mentions_chart),
            "character_psychology_distribution": str(psychology_chart),
        },
    }

    output_json = args.output_dir / "analysis_result.json"
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Analysis complete.")
    print(f"- Story: {args.input}")
    print(f"- Characters: {len(character_results)}")
    print(f"- Scenes: {len(scenes)}")
    print(f"- Output JSON: {output_json}")
    print(f"- Chart: {atmosphere_chart}")
    print(f"- Chart: {mentions_chart}")
    print(f"- Chart: {psychology_chart}")


if __name__ == "__main__":
    main()
