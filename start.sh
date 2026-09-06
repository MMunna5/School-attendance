#!/usr/bin/env bash
set -e

python manage.py process_sms_queue &
worker_pid=$!

cleanup() {
    kill "$worker_pid" 2>/dev/null || true
    wait "$worker_pid" 2>/dev/null || true
}

trap cleanup TERM INT EXIT

gunicorn --bind 0.0.0.0:"$PORT" --timeout 120 core.wsgi:application
