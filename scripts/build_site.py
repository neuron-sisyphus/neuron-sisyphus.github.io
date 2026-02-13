from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import ROOT, load_disease_config, load_json


def layout(title: str, body: str) -> str:
    jst = datetime.now(timezone(timedelta(hours=9)))
    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <link rel=\"stylesheet\" href=\"/assets/style.css\" />
</head>
<body>
<header>
  <div class=\"container\">
    <h1>Neuro Daily Review</h1>
    <p>臨床神経学の最新論文を毎日更新</p>
  </div>
</header>
<div class=\"container\">
{body}
</div>
<footer>
  <div class=\"container\">
    <small>Generated {jst.strftime('%Y-%m-%d %H:%M')} JST</small>
  </div>
</footer>
</body>
</html>"""


def build_index(latest_date: str, diseases: list) -> str:
    cards = "".join(
        [
            f"<div class='card'><h3><a href='/diseases/{d['id']}.html'>{d['name_ja']}</a></h3><small>{d['name_en']}</small></div>"
            for d in diseases
        ]
    )
    body = f"""
<section>
  <h2>最新の日次レビュー</h2>
  <p><a href='/daily/{latest_date}.html'>{latest_date}</a></p>
</section>
<section>
  <h2>疾患別レビュー</h2>
  <div class='grid'>{cards}</div>
</section>
"""
    return layout("Neuro Daily Review", body)


def build_daily_page(date_str: str, items: list, diseases: dict, sections: dict) -> str:
    groups = {}
    for it in items:
        did = it.get("disease") or "other"
        groups.setdefault(did, []).append(it)

    blocks = []
    for did, lst in groups.items():
        dname = diseases.get(did, did)
        bullets = []
        for it in lst:
            sec = sections.get(it.get("section"), "")
            journal = it.get("journal", "")
            summary = it.get("summary_ja", "")
            ref = it.get("doi") or it.get("pmid") or ""
            url = it.get("url") or ""
            title = it.get("title", "")
            link = f"<a href='{url}'>{title}</a>" if url else title
            bullets.append(
                f"<li><span class='badge'>{sec}</span> {link}<br /><small>{journal} / {ref}</small><p>{summary}</p></li>"
            )
        blocks.append(f"<h2>{dname}</h2><ul>{''.join(bullets)}</ul>")

    body = f"<section><h2>日次レビュー {date_str}</h2>{''.join(blocks)}</section>"
    return layout(f"Daily {date_str}", body)


def build_disease_page(disease: dict, items: list, sections: dict) -> str:
    section_blocks = {}
    for it in items:
        sid = it.get("section") or "treatment"
        section_blocks.setdefault(sid, []).append(it)

    def shorten(text: str, limit: int = 150) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    references = []
    ref_index = {}
    def ref_id(it: dict) -> int:
        key = it.get("doi") or it.get("pmid") or it.get("title") or ""
        if key not in ref_index:
            ref_index[key] = len(references) + 1
            references.append(it)
        return ref_index[key]

    blocks = []
    for sid, lst in section_blocks.items():
        sname = sections.get(sid, sid)
        bullets = []
        for it in lst:
            summary = shorten(it.get("summary_ja", ""))
            if not summary:
                continue
            rid = ref_id(it)
            bullets.append(f"<li>{summary} <small>[{rid}]</small></li>")
        blocks.append(f"<h2>{sname}</h2><ul>{''.join(bullets)}</ul>")

    refs_html = []
    for it in references:
        journal = it.get("journal", "")
        ref = it.get("doi") or it.get("pmid") or ""
        url = it.get("url") or ""
        title = it.get("title", "")
        link = f"<a href='{url}'>{title}</a>" if url else title
        refs_html.append(f"<li>{link}<br /><small>{journal} / {ref}</small></li>")
    refs_block = ""
    if refs_html:
        refs_block = f"<h2>参考文献</h2><ol>{''.join(refs_html)}</ol>"

    body = f"<section><h2>{disease['name_ja']}</h2><p>{disease['name_en']}</p>{''.join(blocks)}{refs_block}</section>"
    return layout(disease["name_ja"], body)


def build_site(latest_date: str) -> None:
    cfg = load_disease_config()
    diseases = cfg["diseases"]
    sections_cfg = {s["id"]: s["name_ja"] for s in cfg["sections"]}
    disease_names = {d["id"]: d["name_ja"] for d in diseases}

    daily_data = load_json(ROOT / "data" / "daily" / f"{latest_date}.json", {})
    daily_items = daily_data.get("items", [])

    index_html = build_index(latest_date, diseases)
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")

    daily_html = build_daily_page(latest_date, daily_items, disease_names, sections_cfg)
    daily_path = ROOT / "daily" / f"{latest_date}.html"
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(daily_html, encoding="utf-8")

    for d in diseases:
        did = d["id"]
        disease_data = load_json(ROOT / "data" / "disease" / f"{did}.json", {})
        items = disease_data.get("items", [])
        page_html = build_disease_page(d, items, sections_cfg)
        path = ROOT / "diseases" / f"{did}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page_html, encoding="utf-8")
