import json
import re
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent / "data"
STOP_WORDS = set("a an and are can for from i in is it of on or our the to we with".split())


def read_documents(filename: str) -> list[dict]:
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def _search(filename: str, query: str) -> list[dict]:
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
    return [by_id[row[0]] for row in matches]


# The three tools below mimic the shape of the Microsoft IQ MCP tools. The real IQ
# sources are LLM-backed; these are deterministic stand-ins over local data.


def knowledge_base_retrieve(queries: list[str]) -> str:
    """Simulated Foundry IQ knowledge base: policy documents."""
    references = {}
    for query in queries:
        for document in _search("policies.json", query):
            references.setdefault(document["id"], document)
    return json.dumps({"queries": queries, "references": list(references.values())})


def ask(question: str) -> str:
    """Simulated Work IQ: workplace messages, exceptions and clearances."""
    return json.dumps({"question": question, "results": _search("notices.json", question)})


def search_ontology(question: str) -> str:
    """Simulated Fabric IQ ontology: business entities such as department budgets."""
    result = {"entity": "Department", "available_budget": 50000, "currency": "AUD"}
    return json.dumps({"question": question, "results": [result]})
