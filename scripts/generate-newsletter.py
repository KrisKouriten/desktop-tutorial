#!/usr/bin/env python3
"""
UK Retail Market Financial Newsletter Generator

Reads the newsletter template and a data file, then produces
a populated newsletter for the given month.

Usage:
    python generate-newsletter.py --month 2026-04 --data data/april-2026.json
"""

import argparse
import json
import os
import re
from datetime import datetime


def load_template(template_path: str) -> str:
    """Load the newsletter Markdown template."""
    with open(template_path, "r") as f:
        return f.read()


def load_data(data_path: str) -> dict:
    """Load the monthly data JSON file."""
    with open(data_path, "r") as f:
        return json.load(f)


def substitute_placeholders(template: str, data: dict) -> str:
    """Replace {{PLACEHOLDER}} tokens with values from the data dict."""
    def replacer(match):
        key = match.group(1)
        return str(data.get(key, f"[{key}]"))

    return re.sub(r"\{\{(\w+)\}\}", replacer, template)


def output_path(month: str) -> str:
    """Generate the output file path for a given month string (YYYY-MM)."""
    dt = datetime.strptime(month, "%Y-%m")
    filename = dt.strftime("%Y-%m_uk-retail-market-review.md")
    return os.path.join("newsletters", filename)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a monthly UK Retail Market Financial Newsletter"
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Issue month in YYYY-MM format (e.g. 2026-04)",
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to the monthly data JSON file",
    )
    parser.add_argument(
        "--template",
        default="templates/newsletter-template.md",
        help="Path to the newsletter template (default: templates/newsletter-template.md)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: newsletters/YYYY-MM_uk-retail-market-review.md)",
    )
    args = parser.parse_args()

    template = load_template(args.template)
    data = load_data(args.data)

    newsletter = substitute_placeholders(template, data)

    out = args.output or output_path(args.month)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    with open(out, "w") as f:
        f.write(newsletter)

    print(f"Newsletter generated: {out}")


if __name__ == "__main__":
    main()
