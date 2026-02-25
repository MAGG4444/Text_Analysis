# Text Analysis Web App

This app implements a text analysis workbench focused on article theme + people sentiment:

- Central upload/input section for article text files (`.txt`, `.docx`, `.doc`, `.rtf`, `.md`) or pasted text
- Web-link mode to discover supported files from a page and analyze selected links
- Direct webpage analysis mode to extract visible text from a URL and analyze it
- Centered analysis results with graphs:
  - Theme detection shown first
  - People-only sentiment trajectories (separated per person)
  - One-sentence summary for quick readout
- Optional GenAI-assisted theme/person extraction (`OPENAI_API_KEY`) with automatic local fallback
- Compact submission history panel in the top-left for editing and resubmission

## Run

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python app.py
```

4. Open `http://127.0.0.1:5000`.

## Notes

- `.docx` extraction is reliable.
- Legacy `.doc` extraction is best-effort without external converters. For best results, convert `.doc` to `.docx`.
- Web-link discovery supports links to `.txt`, `.md`, `.rtf`, `.doc`, and `.docx` files.
- People-name extraction excludes repetitive non-person terms and merges name variations (for cleaner person sentiment).
- If GenAI is enabled in UI but no API key is configured, the app safely falls back to local analysis.

## Local Training Pipeline

If you want fully local model training from your own `.txt` story corpus, use:

- [training/README.md](training/README.md)

Quick start:

```bash
python training/scripts/train_models.py
python training/scripts/analyze_story.py --input "path/to/story.txt"
```
