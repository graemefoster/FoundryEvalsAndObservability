"""Flag domain facts that a candidate config copied into its prompt or tool descriptions.

The optimizer can raise scores by writing policy facts (amounts, approvers, dates,
people) into instructions.md or tools.json. Those copies go stale when the policy
changes. This check fails when a candidate introduces facts that the baseline did
not already contain.

Usage (from sample/):
    python evaluation/check_prompt_facts.py \
        --baseline agent/.agent_configs/baseline \
        --candidate path/to/candidate_config \
        --data agent/data/*.json

Exit code 1 means new facts were found. It's blunt on purpose: a human reviews the
list and either accepts the candidate or rejects it.
"""

import argparse
import json
import re
import sys
from pathlib import Path

GENERIC_FACTS = {
    "amount": re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$\s?\d+(?:\.\d+)?"),
    "duration": re.compile(r"\b\d+\s*(?:calendar\s+)?(?:hours?|days?|months?|years?)\b", re.I),
    "date": re.compile(
        r"\b(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2}|\d{1,2}\s+(?:January|February|"
        r"March|April|May|June|July|August|September|October|November|December))\b",
        re.I,
    ),
    "source_id": re.compile(r"\b(?:policy|notice|people|register|message):[a-z0-9-]+\b"),
}

# Capitalised phrases such as "Category Manager" or "Head of Learning", and
# CamelCase names such as "PrintForge". Used to harvest names from the corpus.
NAME_PHRASE = re.compile(
    r"\b[A-Z][a-z]+(?:\s+(?:of\s+)?[A-Z][a-zA-Z]+)+\b|\b[A-Z][a-z]+[A-Z][a-zA-Z]+\b"
)
STOP_PHRASES = {"Sources", "Return JSON", "From", "Note"}


def read_config_text(directory: Path) -> str:
    parts = []
    instructions = directory / "instructions.md"
    if instructions.is_file():
        parts.append(instructions.read_text(encoding="utf-8"))
    tools = directory / "tools.json"
    if tools.is_file():
        for tool in json.loads(tools.read_text(encoding="utf-8")):
            function = tool.get("function", tool)
            parts.append(function.get("description", ""))
            for prop in function.get("parameters", {}).get("properties", {}).values():
                parts.append(prop.get("description", ""))
    return "\n".join(parts)


def corpus_names(paths: list[Path]) -> set[str]:
    names = set()
    for path in paths:
        documents = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(documents, list):  # e.g. policy_embeddings.json: vectors, no text
            continue
        for document in documents:
            text = f"{document.get('title', '')}. {document.get('content', '')}"
            for match in NAME_PHRASE.findall(text):
                if match not in STOP_PHRASES and not match.startswith(
                    ("The ", "This ", "For ", "An ", "A ")
                ):
                    names.add(match)
    return names


def find_facts(text: str, names: set[str]) -> set[tuple[str, str]]:
    found = set()
    for kind, pattern in GENERIC_FACTS.items():
        for match in pattern.findall(text):
            found.add((kind, " ".join(match.split())))
    lowered = text.lower()
    for name in names:
        if re.search(r"\b" + re.escape(name.lower()) + r"\b", lowered):
            found.add(("name", name))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--data", type=Path, nargs="+", required=True, help="Policy/notice/people JSON files"
    )
    args = parser.parse_args()

    names = corpus_names(args.data)
    baseline = find_facts(read_config_text(args.baseline), names)
    candidate = find_facts(read_config_text(args.candidate), names)
    new_facts = sorted(candidate - baseline)

    if not new_facts:
        print("OK: candidate adds no domain facts beyond the baseline.")
        return 0
    print(f"FAIL: candidate adds {len(new_facts)} domain fact(s) not in the baseline:")
    for kind, value in new_facts:
        print(f"  [{kind}] {value}")
    print("These belong in the knowledge sources, not the prompt. Review before promoting.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
