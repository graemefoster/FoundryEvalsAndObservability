"""Replay an external terminal transcript without making cloud calls."""

import argparse
import sys
import time
from pathlib import Path


def replay(transcript: Path) -> None:
    content = transcript.read_text()
    if not content.strip():
        raise ValueError(f"Replay transcript is empty: {transcript}")
    lines = content.splitlines(keepends=True)

    print(
        "DEMO REPLAY - historical output; no cloud calls or new run.",
        file=sys.stderr,
        flush=True,
    )
    for line in lines:
        time.sleep(10 / len(lines))
        sys.stdout.write(line)
        sys.stdout.flush()
    print(
        "\nDEMO REPLAY ended. IDs and statuses above belong to the earlier run.",
        file=sys.stderr,
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay an optimisation transcript offline.")
    parser.add_argument("command", choices=["optimize"])
    parser.add_argument("--transcript", type=Path, required=True)
    args = parser.parse_args()
    replay(args.transcript)


if __name__ == "__main__":
    main()
