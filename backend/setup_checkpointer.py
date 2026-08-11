"""Create LangGraph's PostgresSaver checkpoint tables against DATABASE_URL.

Idempotent — safe to re-run. Run once per fresh database (local dev, or after
provisioning the deploy server's Postgres instance).

    python -m backend.setup_checkpointer
"""
from langgraph.checkpoint.postgres import PostgresSaver

from .db import DATABASE_URL


def main():
    with PostgresSaver.from_conn_string(DATABASE_URL) as saver:
        saver.setup()
    print("PostgresSaver checkpoint tables ready.")


if __name__ == "__main__":
    main()
