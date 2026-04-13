"""Email digest of new jobs."""
from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from .config import Config, env
from .models import Job


log = logging.getLogger(__name__)


def _format_salary(j: Job) -> str:
    if j.salary_raw:
        return j.salary_raw
    if j.salary_min and j.salary_max:
        return f"\u00a3{int(j.salary_min):,} \u2013 \u00a3{int(j.salary_max):,}"
    if j.salary_top():
        return f"\u00a3{int(j.salary_top()):,}"
    return "not stated"


def render_html(jobs: list[Job]) -> str:
    rows = []
    for j in jobs:
        tags = " ".join(f"<span style='background:#eef;padding:2px 6px;border-radius:4px;"
                        f"margin-right:4px;font-size:11px'>{html.escape(t)}</span>"
                        for t in j.tags)
        rows.append(
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;vertical-align:top'>"
            f"<div><a href='{html.escape(j.url)}' style='font-weight:600;color:#0b5'>"
            f"{html.escape(j.title)}</a></div>"
            f"<div style='color:#555;font-size:13px'>"
            f"{html.escape(j.company or 'Unknown')} \u2014 "
            f"{html.escape(j.location or '')}</div>"
            f"<div style='margin-top:4px'>{tags}</div>"
            f"</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;white-space:nowrap;"
            f"vertical-align:top;color:#333'>{html.escape(_format_salary(j))}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;"
            f"vertical-align:top;color:#888;font-size:12px'>{html.escape(j.source)}</td>"
            f"</tr>"
        )
    return (
        "<html><body style='font-family:Arial,sans-serif'>"
        f"<h2>{len(jobs)} new Finance Director role(s)</h2>"
        "<table style='border-collapse:collapse;width:100%'>"
        "<thead><tr style='text-align:left;color:#666;font-size:12px'>"
        "<th style='padding:8px'>Role</th><th style='padding:8px'>Salary</th>"
        "<th style='padding:8px'>Source</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></body></html>"
    )


def render_text(jobs: list[Job]) -> str:
    lines = [f"{len(jobs)} new Finance Director role(s):", ""]
    for j in jobs:
        lines.append(f"- {j.title} \u2014 {j.company or 'Unknown'} ({j.location or ''})")
        lines.append(f"  salary: {_format_salary(j)}  tags: {', '.join(j.tags) or '-'}")
        lines.append(f"  source: {j.source}  link: {j.url}")
        lines.append("")
    return "\n".join(lines)


def send_email(jobs: Iterable[Job], cfg: Config) -> bool:
    jobs = list(jobs)
    if not jobs and cfg.skip_if_empty:
        log.info("No new jobs; skipping email.")
        return False

    host = env("SMTP_HOST")
    port = int(env("SMTP_PORT", "587"))
    user = env("SMTP_USER")
    password = env("SMTP_PASSWORD")
    sender = env("EMAIL_FROM") or user
    recipient = env("EMAIL_TO")

    if not (host and user and password and sender and recipient):
        log.warning("Email env vars missing; printing digest to stdout instead.")
        print(render_text(jobs))
        return False

    jobs = jobs[: cfg.max_jobs_per_email]
    msg = EmailMessage()
    msg["Subject"] = f"{cfg.subject_prefix} {len(jobs)} new role(s)"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(render_text(jobs))
    msg.add_alternative(render_html(jobs), subtype="html")

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    log.info("Sent digest of %d jobs to %s", len(jobs), recipient)
    return True
