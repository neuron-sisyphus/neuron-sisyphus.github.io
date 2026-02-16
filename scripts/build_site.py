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
    <div class=\"topbar\">
      <div class=\"brand\">
        <h1>Neuro Daily Review</h1>
        <p>臨床神経学の最新論文をやさしく整理</p>
      </div>
      <nav class=\"nav\">
        <a href=\"/\">ホーム</a>
        <a href=\"/daily/\">日次レビュー</a>
        <a href=\"/diseases/\">疾患別</a>
      </nav>
    </div>
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


def build_index(latest_date: str, diseases: list, recent_dates: list) -> str:
    cards = "".join(
        [
            f"<div class='card'><h3><a href='/diseases/{d['id']}.html'>{d['name_ja']}</a></h3><small>{d['name_en']}</small></div>"
            for d in diseases
        ]
    )
    recent_links = "".join(
        [f"<li><a href='/daily/{d}.html'>{d}</a></li>" for d in recent_dates]
    )
    body = f"""
<section class="hero">
  <h2>今日のアップデート</h2>
  <p>最新の臨床論文を疾患ごとに整理し、簡潔にレビューします。</p>
</section>
<section>
  <h2>直近1週間の日次レビュー</h2>
  <ul>{recent_links}</ul>
</section>
<section>
  <h2>疾患別レビュー</h2>
  <div class='grid'>{cards}</div>
</section>
"""
    return layout("Neuro Daily Review", body)


def build_daily_index(dates: list) -> str:
    items = "".join([f"<li><a href='/daily/{d}.html'>{d}</a></li>" for d in dates])
    body = f"""
<section class="hero">
  <h2>日次レビュー一覧</h2>
  <p>日付ごとのまとめです。</p>
</section>
<section>
  <h2>更新日</h2>
  <ul>{items}</ul>
</section>
"""
    return layout("Daily Reviews", body)


def build_diseases_index(diseases: list) -> str:
    cards = "".join(
        [
            f"<div class='card'><h3><a href='/diseases/{d['id']}.html'>{d['name_ja']}</a></h3><small>{d['name_en']}</small></div>"
            for d in diseases
        ]
    )
    body = f"""
<section class="hero">
  <h2>疾患別レビュー一覧</h2>
  <p>疾患ごとのレビューをまとめています。</p>
</section>
<section>
  <h2>疾患</h2>
  <div class='grid'>{cards}</div>
</section>
"""
    return layout("Disease Reviews", body)


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
        section_text = disease.get("sections_text", {}).get(sid, "")
        section_intro = f"<p>{section_text}</p>" if section_text else ""
        seen_keys = set()
        for it in lst:
            summary = it.get("summary_short_ja", "")
            if not summary:
                continue
            key = (it.get("doi") or it.get("pmid") or it.get("title") or "").strip().lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            rid = ref_id(it)
            bullets.append(f"<li>{summary} <small>[{rid}]</small></li>")
        blocks.append(f"<h2>{sname}</h2>{section_intro}<ul>{''.join(bullets)}</ul>")

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
        refs_block = f"<section class='refs'><h2>参考文献</h2><ol>{''.join(refs_html)}</ol></section>"

    body = f"<section><h2>{disease['name_ja']}</h2><p>{disease['name_en']}</p>{''.join(blocks)}{refs_block}</section>"
    return layout(disease["name_ja"], body)


def build_site(latest_date: str) -> None:
    cfg = load_disease_config()
    diseases = cfg["diseases"]
    sections_cfg = {s["id"]: s["name_ja"] for s in cfg["sections"]}
    disease_names = {d["id"]: d["name_ja"] for d in diseases}

    daily_dir = ROOT / "data" / "daily"
    dates = []
    if daily_dir.exists():
        for p in daily_dir.glob("*.json"):
            dates.append(p.stem)
    dates = sorted(dates, reverse=True)

    daily_data = load_json(ROOT / "data" / "daily" / f"{latest_date}.json", {})
    daily_items = daily_data.get("items", [])

    index_html = build_index(latest_date, diseases, dates[:7])
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")

    # Daily index
    daily_index = build_daily_index(dates)
    (ROOT / "daily").mkdir(parents=True, exist_ok=True)
    (ROOT / "daily" / "index.html").write_text(daily_index, encoding="utf-8")

    diseases_index = build_diseases_index(diseases)
    (ROOT / "diseases").mkdir(parents=True, exist_ok=True)
    (ROOT / "diseases" / "index.html").write_text(diseases_index, encoding="utf-8")

    daily_html = build_daily_page(latest_date, daily_items, disease_names, sections_cfg)
    daily_path = ROOT / "daily" / f"{latest_date}.html"
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(daily_html, encoding="utf-8")

    for d in diseases:
        did = d["id"]
        disease_text = load_json(ROOT / "data" / "disease_text" / f"{did}.json", {})
        d["sections_text"] = disease_text.get("sections", {})
        disease_data = load_json(ROOT / "data" / "disease" / f"{did}.json", {})
        items = disease_data.get("items", [])
        page_html = build_disease_page(d, items, sections_cfg)
        path = ROOT / "diseases" / f"{did}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page_html, encoding="utf-8")
