#!/bin/sh
# Prepares the local .env files: copies the missing ones from .env.example and generates
# each secret below that is empty, too short, or still set to a value the repository has
# published. A value the backend accepts is never changed, so it is safe to run again.
set -eu

cd "$(dirname "$0")/.."

BACKEND_ENV=backend/config/.env
FRONTEND_ENV=frontend/.env

# Usage: copy_if_missing SOURCE TARGET [MODE]
copy_if_missing() {
    if [ -f "$2" ]; then
        echo "Kept     $2"
        return
    fi
    cp "$1" "$2"
    if [ $# -ge 3 ]; then
        chmod "$3" "$2"
    fi
    echo "Created  $2"
}

# Lines that set NAME, the way python-dotenv reads them: an optional "export" and spaces
# around "=" are allowed. The name only contains [A-Z_], so it is safe inside the pattern.
line_pattern() {
    printf '^[ \\t]*(export[ \\t]+)?%s[ \\t]*=' "$1"
}

# Prints NAME's value from the backend .env the way python-dotenv reads it: a quoted value
# runs to its closing quote, an unquoted one ends at " #" (a comment). A CR is dropped.
# Reads the last occurrence, because that is the one python-dotenv uses.
current_value() {
    awk -v pattern="$(line_pattern "$1")" '
        { sub(/\r$/, "") }
        match($0, pattern) {
            value = substr($0, RLENGTH + 1)
            sub(/^[ \t]+/, "", value)
            quote = substr(value, 1, 1)
            if (quote == "\"" || quote == "\047") {
                value = substr(value, 2)
                end = index(value, quote)
                if (end) value = substr(value, 1, end - 1)
            } else {
                sub(/[ \t]+#.*$/, "", value)
                sub(/[ \t]+$/, "", value)
            }
            found = value
        }
        END { print found }
    ' "$BACKEND_ENV"
}

# Writes NAME=VALUE in place of the first line that sets NAME and drops any later ones,
# or appends it if there is none.
set_value() {
    tmp=$(mktemp)
    # The copy holds every secret in .env, so it must not outlive a failed write.
    trap 'rm -f "$tmp"' EXIT
    trap 'exit 1' INT TERM
    awk -v pattern="$(line_pattern "$1")" -v line="$1=$2" '
        match($0, pattern) { if (!done) print line; done = 1; next }
        { print }
        END { if (!done) print line }
    ' "$BACKEND_ENV" > "$tmp"
    # Writing through the existing file keeps its permissions.
    cat "$tmp" > "$BACKEND_ENV"
    rm -f "$tmp"
    trap - EXIT INT TERM
}

random_hex() {
    od -An -tx1 -N32 /dev/urandom | tr -d ' \n'
}

# Usage: ensure_secret NAME MIN_LENGTH [published value...]
# Adds NAME to $replaced when it replaces a value that was set.
ensure_secret() {
    name=$1
    min_length=$2
    shift 2
    current=$(current_value "$name")
    case "$current" in
        *'$'*)
            # python-dotenv expands ${VAR}, so the literal text says nothing about the key the
            # backend gets. Leave it alone: the backend still refuses a bad expanded value.
            echo "Kept     $name (it references another variable, not checked)"
            return
            ;;
    esac
    reason=""
    for value in "$@"; do
        if [ "$current" = "$value" ]; then
            reason="it was a published default"
        fi
    done
    if [ -z "$current" ]; then
        reason=empty
    elif [ -z "$reason" ] && [ "${#current}" -lt "$min_length" ]; then
        reason="it was shorter than $min_length characters"
    fi
    if [ -z "$reason" ]; then
        echo "Kept     $name"
        return
    fi
    set_value "$name" "$(random_hex)"
    if [ "$reason" = empty ]; then
        echo "Set      $name"
    else
        echo "Replaced $name ($reason)"
        replaced="$replaced $name"
    fi
}

replaced=""

# The backend file is about to hold secrets, so only its owner may read it.
copy_if_missing backend/config/.env.example "$BACKEND_ENV" 600
copy_if_missing frontend/.env.example "$FRONTEND_ENV"

# Keep in sync with PUBLISHED_SECRET_VALUES and MIN_SECRET_KEY_LENGTH in backend/app/config.py;
# backend/tests/scripts/test_init_env_script.py checks that it is.
ensure_secret SECRET_KEY 32 secret-key-str

case "$replaced" in
    *SECRET_KEY*)
        echo
        echo "Run \`make run\` to recreate the containers with the new SECRET_KEY: \`docker compose"
        echo "restart\` keeps the old one. The new key signs everyone out and invalidates issued SDK"
        echo "tokens. Webhook secrets that default to SECRET_KEY change too: register those"
        echo "webhooks again and update the secret in the Suunto portal."
        ;;
esac

echo
echo "Next: make run"
