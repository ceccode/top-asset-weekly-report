# Top Assets Weekly Report

A CLI tool that generates weekly market reports in Markdown for:

1. **Global Assets** - Major equities, ETFs, and cryptocurrencies
2. **Software Companies** - Curated list of software/SaaS companies

## Features

- Fetches live market data from Yahoo Finance
- Ranks assets by market capitalization
- Calculates concentration metrics (Top 5, Top 10)
- Tracks week-over-week changes (entries, exits, movers)
- Generates clean Markdown reports in English with YAML frontmatter
- Optional LLM integration for editorial sections
- File-based RAG for historical context
- Telegram-friendly TXT summaries
- Static site publishing for GitHub Pages

## Requirements

- Python 3.11+
- macOS/Linux

## Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/top-asset-weekly-report.git
cd top-asset-weekly-report

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (optional, for LLM integration)
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Usage

### Basic Usage

```bash
# Generate both reports for today
python main.py

# Generate only global report
python main.py --only global

# Generate only software report
python main.py --only software
```

### Options

```bash
python main.py --help

Options:
  --date YYYY-MM-DD    Report date (default: today UTC)
  --top-n N            Number of top assets (default: 50)
  --rag-k K            Previous reports for RAG context (default: 4)
  --no-llm             Disable LLM, use placeholder sections
  --only TYPE          Generate only: global, software, or all
  --no-telegram        Disable Telegram TXT generation
  --no-rag-check       Disable RAG freshness check
```

### Examples

```bash
# Generate report for a specific date
python main.py --date 2024-12-30

# Generate top 25 assets only
python main.py --top-n 25

# Force placeholder sections (no LLM)
python main.py --no-llm

# Generate and publish to public/ folder
python main.py --publish
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The suite runs offline: Yahoo Finance and OpenAI are never called.

## Exit Code

`main.py` exits with `0` only when every requested report was generated (and,
with `--publish`, the public folder was built). A partial run exits with `1`.

## LLM Integration (Optional)

To enable AI-generated editorial sections:

```bash
export OPENAI_API_KEY="your-api-key"
python main.py
```

Without an API key, the tool generates deterministic placeholder sections.

The commentary is written by `gpt-6.1-terra`. Set `OPENAI_MODEL` to use another model.

## Regenerating Past Reports

`regenerate.py` renders the reports in `data/reports/` again from their snapshots,
so a template or format fix reaches the whole archive:

```bash
python regenerate.py                  # every report
python regenerate.py --from 2026-06-01 --only global
python regenerate.py --no-llm         # never call the LLM
```

Commentary already written by the LLM is kept. A report that only has placeholders
gets its commentary written now, from that week's data, and states the day in its
frontmatter (`commentary_date`). Running the script again does not call the LLM
for reports that already have commentary.

## Output Structure

```text
top-asset-weekly-report/
├── main.py              # CLI entrypoint
├── regenerate.py        # Regenerate past reports from snapshots
├── config.py            # Configuration
├── yahoo.py             # Data fetching
├── asset.py             # The ranked asset
├── metrics.py           # Calculations
├── snapshot.py          # CSV/JSON snapshots
├── render.py            # Markdown generation
├── llm.py               # LLM integration
├── rag.py               # RAG context
├── telegram.py          # Telegram summaries
├── publisher.py         # GitHub Pages publishing
├── report_id.py         # Report date/scope, file names and labels
├── mdtext.py            # Markdown text helpers
├── tests/               # pytest suite
├── data/
│   ├── config/          # Ticker whitelists
│   │   ├── global_tickers.txt
│   │   └── software_tickers.txt
│   ├── reports/         # Generated Markdown reports
│   │   └── YYYY-MM-DD.{scope}.md
│   ├── snapshots/       # CSV/JSON snapshots
│   │   ├── YYYY-MM-DD.{scope}.csv
│   │   ├── YYYY-MM-DD.{scope}.json
│   │   └── YYYY-MM-DD.telegram.{scope}.txt
│   └── rag/             # RAG context files
│       └── rag_context_{scope}.txt
├── public/              # GitHub Pages output (generated)
├── .github/
│   └── workflows/
│       └── publish.yml  # Automated publishing
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Configuration

### Ticker Lists

Edit files in `data/config/`:

- `global_tickers.txt` - Global assets to track
- `software_tickers.txt` - Software companies whitelist

Format: One ticker per line, comments start with `#`

```text
AAPL     # Apple
MSFT     # Microsoft
```

## Report Format

Each Markdown report includes:

1. **YAML Frontmatter** - Metadata and disclaimer
2. **Executive Summary** - Overview (LLM or placeholder)
3. **Ranking** - Ranking table
4. **Key Metrics** - Totals and concentration
5. **Weekly Changes** - Week-over-week changes
6. **Quantitative Observations** - Data observations
7. **Methodology and Limitations** - Standard methodology section
8. **Strategic Reflection** - Strategic analysis (LLM or placeholder)
9. **Implications** - Implications (LLM or placeholder)

Reports are written in **English**.

## GitHub Pages Publishing

The project includes automated publishing to GitHub Pages.

### Local Preview

```bash
# Generate reports and build public/ folder
python main.py --no-llm --publish

# Preview locally
open public/index.html
```

### GitHub Actions Setup

1. Push the repository to GitHub
2. Go to Settings → Pages
3. Set Source to "GitHub Actions"
4. The workflow runs automatically every Monday at 07:00 UTC
5. You can also trigger it manually from Actions tab

The workflow file is at `.github/workflows/publish.yml`.

### Public Folder Structure

```text
public/
├── index.html              # Landing page
├── manifest.json           # Report index with metadata
├── reports/
│   └── YYYY-MM-DD.*.md     # Markdown reports
├── data/
│   └── YYYY-MM-DD.*.json   # Structured JSON data
└── telegram/
    └── YYYY-MM-DD.*.txt    # Telegram summaries
```

## Disclaimer

This tool is for informational purposes only and does not constitute financial advice. Always conduct your own research before making investment decisions.

## License

MIT
