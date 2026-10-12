"""Embed the policies for hybrid search in knowledge_base_retrieve.

Run from sample/ after any change to agent/data/policies.json (needs FOUNDRY_PROJECT_ENDPOINT):
    python agent/build_embeddings.py
Check, without network access, that the stored embeddings match the policies (used in CI):
    python agent/build_embeddings.py --check
"""

import argparse
import json
import sys

import tools


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Fail if embeddings are stale.")
    args = parser.parse_args()
    policies = tools.read_documents("policies.json")

    if args.check:
        stored = json.loads(tools.EMBEDDINGS.read_text()) if tools.EMBEDDINGS.is_file() else {}
        stale = tools.stale_policies(policies, stored)
        if stale:
            sys.exit(
                f"Stale or missing embeddings for {stale}.\nRun: python agent/build_embeddings.py"
            )
        print(f"Embeddings match all {len(policies)} policies.")
        return

    vectors = tools.embed([tools.policy_text(p) for p in policies])
    stored = {
        "model": tools.EMBEDDING_DEPLOYMENT,
        "dimensions": tools.EMBEDDING_DIMENSIONS,
        "policies": {
            p["id"]: {"hash": tools.policy_hash(p), "vector": [round(x, 6) for x in v]}
            for p, v in zip(policies, vectors, strict=True)
        },
    }
    tools.EMBEDDINGS.write_text(json.dumps(stored, separators=(",", ":")) + "\n")
    print(f"Wrote {tools.EMBEDDINGS.name} ({len(policies)} policies).")


if __name__ == "__main__":
    main()
