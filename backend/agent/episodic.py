"""Episodic memory (cross-claim entity facts). See requirements.md §7, technical.md §2.

Keyed lookup by (entity_id, entity_type) -- not similarity search -- so this lives in
Postgres rather than Pinecone.
"""
import json

from .. import db


def get_facts(entity_id: str, entity_type: str) -> dict:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fact_key, fact_value FROM episodic_facts WHERE entity_id = %s AND entity_type = %s",
                (entity_id, entity_type),
            )
            rows = cur.fetchall()
    return {row["fact_key"]: row["fact_value"] for row in rows}


def upsert_fact(entity_id: str, entity_type: str, fact_key: str, fact_value, claim_id: str, source: str):
    provenance = {"claim_id": claim_id, "source": source}
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO episodic_facts (entity_id, entity_type, fact_key, fact_value, provenance)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, entity_type, fact_key)
                DO UPDATE SET fact_value = EXCLUDED.fact_value, provenance = EXCLUDED.provenance, updated_at = now()
                """,
                (entity_id, entity_type, fact_key, json.dumps(fact_value), json.dumps(provenance)),
            )
