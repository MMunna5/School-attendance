#!/usr/bin/env bash
set -o errexit
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm install --include=dev --no-audit --no-fund
mkdir -p attendance/static/attendance/css
npm run build:css
python manage.py collectstatic --noinput
python manage.py migrate
