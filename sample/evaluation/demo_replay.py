"""Replay an external terminal transcript without making cloud calls.

Transcripts live outside the repository in $DEMO_REPLAY_DIR:
    evaluation.txt    replayed by `evaluate.py --demo-replay` or `demo_replay.py evaluate`
    optimisation.txt  replayed by `demo_replay.py optimize`

Before going live, run `demo_replay.py check` in the terminal you will present from.
Capture a transcript from a real run with, for example:
    azd ai agent optimize --config evaluation/optimize.yaml 2>&1 \
        | tee "$DEMO_REPLAY_DIR/optimisation.txt"
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

TRANSCRIPTS = {"evaluate": "evaluation.txt", "optimize": "optimisation.txt"}
# Inputs that change what a fresh run would print. A transcript older than these may be stale.
RUN_INPUTS = [
    "evaluation/datasets",
    "evaluation/optimize.yaml",
    "evaluation/overfitting-demo",
    "evaluation/purchasing-next-action.json",
    "evaluation/purchasing-demo-rubric.json",
    "agent/.agent_configs/baseline",
    "agent/data",
]
SAMPLE_DIR = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"DEMO REPLAY: {message}", file=sys.stderr, flush=True)
    raise SystemExit(2)


def replay_dir() -> Path:
    value = os.environ.get("DEMO_REPLAY_DIR", "").strip()
    if not value:
        fail(
            "DEMO_REPLAY_DIR is not set in this terminal. "
            'Run: export DEMO_REPLAY_DIR="/path/to/your/transcripts"'
        )
    directory = Path(value).expanduser()
    if not directory.is_dir():
        fail(f"DEMO_REPLAY_DIR does not exist: {directory}")
    return directory


def replay(transcript: Path) -> None:
    if not transcript.is_file():
        hint = "" if os.environ.get("DEMO_REPLAY_DIR") else " (DEMO_REPLAY_DIR is not set)"
        fail(f"transcript not found: {transcript}{hint}")
    content = transcript.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        fail(f"transcript is empty: {transcript}")
    lines = content.splitlines(keepends=True)

    print(
        "DEMO REPLAY - historical output; no cloud calls or new run.",
        file=sys.stderr,
        flush=True,
    )
    delay = min(10 / len(lines), 0.5)
    for line in lines:
        time.sleep(delay)
        sys.stdout.write(line)
        sys.stdout.flush()
    print(
        "\nDEMO REPLAY ended. IDs and statuses above belong to the earlier run.",
        file=sys.stderr,
        flush=True,
    )


def newest_input() -> tuple[float, str]:
    newest = (0.0, "")
    for relative in RUN_INPUTS:
        path = SAMPLE_DIR / relative
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for file in files:
            mtime = file.stat().st_mtime
            if mtime > newest[0]:
                newest = (mtime, str(file.relative_to(SAMPLE_DIR)))
    return newest


def check() -> None:
    directory = replay_dir()
    input_mtime, input_name = newest_input()
    problems = 0
    for command, name in TRANSCRIPTS.items():
        path = directory / name
        if not path.is_file():
            print(f"MISSING  {name:<18} needed by: {command}")
            problems += 1
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            print(f"EMPTY    {name:<18} needed by: {command}")
            problems += 1
            continue
        captured = datetime.fromtimestamp(path.stat().st_mtime)
        status = "OK"
        if path.stat().st_mtime < input_mtime:
            status = "STALE"
            problems += 1
        print(
            f"{status:<8} {name:<18} {len(text.splitlines())} lines, "
            f"captured {captured:%d %b %H:%M}"
        )
        if status == "STALE":
            print(f"         older than {input_name}; a fresh run would print different output.")
    if problems:
        raise SystemExit(1)
    print("All transcripts present and newer than the agent, data and evaluation inputs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay or check demo transcripts offline.")
    parser.add_argument("command", choices=["optimize", "evaluate", "check"])
    parser.add_argument(
        "--transcript", type=Path, help="Defaults to the matching file in $DEMO_REPLAY_DIR."
    )
    args = parser.parse_args()
    if args.command == "check":
        check()
        return
    replay(args.transcript or replay_dir() / TRANSCRIPTS[args.command])


if __name__ == "__main__":
    main()
