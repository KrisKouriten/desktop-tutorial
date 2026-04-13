# Finance Director Job Monitor

Monitors UK recruitment sites for **Finance Director / CFO** roles in **London
and the South West**, filters by your criteria, and emails you a digest of any
new postings since the last run.

## Coverage

| Source       | Auth           | Coverage                                         |
| ------------ | -------------- | ------------------------------------------------ |
| Reed         | Free API key   | reed.co.uk direct + many recruiter listings     |
| Adzuna       | Free App ID/Key| Aggregates hundreds of UK boards incl. agencies |
| Jooble       | Free API key   | Additional aggregator, fills gaps                |
| CV-Library   | RSS (no auth)  | Direct RSS feed                                  |
| Totaljobs    | RSS (no auth)  | Direct RSS feed                                  |
| SerpApi      | Paid key       | Google Jobs -> LinkedIn + Indeed results         |

LinkedIn and Indeed no longer expose free public APIs and actively block
scraping. The practical way to reach them is via SerpApi (Google Jobs results),
which is why it's an optional paid source. Reed + Adzuna + Jooble already cover
most agency/recruiter postings for the same roles.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in keys you have
```

Get free API keys:

- Reed:   https://www.reed.co.uk/developers
- Adzuna: https://developer.adzuna.com/
- Jooble: https://jooble.org/api/about

For email digests via Gmail, create an
[App Password](https://support.google.com/accounts/answer/185833) and use it as
`SMTP_PASSWORD`.

## Configure

Edit `config.yaml`:

- `keywords.titles_any`  - which titles count as FD-level
- `keywords.titles_exclude` - titles to always drop (FC, Head of Finance, etc.)
- `locations`            - London + the South West hubs (Bristol, Bath, Exeter,
  Plymouth, Bournemouth, Swindon, Cheltenham by default)
- `filters.min_salary_gbp` - minimum salary (default \u00a3120,000)
- `filters.require_hybrid_or_remote` - hard filter or just a flag
- `sources`              - toggle individual sources on/off

No code changes are needed to tweak the search.

## Run

```bash
# Dry run - prints matches to stdout, doesn't email or mark jobs as seen
python -m jobsearch.main --dry-run -v

# Real run - emails new jobs and remembers them in jobs.db
python -m jobsearch.main
```

## Automate (monitor 24/7)

The script only emails jobs it hasn't seen before (tracked in `jobs.db`), so
just run it on a schedule.

**Linux / macOS crontab** (every 15 minutes):

```
*/15 * * * * /path/to/desktop-tutorial/scripts/run.sh >> /tmp/fd-jobs.log 2>&1
```

**GitHub Actions** (free):

```yaml
# .github/workflows/monitor.yml
on:
  schedule: [{ cron: "*/15 * * * *" }]
  workflow_dispatch:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python -m jobsearch.main
        env:
          REED_API_KEY: ${{ secrets.REED_API_KEY }}
          ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
          ADZUNA_APP_KEY: ${{ secrets.ADZUNA_APP_KEY }}
          JOOBLE_API_KEY: ${{ secrets.JOOBLE_API_KEY }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
      # commit the updated jobs.db back so dedup persists between runs
      - run: |
          git config user.email "bot@example.com"
          git config user.name "fd-monitor"
          git add jobs.db || true
          git commit -m "update seen jobs" || true
          git push || true
```

## How it works

```
sources/*.py  --fetch-->  Job dataclass
                              |
                              v
                         filters.apply()  (title / salary / hybrid checks)
                              |
                              v
                         JobStore (SQLite) -- dedup against past runs
                              |
                              v
                         notify.send_email() -- HTML + plaintext digest
```

- Each source is isolated: one crashing does not break the run.
- New jobs are only marked "seen" after a successful notification.
- SQLite (`jobs.db`) is the persistence layer - delete it to re-notify every
  historical job.

## Project layout

```
jobsearch/
  main.py        # CLI entry, run() orchestration
  config.py      # config.yaml + .env loader
  models.py      # Job dataclass
  store.py       # SQLite dedup
  filters.py     # title / salary / hybrid filtering
  notify.py      # SMTP email with HTML digest
  sources/
    reed.py      adzuna.py  jooble.py  serpapi.py  rss.py
scripts/run.sh   # cron wrapper
config.yaml      # your criteria
.env.example     # credential template
```
