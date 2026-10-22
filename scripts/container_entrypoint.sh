#!/bin/sh
set -eu

if [ "${PYTRADEKIT_RUN_MIGRATIONS:-1}" = "1" ]; then
    alembic -c /app/alembic.ini upgrade head
fi

exec pytradekit "$@"
