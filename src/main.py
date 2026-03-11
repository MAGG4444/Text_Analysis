import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from character_extraction import associate_characters_to_scenes, extract_major_characters
from preprocess import preprocess_text_file
from segmentation import build_scenes
from sentiment_model import NarrativeEmotionAnalyzer
from trajectory import (
    build_character_trajectories,
    build_overall_tone_trajectory,
    smooth_character_trajectories,
    smooth_overall_tone_trajectory,
)
from utils import configure_logging, ensure_directory, save_json
from visualization import plot_character_emotion_trajectories, plot_overall_tone_trajectory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baseline narrative analyzer for scene tone and character emotion trajectories."
    )
    parser.add_argument("--input", required=True, help="Path to the input .txt file.")
    parser.add_argument("--output", required=True, help="Directory for JSON and PNG outputs.")
    parser.add_argument("--models-dir", default="models", help="Directory that may contain optional local models.")
    parser.add_argument("--max-characters", type=int, default=5, help="Maximum number of major characters to keep.")
    parser.add_argument(
        "--min-character-frequency",
        type=int,
        default=2,
        help="Minimum detected frequency required to keep a character as major before falling back to top-N.",
    )
    parser.add_argument(
        "--smooth-window",
        type=int,
        default=1,
        help="Optional moving-average window size for trajectory smoothing.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level, for example INFO or DEBUG.")
    return parser.parse_args()


def run_pipeline(args: argparse.Namespace) -> dict:
    logger = configure_logging(args.log_level)
    output_dir = ensure_directory(args.output)
    logger.info("Starting narrative analysis for %s", args.input)

    logger.info("Step 1: loading and splitting paragraphs")
    paragraphs = preprocess_text_file(args.input)
    if not paragraphs:
        raise ValueError("The input file did not produce any paragraphs after preprocessing.")
    logger.info("Loaded %d paragraphs", len(paragraphs))

    logger.info("Step 2: generating baseline scene structure")
    scenes = build_scenes(paragraphs)
    logger.info("Generated %d scenes", len(scenes))

    logger.info("Step 3: extracting characters and associating them to scenes")
    major_characters, character_frequencies, alias_map = extract_major_characters(
        paragraphs=paragraphs,
        scenes=scenes,
        max_characters=args.max_characters,
        min_frequency=args.min_character_frequency,
        logger=logger,
    )
    scene_characters = associate_characters_to_scenes(scenes, major_characters, alias_map)
    scene_character_map = {
        int(item["scene_id"]): [str(character) for character in item["characters"]]
        for item in scene_characters
    }
    logger.info("Associated characters across %d scenes", len(scene_characters))

    logger.info("Step 4: analyzing scene-level overall tone")
    analyzer = NarrativeEmotionAnalyzer(models_dir=args.models_dir, logger=logger)
    overall_tone = analyzer.analyze_scene_tones(scenes)

    logger.info("Step 5: analyzing scene-character emotions")
    character_emotions = analyzer.analyze_character_emotions(scenes, scene_character_map)

    logger.info("Step 6: aggregating trajectory data")
    overall_tone_trajectory = build_overall_tone_trajectory(overall_tone)
    character_trajectories = build_character_trajectories(character_emotions)

    smoothed_overall_tone_trajectory = overall_tone_trajectory
    smoothed_character_trajectories = character_trajectories
    if args.smooth_window > 1:
        logger.info("Applying smoothing with window=%d", args.smooth_window)
        smoothed_overall_tone_trajectory = smooth_overall_tone_trajectory(
            overall_tone_trajectory,
            args.smooth_window,
        )
        smoothed_character_trajectories = smooth_character_trajectories(
            character_trajectories,
            args.smooth_window,
        )

    analysis_results = {
        "metadata": {
            "input_file": str(Path(args.input).resolve()),
            "output_dir": str(output_dir.resolve()),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "smooth_window": args.smooth_window,
            "tone_method": analyzer.sentiment_source,
            "emotion_method": analyzer.emotion_source,
        },
        "paragraphs": paragraphs,
        "scenes": scenes,
        "major_characters": major_characters,
        "character_frequencies": character_frequencies,
        "scene_characters": scene_characters,
        "overall_tone": overall_tone,
        "character_emotions": character_emotions,
        "overall_tone_trajectory": overall_tone_trajectory,
        "character_trajectories": character_trajectories,
    }

    if args.smooth_window > 1:
        analysis_results["smoothed_overall_tone_trajectory"] = smoothed_overall_tone_trajectory
        analysis_results["smoothed_character_trajectories"] = smoothed_character_trajectories

    logger.info("Step 7: saving JSON results")
    json_output_path = output_dir / "analysis_results.json"
    save_json(analysis_results, json_output_path)

    logger.info("Step 8: generating trajectory charts")
    plot_overall_tone_trajectory(
        smoothed_overall_tone_trajectory,
        output_dir / "overall_tone_trajectory.png",
        use_smoothed_values=args.smooth_window > 1,
    )
    plot_character_emotion_trajectories(
        smoothed_character_trajectories,
        output_dir / "character_emotion_trajectory.png",
        use_smoothed_values=args.smooth_window > 1,
    )

    logger.info("Analysis complete. Results saved to %s", output_dir)
    return analysis_results


def main() -> int:
    args = parse_args()
    try:
        run_pipeline(args)
    except Exception as exc:
        logger = configure_logging(args.log_level)
        logger.exception("Narrative analysis failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
