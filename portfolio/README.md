# Kris Fitzwater — Finance Portfolio

Static, multi-page portfolio site designed to be shared alongside a CV.

## Structure

```
portfolio/
├── index.html           # 01 Profile / Positioning
├── case-study.html      # 02 Miniso UK scaling case study
├── commercial.html      # 03 Commercial decision-making
├── funding.html         # 04 Funding & cash strategy
├── transformation.html  # 05 AI & finance transformation
├── playbook.html        # 06 Transformation playbook
├── next-role.html       # 07 Next role / call to action
├── css/style.css
└── assets/
    └── Kris-Fitzwater-CV.pdf   # (replace with your own PDF anytime)
```

`cv-source.html` lives at the repo root (not inside `portfolio/`, so it
isn't served by the site) and is the HTML used to render the PDF.

## Running locally

Any static file server works. For example:

```
cd portfolio
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Adding or updating the CV

The repo ships with a generated PDF at `portfolio/assets/Kris-Fitzwater-CV.pdf`
rendered from the source at `../cv-source.html` (repo root, outside the
served site).

- **Replace with your own PDF:** drop any PDF at the same path and filename
  (`portfolio/assets/Kris-Fitzwater-CV.pdf`) — that's all.
- **Edit the existing CV and regenerate:** edit `cv-source.html`, then:

  ```
  pip install weasyprint
  python3 -c "from weasyprint import HTML; HTML('cv-source.html').write_pdf('portfolio/assets/Kris-Fitzwater-CV.pdf')"
  ```

The "Download CV" button in the header (on every slide) points to that
filename.

## Editing content

Each slide is its own standalone HTML file. Copy follows the same pattern on
every page (eyebrow → title → sections → pull quote), so edits stay simple.
