#!/usr/bin/env bash
# Cron-friendly wrapper. Example crontab entry to run every 15 minutes:
#   */15 * * * * /home/you/desktop-tutorial/scripts/run.sh >> /tmp/fd-jobs.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
exec python -m jobsearch.main "$@"
