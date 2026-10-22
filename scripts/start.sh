#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py prepare_deploy
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8017}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
