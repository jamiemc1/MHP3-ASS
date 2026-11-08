"""Summarise the differential-fuzz goldens: how many solutions the fuzz queries find.

Reads tests/golden/fuzz/*.manifest.json (written by
scripts/windows/generate-goldens.ps1 -Fuzz) and prints a Markdown table of
solution counts by bin, by charm mode and by skill count, plus the files
that would be committed. The fuzz plan asks for 10-40 % of queries with no
solutions and at least 5 % with more than 10,000.

    uv run python scripts/fuzz_corpus_report.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def solution_bin(count: int) -> str:
    if count == 0:
        bin_name = "0"
    elif count <= 100:
        bin_name = "1-100"
    elif count <= 10_000:
        bin_name = "101-10k"
    else:
        bin_name = "> 10k"
    return bin_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--golden-dir", type=Path, default=repo_root / "tests" / "golden" / "fuzz")
    args = parser.parse_args()

    bins = ["0", "1-100", "101-10k", "> 10k"]
    by_bin: Counter[str] = Counter()
    by_mode: dict[str, Counter[str]] = {}
    by_skills: dict[int, Counter[str]] = {}
    exceptions = []
    for path in sorted(args.golden_dir.glob("*.manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        query = json.loads(manifest["query_json"])
        bin_name = solution_bin(manifest["solution_count"])
        by_bin[bin_name] += 1
        by_mode.setdefault(query["charm_mode"], Counter())[bin_name] += 1
        by_skills.setdefault(len(query["skills"]), Counter())[bin_name] += 1
        if manifest["exception"] is not None:
            exceptions.append(path.name)
    total = sum(by_bin.values())

    print("| Solutions | " + " | ".join(bins) + " |")
    print("|---|" + "---|" * len(bins))
    print(
        "| All queries | "
        + " | ".join(f"{by_bin[b]} ({100 * by_bin[b] / total:.0f} %)" for b in bins)
        + " |"
    )
    for mode in sorted(by_mode):
        print(f"| {mode} | " + " | ".join(str(by_mode[mode][b]) for b in bins) + " |")
    for skills in sorted(by_skills):
        print(
            f"| {skills} skill(s) | " + " | ".join(str(by_skills[skills][b]) for b in bins) + " |"
        )

    files = list(args.golden_dir.iterdir())
    size = sum(path.stat().st_size for path in files)
    solution_files = sum(1 for path in files if path.name.endswith(".solutions.txt.gz"))
    print()
    print(f"{total} manifests, {solution_files} solution files, {size / 1e6:.1f} MB in all")
    print(f"Exceptions recorded: {exceptions if exceptions else 'none'}")


if __name__ == "__main__":
    main()
