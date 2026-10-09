import json
import re
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent / "data"
STOP_WORDS = set("a an and are can for from i in is it of on or our the to we with".split())


def read_documents(filename: str) -> list[dict]:
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def _search(filename: str, query: str) -> str:
    terms = sorted(set(re.findall(r"[a-z0-9]+", query.lower())) - STOP_WORDS)
    if not terms:
        raise ValueError("Provide searchable words, such as a supplier, product or policy topic.")
    documents = read_documents(filename)
    by_id = {document["id"]: document for document in documents}
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE VIRTUAL TABLE documents USING fts5("
            "id UNINDEXED, title, content, tokenize='porter unicode61')"
        )
        connection.executemany(
            "INSERT INTO documents (id, title, content) VALUES (?, ?, ?)",
            [(d["id"], d["title"], d["content"]) for d in documents],
        )
        # Match any query term; title matches carry more weight than body matches.
        matches = connection.execute(
            "SELECT id FROM documents WHERE documents MATCH ? "
            "ORDER BY bm25(documents, 0, 3, 1), id LIMIT 3",
            (" OR ".join(f'"{term}"' for term in terms),),
        ).fetchall()
    return json.dumps({"query": query, "documents": [by_id[row[0]] for row in matches]})


def search_policies(query: str) -> str:
    """Search organisational policies relevant to purchases and related commitments."""
    return _search("policies.json", query)


def search_workplace_notices(query: str) -> str:
    """Search workplace exceptions and security clearances."""
    return _search("notices.json", query)


def get_department_budget() -> str:
    """Return the requester's available department budget."""
    # Stands in for a Fabric IQ lookup of governed business data; the value is fixed.
    budget = {"available_budget": 50000, "currency": "AUD", "source": "fabric-iq-simulated"}
    return json.dumps(budget)
