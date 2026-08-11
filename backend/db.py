import os

from psycopg import connect
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set in .env.local')


def get_connection():
    return connect(DATABASE_URL, row_factory=dict_row)


def test_connection():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            return cur.fetchone()
