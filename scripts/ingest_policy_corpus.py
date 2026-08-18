"""Ingest the policy/regulation markdown corpus (docs/files/*.md) into Qdrant.

Phase 3 ingestion script (requirements.md §9, specs/tracker.md). Clause-boundary
chunker: one chunk per ### / #### heading (each is a single numbered policy
provision, e.g. "FRD-2.1"), not naive paragraph splitting. The fixed-order
metadata lines directly under each heading (**Effective:**, **Applies to:**,
**Cross-references:**, **Regulatory basis:**, ...) are parsed into the payload
and stripped out of the embedded text; the section heading path is prepended to
the clause body instead, per docs/files/00_CORPUS_INDEX.md's own guidance that
heading-path text retrieves better than the bare clause.

Usage:
    python scripts/ingest_policy_corpus.py

Environment variables (see .env.example):
    OPENAI_API_KEY     used for text-embedding-3-small
    QDRANT_URL, QDRANT_API_KEY
    QDRANT_COLLECTION  optional, defaults to "claims-policy-corpus"
"""

import os
import re
import uuid

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env.local"))

DOCS_DIR = os.path.join(ROOT, "docs", "files")
COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION", "claims-policy-corpus")
EMBED_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
EMBED_BATCH_SIZE = 100
ID_NAMESPACE = uuid.UUID("c39b6a1e-2a7f-4e3a-9a3d-2b0a6d6f2b40")

# Filename prefix -> claim taxonomy (backend/agent/checks.py). Files with no
# entry here (e.g. 00_CORPUS_INDEX.md, which is meta-documentation about the
# corpus rather than policy text) are skipped.
#
# "network_recovery" isn't a real claim_type (backend/agent/checks.py's
# REQUIRED_CHECKS only has "billing_dispute"/"fraud") -- it's a separate tag reusing
# search_policy's/search_network_policy's existing claim_type-filtered-collection
# pattern (specs/technical.md §5) for the on-demand Recovery agent's own corpus,
# kept in the same Qdrant collection rather than standing up a second one.
CLAIM_TYPE_BY_DOC_ID = {
    "ACH": "billing_dispute",
    "CCD": "billing_dispute",
    "DBD": "billing_dispute",
    "ZEL": "billing_dispute",
    "FRD": "fraud",
    "NWR": "network_recovery",
}

HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")
CLAUSE_RE = re.compile(r"^(?P<id>[A-Z]+-[\d.]+[a-z]?)\s+—\s+(?P<title>.+)$")
META_RE = re.compile(r"^\*\*([\w /\-]+):\*\*\s*(.*)$")


def parse_file(filepath: str) -> list[dict]:
    filename = os.path.basename(filepath)
    doc_id = filename.split("_", 1)[0]
    claim_type = CLAIM_TYPE_BY_DOC_ID.get(doc_id)
    if claim_type is None:
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    doc_title = None
    section = None
    clause_heading = None
    chunks: list[dict] = []
    current = None

    def flush():
        if current is None:
            return
        body = "\n".join(current["body_lines"]).strip()
        if not body:
            return
        chunks.append(
            {
                "citation": current["clause_id"],
                "title": current["title"],
                "section_path": current["heading_path"],
                "doc_id": doc_id,
                "doc_title": doc_title,
                "claim_type": claim_type,
                "source": filename,
                "meta": current["meta"],
                "text": f"{current['heading_path']}: {body}",
            }
        )

    for line in lines:
        if doc_title is None and line.startswith("# "):
            doc_title = line[2:].strip()
            continue

        m = HEADING_RE.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 2:
                flush()
                current = None
                section, clause_heading = text, None
                continue

            clause_m = CLAUSE_RE.match(text)
            flush()
            current = None
            if clause_m:
                title = clause_m.group("title")
                heading_path = (
                    f"{section} > {clause_heading} > {title}"
                    if level == 4 and clause_heading
                    else f"{section} > {title}"
                )
                current = {
                    "clause_id": clause_m.group("id"),
                    "title": title,
                    "heading_path": heading_path,
                    "meta": {},
                    "body_lines": [],
                    "in_meta_block": True,
                    "meta_started": False,
                }
                if level == 3:
                    clause_heading = title
            continue

        if current is None:
            continue

        stripped = line.strip()
        if current["in_meta_block"]:
            meta_m = META_RE.match(stripped)
            if meta_m:
                key = meta_m.group(1).strip().lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                current["meta"][key] = meta_m.group(2).strip()
                current["meta_started"] = True
                continue
            if stripped == "":
                if current["meta_started"]:
                    current["in_meta_block"] = False
                continue
            current["in_meta_block"] = False

        if stripped == "---":
            continue
        current["body_lines"].append(line)

    flush()
    return chunks


def embed_all(client: OpenAI, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend(d.embedding for d in resp.data)
        print(f"  embedded {min(start + EMBED_BATCH_SIZE, len(texts))}/{len(texts)}")
    return vectors


def main() -> None:
    chunks: list[dict] = []
    for filename in sorted(os.listdir(DOCS_DIR)):
        if filename.endswith(".md"):
            chunks.extend(parse_file(os.path.join(DOCS_DIR, filename)))

    if not chunks:
        print(f"No policy chunks parsed from {DOCS_DIR}")
        return

    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c["claim_type"]] = by_type.get(c["claim_type"], 0) + 1
    print(f"Parsed {len(chunks)} clauses: {by_type}")

    openai_client = OpenAI()
    print(f"Embedding {len(chunks)} clauses via {EMBED_MODEL}...")
    vectors = embed_all(openai_client, [c["text"] for c in chunks])

    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"]
    )
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
    qdrant.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="claim_type",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )

    points = [
        models.PointStruct(
            id=str(uuid.uuid5(ID_NAMESPACE, f"{c['doc_id']}:{c['citation']}")),
            vector=vector,
            payload=c,
        )
        for c, vector in zip(chunks, vectors)
    ]

    print(f"Upserting {len(points)} points into Qdrant collection '{COLLECTION_NAME}'...")
    for start in range(0, len(points), EMBED_BATCH_SIZE):
        batch = points[start : start + EMBED_BATCH_SIZE]
        qdrant.upsert(collection_name=COLLECTION_NAME, points=batch)
        print(f"  upserted {min(start + EMBED_BATCH_SIZE, len(points))}/{len(points)}")

    print("Ingestion complete!")


if __name__ == "__main__":
    main()
