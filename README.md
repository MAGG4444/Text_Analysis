# Narrative Trajectory Baseline

This project is a runnable Python baseline for analyzing a narrative article or story from a single `.txt` file. It segments the text into paragraph-level scenes, extracts major characters, estimates scene-level overall tone, estimates per-character emotions inside scenes where they appear, builds trajectory data, and saves both JSON and PNG outputs.

## Project Structure

```text
data/
models/
outputs/
src/
README.md
requirements.txt
```

Key source files:

- `src/main.py`: command-line entry point
- `src/preprocess.py`: text loading, cleaning, paragraph splitting
- `src/segmentation.py`: baseline paragraph-to-scene conversion
- `src/character_extraction.py`: character extraction and scene association
- `src/sentiment_model.py`: scene tone and character emotion analysis
- `src/trajectory.py`: trajectory aggregation and smoothing
- `src/visualization.py`: PNG chart generation
- `src/utils.py`: logging and file helpers

## Goal

Given a text file containing the full story or article, the pipeline produces:

- Paragraph segmentation results
- Scene segmentation results
- Scene-level overall tone labels and scores
- Scene-character emotion labels and scores for major characters
- Overall tone trajectory data
- Character emotion trajectory data
- `outputs/analysis_results.json`
- `outputs/overall_tone_trajectory.png`
- `outputs/character_emotion_trajectory.png`

## Installation

1. Create and activate a virtual environment if you want isolation.
2. Install the baseline dependencies:

```bash
pip install -r requirements.txt
```

Optional improvements:

- If you already have `transformers` and a compatible local sentiment or emotion model cached or stored under `models/`, the program will try to use them.
- If `spacy` and `en_core_web_sm` are installed, character extraction can use them automatically.

The pipeline does not require those optional packages to run. If they are unavailable, it falls back to rule-based methods.

## Usage

Basic run:

```bash
python src/main.py --input data/story.txt --output outputs/
```

Useful optional flags:

```bash
python src/main.py \
  --input data/story.txt \
  --output outputs/ \
  --models-dir models/ \
  --max-characters 5 \
  --min-character-frequency 2 \
  --smooth-window 3 \
  --log-level INFO
```

## Input Format

Input is a single `.txt` file containing the full narrative text. Paragraphs should be separated by one or more blank lines.

Preprocessing output format:

```json
[
  {"paragraph_id": 0, "text": "..."},
  {"paragraph_id": 1, "text": "..."}
]
```

Scene output format:

```json
[
  {"scene_id": 0, "paragraph_ids": [0], "text": "..."}
]
```

## Output Files

The pipeline writes:

- `outputs/analysis_results.json`
- `outputs/overall_tone_trajectory.png`
- `outputs/character_emotion_trajectory.png`

The JSON contains at least:

- `paragraphs`
- `scenes`
- `scene_characters`
- `overall_tone`
- `character_emotions`
- `overall_tone_trajectory`
- `character_trajectories`

Example scene tone record:

```json
{"scene_id": 0, "tone_label": "negative", "tone_score": -0.62}
```

Example character emotion record:

```json
{"scene_id": 0, "character": "Alice", "emotion_label": "sadness", "emotion_score": 0.78}
```

## Baseline Method Summary

1. Text loading and paragraph splitting
2. Scene generation with one paragraph per scene
3. Character extraction using optional spaCy NER, with rule-based fallback from proper nouns and dialogue clues
4. Scene-level tone scoring using an optional local transformer model, with VADER or handcrafted lexicon fallback
5. Character emotion scoring using optional local transformer emotion classification, with context-window lexicon fallback
6. Trajectory aggregation and optional moving-average smoothing
7. JSON and PNG export

## Limitations

- Scene segmentation is intentionally simple: one paragraph equals one scene.
- Rule-based character extraction can still pick up some false positives or miss pronoun-only references.
- Emotion inference is approximate and driven by local lexical cues when no model is available.
- Tone and emotion scores are useful as baseline signals, not as gold-standard narrative understanding.
- The plotting step uses only the dominant emotion score per scene-character pair.

## Future Improvements

- Merge adjacent paragraphs into larger scenes using semantic similarity or topic shift detection
- Add coreference resolution so pronouns can be linked back to characters
- Improve name normalization for titles, surnames, and aliases
- Add stronger local models for sentiment and emotion classification
- Add richer outputs such as per-emotion trajectories, confidence calibration, and CSV exports
