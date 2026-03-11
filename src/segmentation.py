from typing import Dict, List


def build_scenes(
    paragraphs: List[Dict[str, str | int]],
    merge_strategy: str | None = None,
) -> List[Dict[str, str | int | list[int]]]:
    """Create baseline scenes from paragraphs.

    The current baseline keeps one paragraph per scene. The optional
    merge_strategy parameter is reserved for future multi-paragraph merging.
    """
    _ = merge_strategy
    scenes: List[Dict[str, str | int | list[int]]] = []

    for paragraph in paragraphs:
        scenes.append(
            {
                "scene_id": len(scenes),
                "paragraph_ids": [int(paragraph["paragraph_id"])],
                "text": str(paragraph["text"]),
            }
        )

    return scenes
