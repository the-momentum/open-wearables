import os
import sys

import psycopg

try:
    psycopg.connect(
        dbname=os.getenv("DB_NAME", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", ""),
        port=os.getenv("DB_PORT", ""),
    )
except psycopg.OperationalError:
    print("- PostgreSQL unavaliable - waiting")
    sys.exit(-1)
sys.exit(0)
