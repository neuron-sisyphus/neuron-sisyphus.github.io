from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return re.sub(r"\s+", " ", t).strip()


def choose_key(doi: Optional[str], pmid: Optional[str], title: str) -> str:
    if doi:
        return f"doi:{doi.lower().strip()}"
    if pmid:
        return f"pmid:{pmid.strip()}"
    return f"title:{normalize_title(title)}"


def load_journal_whitelist() -> List[dict]:
    data = load_yaml(ROOT / "config" / "journals.yaml")
    return data.get("journals", [])


def is_whitelisted(journal: str, whitelist: List[dict]) -> bool:
    if not journal:
        return False
    j = journal.lower().strip()
    for item in whitelist:
        names = [item.get("name", "")] + item.get("aliases", [])
        for n in names:
            if j == str(n).lower().strip():
                return True
    return False


def load_disease_config() -> dict:
    return load_yaml(ROOT / "config" / "diseases.yaml")


def match_disease(title: str, abstract: str, diseases: List[dict]) -> Optional[str]:
    text = f"{title} {abstract}".lower()
    for d in diseases:
        for term in d.get("terms", []):
            if term.lower() in text:
                return d["id"]
    return None


def match_section(title: str, abstract: str, sections: List[dict]) -> str:
    text = f"{title} {abstract}".lower()
    for s in sections:
        for kw in s.get("keywords", []):
            if kw.lower() in text:
                return s["id"]
    return "treatment"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
