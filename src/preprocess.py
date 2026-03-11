import re
from pathlib import Path
from typing import Dict, List


def read_text_file(file_path: str | Path) -> str:
    """Read a text file with a small set of fallback encodings."""
    path = Path(file_path)
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode text file: {path}")


def clean_text(raw_text: str) -> str:
    """Normalize whitespace while preserving paragraph boundaries."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_paragraphs(cleaned_text: str) -> List[Dict[str, str | int]]:
    """Split cleaned text into ordered paragraph records."""
    paragraph_texts = [chunk.strip() for chunk in re.split(r"\n\s*\n", cleaned_text) if chunk.strip()]
    return [
        {"paragraph_id": paragraph_id, "text": paragraph_text}
        for paragraph_id, paragraph_text in enumerate(paragraph_texts)
    ]


def preprocess_text_file(file_path: str | Path) -> List[Dict[str, str | int]]:
    """Read, clean, and split a story file into paragraph records."""
    raw_text = read_text_file(file_path)
    cleaned_text = clean_text(raw_text)
    return split_into_paragraphs(cleaned_text)
