from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import requests
from dateutil import parser as dateparser
from openai import OpenAI

from utils import (
    ROOT,
    choose_key,
    is_whitelisted,
    load_disease_config,
    load_journal_whitelist,
    load_json,
    match_disease,
    match_section,
    save_json,
)

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def jst_today() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def build_query(terms: List[str]) -> str:
    or_terms = " OR ".join([f'"{t}"' for t in terms])
    return f"({or_terms}) AND humans[mesh] AND english[lang]"


def fetch_pubmed(terms: List[str]) -> List[dict]:
    params = {
        "db": "pubmed",
        "term": build_query(terms),
        "retmode": "json",
        "retmax": 200,
        "reldate": 1,
        "datetype": "pdat",
    }
    r = requests.get(PUBMED_SEARCH, params=params, timeout=30)
    r.raise_for_status()
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
    }
    f = requests.get(PUBMED_FETCH, params=fetch_params, timeout=30)
    f.raise_for_status()

    import xml.etree.ElementTree as ET

    root = ET.fromstring(f.text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title = article.findtext(".//ArticleTitle") or ""
        abstract = " ".join(
            [t.text or "" for t in article.findall(".//Abstract/AbstractText")]
        ).strip()
        journal = article.findtext(".//Journal/Title") or ""
        doi = None
        for idnode in article.findall(".//ArticleId"):
            if idnode.get("IdType") == "doi":
                doi = idnode.text
        pub_year = article.findtext(".//PubDate/Year") or ""
        pub_month = article.findtext(".//PubDate/Month") or ""
        pub_day = article.findtext(".//PubDate/Day") or ""
        published = "-".join([p for p in [pub_year, pub_month, pub_day] if p])
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        articles.append(
            {
                "source": "pubmed",
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": pub_year,
                "published": published or pub_year,
                "url": url,
            }
        )
    return articles


def fetch_epmc(terms: List[str], from_date: str, to_date: str) -> List[dict]:
    query_terms = " OR ".join([f'"{t}"' for t in terms])
    query = (
        f"({query_terms}) AND (HAS_ABSTRACT:Y) AND (LANG:eng) "
        f"AND (PUB_TYPE:\"journal article\") AND FIRST_PDATE:[{from_date} TO {to_date}]"
    )
    params = {
        "query": query,
        "format": "json",
        "pageSize": 100,
        "resultType": "core",
    }
    r = requests.get(EPMC_SEARCH, params=params, timeout=30)
    r.raise_for_status()
    results = r.json().get("resultList", {}).get("result", [])

    articles = []
    for item in results:
        pmid = item.get("pmid")
        doi = item.get("doi")
        title = item.get("title", "")
        abstract = item.get("abstractText", "")
        journal = item.get("journalTitle", "")
        year = item.get("pubYear", "")
        published = item.get("firstPublicationDate") or item.get("firstPublicationDate") or year
        url = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
        url = url[0].get("url") if url else ""
        articles.append(
            {
                "source": "epmc",
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": year,
                "published": published,
                "url": url,
            }
        )
    return articles


def summarize(client: OpenAI, title: str, abstract: str) -> str:
    if os.environ.get("SKIP_SUMMARY") == "1":
        return ""
    if not abstract:
        return ""
    prompt = (
        "以下の英語の論文情報を、日本語で約300字に要約してください。\n"
        "構成は『背景/方法/結果/結論』の順にし、冗長な前置きは不要です。\n\n"
        f"Title: {title}\n"
        f"Abstract: {abstract}"
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.2,
    )
    return resp.output_text.strip()


def summarize_short(client: OpenAI, title: str, abstract: str) -> str:
    if os.environ.get("SKIP_SUMMARY") == "1":
        return ""
    if not abstract:
        return ""
    prompt = (
        "以下の英語の論文情報を、日本語で約150字の完結した要約にしてください。"
        "冗長な前置きは不要です。\\n\\n"
        f"Title: {title}\\n"
        f"Abstract: {abstract}"
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.2,
    )
    return resp.output_text.strip()


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")
    diseases_cfg = load_disease_config()
    diseases = diseases_cfg["diseases"]
    sections = diseases_cfg["sections"]
    whitelist = load_journal_whitelist()

    terms = sorted({t for d in diseases for t in d.get("terms", [])})

    today = jst_today()
    from_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    items = []
    items.extend(fetch_pubmed(terms))
    items.extend(fetch_epmc(terms, from_date, to_date))

    merged = {}
    for it in items:
        key = choose_key(it.get("doi"), it.get("pmid"), it.get("title", ""))
        if key in merged:
            continue
        if not is_whitelisted(it.get("journal", ""), whitelist):
            continue
        merged[key] = it

    def sort_key(it: dict) -> datetime:
        raw = it.get("published") or it.get("year") or ""
        try:
            return dateparser.parse(str(raw)) or datetime(1900, 1, 1)
        except Exception:
            return datetime(1900, 1, 1)

    max_items = int(os.environ.get("MAX_ITEMS_PER_DAY", "10"))
    merged_items = sorted(merged.values(), key=sort_key, reverse=True)[:max_items]

    client = OpenAI()
    cache_path = ROOT / "data" / "cache" / "summaries.json"
    cache = load_json(cache_path, {})

    daily = []
    for it in merged_items:
        cache_key = it.get("doi") or it.get("pmid") or it.get("title")
        cached = cache.get(cache_key) or {}
        if isinstance(cached, str):
            cached = {"summary_ja": cached, "summary_short_ja": ""}

        summary = cached.get("summary_ja", "")
        summary_short = cached.get("summary_short_ja", "")

        if not summary:
            summary = summarize(client, it.get("title", ""), it.get("abstract", ""))
        if not summary_short:
            summary_short = summarize_short(
                client, it.get("title", ""), it.get("abstract", "")
            )

        if summary or summary_short:
            cache[cache_key] = {
                "summary_ja": summary,
                "summary_short_ja": summary_short,
            }
        disease_id = match_disease(it.get("title", ""), it.get("abstract", ""), diseases)
        section_id = match_section(it.get("title", ""), it.get("abstract", ""), sections)
        daily.append(
            {
                **it,
                "summary_ja": summary,
                "summary_short_ja": summary_short,
                "disease": disease_id or "other",
                "section": section_id,
            }
        )

    save_json(cache_path, cache)

    date_str = today.strftime("%Y-%m-%d")
    daily_path = ROOT / "data" / "daily" / f"{date_str}.json"
    save_json(daily_path, {"date": date_str, "items": daily})

    for d in diseases:
        did = d["id"]
        disease_path = ROOT / "data" / "disease" / f"{did}.json"
        existing = load_json(disease_path, {"disease": did, "items": []})
        existing_items = existing.get("items", [])
        new_items = [it for it in daily if it.get("disease") == did]
        existing["items"] = new_items + existing_items
        save_json(disease_path, existing)

    # Update disease wiki text (per section) with minimal changes
    text_dir = ROOT / "data" / "disease_text"
    text_dir.mkdir(parents=True, exist_ok=True)
    for d in diseases:
        did = d["id"]
        disease_text_path = text_dir / f"{did}.json"
        existing_text = load_json(disease_text_path, {"disease": did, "sections": {}})
        sections_text = existing_text.get("sections", {})

        for s in sections:
            sid = s["id"]
            new_items = [it for it in daily if it.get("disease") == did and it.get("section") == sid]
            if not new_items:
                continue
            new_summaries = "\n".join(
                [f"- {it.get('summary_short_ja') or it.get('summary_ja','')}" for it in new_items if it.get("summary_short_ja") or it.get("summary_ja")]
            ).strip()
            if not new_summaries:
                continue

            current = sections_text.get(sid, "")
            prompt = (
                "以下は疾患レビューの本文です。新しい研究要約を反映して、"
                "本文を最小限だけ更新してください。更新は最大2文まで。"
                "既存の内容を大きく書き換えないでください。\\n\\n"
                f"現在の本文:\\n{current}\\n\\n"
                f"新しい要約:\\n{new_summaries}\\n\\n"
                "更新後の本文:"
            )
            model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
            resp = client.responses.create(
                model=model,
                input=prompt,
                temperature=0.2,
            )
            updated = resp.output_text.strip()
            if updated:
                sections_text[sid] = updated

        existing_text["sections"] = sections_text
        save_json(disease_text_path, existing_text)

    from build_site import build_site

    build_site(date_str)


if __name__ == "__main__":
    main()
