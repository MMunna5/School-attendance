#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate
