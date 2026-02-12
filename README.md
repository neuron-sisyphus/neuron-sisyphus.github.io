# Neuro Daily Review

Daily, disease-focused summaries of clinical neurology papers. Built for GitHub Pages.

## What this does
- Fetches new papers daily from PubMed and Europe PMC
- Filters to English + human + clinical
- Dedupe by DOI/PMID/title
- Summarizes each paper (~300 Japanese characters)
- Organizes by disease and updates a wiki-style page

## Repo layout
- `scripts/` pipeline scripts
- `config/` sources, journals, disease terms
- `daily/` generated daily pages
- `diseases/` generated disease pages
- `assets/` site styles

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...  # required
python scripts/run_daily.py
```

## GitHub Actions
Configured to run daily at 09:00 JST (00:00 UTC).

## Notes
- Impact factor is kept as reference only (whitelist of journals).
- Wikipedia-style sections are: Epidemiology, Diagnosis, Imaging, Treatment, Prognosis.
