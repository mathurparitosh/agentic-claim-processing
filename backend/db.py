import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL is not set in .env.local')

pool = ConnectionPool(
    DATABASE_URL,
    kwargs={'row_factory': dict_row},
    open=False,
)


def open_pool():
    pool.open(wait=True)


def close_pool():
    pool.close()


def get_connection():
    """Checkout a pooled connection. Use as a context manager: `with get_connection() as conn:`."""
    return pool.connection()


def test_connection():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            return cur.fetchone()
