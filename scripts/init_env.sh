#!/bin/sh
# Creates the missing .env files from their examples and generates SECRET_KEY when it is empty
# or still the old .env.example default. Any other value is kept, so it is safe to run again.
set -eu
cd "$(dirname "$0")/.."

BACKEND_ENV=backend/config/.env

if [ ! -f "$BACKEND_ENV" ]; then
    (umask 077 && cp backend/config/.env.example "$BACKEND_ENV")
    echo "Created $BACKEND_ENV"
fi
if [ ! -f frontend/.env ]; then
    cp frontend/.env.example frontend/.env
    echo "Created frontend/.env"
fi

if grep -Eq '^SECRET_KEY=(secret-key-str)?$' "$BACKEND_ENV"; then
    key=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
    (umask 077 && sed -E "s/^SECRET_KEY=(secret-key-str)?$/SECRET_KEY=$key/" "$BACKEND_ENV" > "$BACKEND_ENV.tmp")
    mv "$BACKEND_ENV.tmp" "$BACKEND_ENV"
    echo "Generated SECRET_KEY (a replaced key signs everyone out)"
fi

echo "Next: make run"
