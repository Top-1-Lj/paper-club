#!/usr/bin/env sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
port="${1:-8000}"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py import_papers
printf 'Paper Club: http://127.0.0.1:%s\n' "$port"
printf 'Demo accounts: lin / chen; initial password: PaperClub2026!\n'
exec .venv/bin/python manage.py runserver "127.0.0.1:$port"
