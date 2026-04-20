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
├── css/style.css
└── assets/
    └── Kris-Fitzwater-CV.pdf   # (drop your CV here — filename must match)
```

## Running locally

Any static file server works. For example:

```
cd portfolio
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Adding your CV

Place your CV as `portfolio/assets/Kris-Fitzwater-CV.pdf`. The "Download CV"
button in the header and the link on the final slide point to that exact
filename.

## Editing content

Each slide is its own standalone HTML file. Copy follows the same pattern on
every page (eyebrow → title → sections → pull quote), so edits stay simple.

## Draft sections to review

The original brief cut off partway through Slide 5. The two-column
"Where I'm Focused" / "Why It Matters" blocks and the closing "Let's Talk"
section on `transformation.html` are draft copy written to complete the
narrative arc — refine or replace before sharing.
