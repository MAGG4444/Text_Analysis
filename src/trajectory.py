from collections import defaultdict
from typing import Dict, List


def build_overall_tone_trajectory(
    overall_tone_results: List[Dict[str, str | float | int]],
) -> List[Dict[str, float | int]]:
    """Create an ordered scene-level tone trajectory."""
    return [
        {"scene_id": int(item["scene_id"]), "tone_score": float(item["tone_score"])}
        for item in sorted(overall_tone_results, key=lambda item: int(item["scene_id"]))
    ]


def build_character_trajectories(
    character_emotion_results: List[Dict[str, str | float | int]],
) -> Dict[str, List[Dict[str, str | float | int]]]:
    """Aggregate emotion scores into per-character trajectories."""
    trajectories: Dict[str, List[Dict[str, str | float | int]]] = defaultdict(list)

    for item in sorted(
        character_emotion_results,
        key=lambda record: (str(record["character"]), int(record["scene_id"])),
    ):
        trajectories[str(item["character"])].append(
            {
                "scene_id": int(item["scene_id"]),
                "emotion_score": float(item["emotion_score"]),
                "emotion_label": str(item["emotion_label"]),
            }
        )

    return dict(trajectories)


def moving_average(values: List[float], window: int) -> List[float]:
    """Smooth a numeric series with a trailing moving average."""
    if window <= 1 or not values:
        return values[:]

    smoothed: List[float] = []
    for index in range(len(values)):
        start_index = max(0, index - window + 1)
        window_values = values[start_index : index + 1]
        smoothed.append(sum(window_values) / len(window_values))
    return smoothed


def smooth_overall_tone_trajectory(
    trajectory: List[Dict[str, float | int]],
    window: int,
) -> List[Dict[str, float | int]]:
    """Apply moving-average smoothing to the overall tone trajectory."""
    scores = [float(item["tone_score"]) for item in trajectory]
    smoothed_scores = moving_average(scores, window)

    return [
        {"scene_id": int(item["scene_id"]), "tone_score": round(smoothed_scores[index], 4)}
        for index, item in enumerate(trajectory)
    ]


def smooth_character_trajectories(
    trajectories: Dict[str, List[Dict[str, str | float | int]]],
    window: int,
) -> Dict[str, List[Dict[str, str | float | int]]]:
    """Apply moving-average smoothing to each character trajectory."""
    smoothed_trajectories: Dict[str, List[Dict[str, str | float | int]]] = {}

    for character, points in trajectories.items():
        scores = [float(point["emotion_score"]) for point in points]
        smoothed_scores = moving_average(scores, window)
        smoothed_trajectories[character] = [
            {
                "scene_id": int(point["scene_id"]),
                "emotion_score": round(smoothed_scores[index], 4),
                "emotion_label": str(point["emotion_label"]),
            }
            for index, point in enumerate(points)
        ]

    return smoothed_trajectories
