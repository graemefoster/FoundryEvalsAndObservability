import hashlib
import json
import logging
import math
import os
import re
import sqlite3
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path(__file__).parent / "data"
EMBEDDINGS = DATA / "policy_embeddings.json"
EMBEDDING_DEPLOYMENT = os.environ.get("EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = 512
POLICY_RESULTS = 5
RRF_K = 60  # reciprocal rank fusion constant, as used by Azure AI Search hybrid queries
STOP_WORDS = set("a an and are can for from i in is it of on or our the to we with".split())

log = logging.getLogger(__name__)


def read_documents(filename: str) -> list[dict]:
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def _keyword_ranking(filename: str, query: str, limit: int | None = 3) -> list[str]:
    """BM25 over title and content. Returns document IDs, best first."""
    terms = sorted(set(re.findall(r"[a-z0-9]+", query.lower())) - STOP_WORDS)
    if not terms:
        raise ValueError("Provide searchable words, such as a supplier, product or policy topic.")
    documents = read_documents(filename)
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
        sql = (
            "SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents, 0, 3, 1), id"
        )
        params: tuple = (" OR ".join(f'"{term}"' for term in terms),)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        return [row[0] for row in connection.execute(sql, params).fetchall()]


def _search(filename: str, query: str) -> list[dict]:
    by_id = {document["id"]: document for document in read_documents(filename)}
    return [by_id[doc_id] for doc_id in _keyword_ranking(filename, query)]


# Policy embeddings: built offline by build_embeddings.py, checked against policies.json.


def policy_text(policy: dict) -> str:
    return f"{policy['title']}\n\n{policy['content']}"


def policy_hash(policy: dict) -> str:
    return hashlib.sha256(policy_text(policy).encode("utf-8")).hexdigest()[:16]


# Embeddings call the account's OpenAI v1 endpoint on its cognitiveservices.azure.com host, as
# Microsoft documents for agent code calling the account directly. Tested: the project route
# returns 404 for embeddings, and the services.ai.azure.com host refuses the hosted agent's
# identity (401) even with the role. The agent identity needs Cognitive Services OpenAI User on
# the account, which infra/grant-agent-embeddings.sh grants after each deploy.
EMBEDDING_SCOPE = "https://cognitiveservices.azure.com/.default"


def openai_endpoint() -> str:
    if explicit := os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return explicit.rstrip("/") + "/openai/v1/"
    host = urlsplit(
        os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    ).netloc  # <account>.services.ai.azure.com
    account = host.split(".")[0]
    return f"https://{account}.cognitiveservices.azure.com/openai/v1/"


@cache
def _openai_client():
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    token = get_bearer_token_provider(DefaultAzureCredential(), EMBEDDING_SCOPE)
    return OpenAI(base_url=openai_endpoint(), api_key=token)


def embed(texts: list[str]) -> list[list[float]]:
    response = _openai_client().embeddings.create(
        model=EMBEDDING_DEPLOYMENT, input=texts, dimensions=EMBEDDING_DIMENSIONS
    )
    return [item.embedding for item in response.data]


def _caller_identity() -> str:
    """Which identity the call ran as, read from the token's claims (for diagnosing 401s)."""
    try:
        import base64

        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(EMBEDDING_SCOPE)
        payload = token.token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return f"oid={claims.get('oid')} appid={claims.get('appid') or claims.get('azp')}"
    except Exception as error:
        return f"unknown ({type(error).__name__})"


def stale_policies(policies: list[dict], stored: dict) -> list[str]:
    vectors = stored.get("policies", {})
    return [p["id"] for p in policies if vectors.get(p["id"], {}).get("hash") != policy_hash(p)]


@cache
def _policy_vectors() -> dict[str, list[float]] | None:
    if not EMBEDDINGS.is_file():
        log.warning("%s is missing; policy search is keyword-only.", EMBEDDINGS.name)
        return None
    stored = json.loads(EMBEDDINGS.read_text(encoding="utf-8"))
    stale = stale_policies(read_documents("policies.json"), stored)
    if stale:
        log.warning("Embeddings are stale for %s; policy search is keyword-only.", stale)
        return None
    return {doc_id: entry["vector"] for doc_id, entry in stored["policies"].items()}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _fuse(*rankings: list[str]) -> list[str]:
    """Reciprocal rank fusion: documents ranked well by either method rise to the top."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores, key=lambda doc_id: (-scores[doc_id], doc_id))


# The three tools below mimic the shape of the Microsoft IQ MCP tools. The real IQ
# sources are LLM-backed; these are deterministic stand-ins over local data.


def knowledge_base_retrieve(queries: list[str]) -> str:
    """Simulated Foundry IQ knowledge base: hybrid (keyword + vector) search over policies."""
    policies = {p["id"]: p for p in read_documents("policies.json")}
    vectors = _policy_vectors()
    query_vectors = None
    fallback = "embeddings missing or stale"
    if vectors is not None:
        try:
            query_vectors = embed(queries)
        except Exception as error:  # degrade to keyword search rather than fail the conversation
            log.warning("Query embedding failed; policy search is keyword-only.", exc_info=True)
            fallback = f"embedding call failed: {type(error).__name__}: {str(error)[:300]}"
            if "PermissionDenied" in str(error):
                fallback += f" Caller: {_caller_identity()}"
    references = {}
    for i, query in enumerate(queries):
        keyword = _keyword_ranking("policies.json", query, limit=None)
        if query_vectors is None:
            ranked = keyword
        else:
            similarity = {doc_id: _cosine(query_vectors[i], v) for doc_id, v in vectors.items()}
            semantic = sorted(similarity, key=lambda doc_id: -similarity[doc_id])
            ranked = _fuse(keyword, semantic)
        for doc_id in ranked[:POLICY_RESULTS]:
            references.setdefault(doc_id, policies[doc_id])
    result = {"queries": queries, "search_mode": "hybrid"}
    if query_vectors is None:
        result |= {"search_mode": "keyword", "fallback_reason": fallback}
    return json.dumps(result | {"references": list(references.values())})


LINE_MANAGER = re.compile(r"Line manager: ([^.]+)\.")
ROLE_HOLDER = re.compile(r"Role directory: ([^.]+?) is the ([^.]+)\.")
ABOUT_AUTHORITY = re.compile(r"delegat|approv|cover|sign", re.IGNORECASE)


def _holder_records(name: str, question: str) -> list[dict]:
    """The person's directory record, plus their recorded delegations if the question asks."""
    records = []
    for document in read_documents("people.json") + read_documents("roster.json"):
        content = document["content"]
        if content.startswith((f"Directory: {name} manages", f"Role directory: {name} is")):
            records.append(document)
        elif ABOUT_AUTHORITY.search(question) and re.match(
            rf"Recorded by {re.escape(name)}[.,]", content
        ):
            records.append(document)
    return records


def _resolve_people(results: list[dict], question: str) -> list[dict]:
    """Real Work IQ resolves "my line manager" or "the Hospitality Lead" and answers about
    that person, so a single question reaches their availability and delegations."""
    names = [m.group(1) for r in results if (m := LINE_MANAGER.search(r["content"]))]
    for document in read_documents("people.json"):
        match = ROLE_HOLDER.match(document["content"])
        if match and match.group(2).lower() in question.lower():
            names.append(match.group(1))
    return [record for name in dict.fromkeys(names) for record in _holder_records(name, question)]


def ask(question: str) -> str:
    """Simulated Work IQ: people, roles, availability, messages, notices and clearances."""
    results = (
        _search("notices.json", question)
        + _search("people.json", question)
        + _search("roster.json", question)
    )
    results += _resolve_people(results, question)
    unique = list({r["id"]: r for r in results}.values())
    return json.dumps({"question": question, "results": unique})


def search_ontology(question: str) -> str:
    """Simulated Fabric IQ ontology: business entities such as department budgets."""
    result = {
        "id": "ontology:department-budget",
        "entity": "Department",
        "available_budget": 50000,
        "currency": "dollars",
    }
    return json.dumps({"question": question, "results": [result]})
