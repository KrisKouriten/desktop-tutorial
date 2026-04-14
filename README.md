# UK Retail Market Financial Newsletter

A monthly financial newsletter providing comprehensive analysis of the UK retail sector.

## Overview

This project produces a monthly newsletter covering:

- **FTSE-listed retailer performance** (earnings, share prices, margins)
- **UK retail sales data** from ONS and BRC-KPMG
- **Consumer confidence and spending** trends (GfK, household data)
- **Macroeconomic indicators** (inflation, interest rates, FX, GDP)
- **E-commerce and digital retail** developments
- **Sector risks and outlook** with analyst consensus

## Project Structure

```
├── newsletters/          # Published monthly newsletter issues
├── templates/            # Reusable newsletter template with placeholders
├── data/
│   ├── tracked-companies.json   # UK retailers tracked each month
│   ├── data-sources.json        # Reference list of data sources
│   └── earnings-calendar.json   # Upcoming earnings dates
├── scripts/
│   └── generate-newsletter.py   # Script to generate a newsletter from template + data
└── README.md
```

## Usage

### Generate a newsletter

Prepare a monthly data JSON file with values for each template placeholder, then run:

```bash
python scripts/generate-newsletter.py --month 2026-04 --data data/april-2026.json
```

The generated newsletter will be saved to `newsletters/2026-04_uk-retail-market-review.md`.

### Edit the template

The reusable template is at `templates/newsletter-template.md`. Placeholders use `{{KEY}}` syntax and are substituted by the generator script.

## Data Sources

| Source | Data Provided |
|--------|--------------|
| ONS | Retail sales, CPI, employment, GDP |
| BRC-KPMG | Retail sales monitor, footfall |
| GfK | Consumer confidence barometer |
| IMRG | Online retail index |
| Bank of England | Base rate, credit statistics |
| LSE / LSEG | Share prices, FTSE indices |

## Tracked Companies

**Grocery & Food:** Tesco, Sainsbury's, Marks & Spencer, Ocado
**Fashion & General:** Next, Primark (ABF), JD Sports, Frasers Group, boohoo
**Home & Specialty:** Kingfisher (B&Q), Dunelm, WHSmith, Pets at Home

## Disclaimer

This newsletter is for informational purposes only and does not constitute financial advice.
