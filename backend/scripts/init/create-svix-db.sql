-- Runs via Postgres /docker-entrypoint-initdb.d on first cluster init, before the
-- server accepts external connections — so svix-server never races DB creation.
-- Idempotent; the Python fallback (create_svix_db.py in app.sh) covers managed
-- Postgres, where init scripts do not run.
SELECT 'CREATE DATABASE svix'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'svix')\gexec
