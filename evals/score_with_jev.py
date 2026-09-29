#!/usr/bin/env python3
"""Score clean-mode with/without outputs on TypeSafe Jev dimensions.

    pip install typesafe-sdk
    export TYPESAFE_API_KEY=...
    python3 evals/score_with_jev.py

Runs `claude plugin eval` for the given case glob (default: every clean-mode
case), then scores each captured with/without output on three dimensions
taken from clean-mode's own general principles: whether the opening states
the outcome before implementation detail, whether it scans (short
paragraphs/lists), and whether implementation detail is kept separate from
the summary. Use --from to re-score an existing `claude plugin eval --json`
result instead of running a new eval.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from typesafe_sdk import Score, TypeSafeClient
except ImportError:
    sys.exit("typesafe-sdk is not installed. Run: pip install typesafe-sdk")

DIMENSIONS = {
    "outcome_first": Score(
        instructions=(
            "Does the document's opening (before any implementation or technical "
            "detail) state the outcome, decision, or summary of the work?"
        ),
        criteria=[
            "The opening is implementation detail, technical steps, or raw notes; the outcome/summary is buried or absent",
            "The opening mixes some outcome/summary language with implementation detail",
            "The opening is a clear, short outcome/summary, with implementation detail appearing only afterward",
        ],
    ),
    "scannability": Score(
        instructions=(
            "Is the document's structure matched to its content, at the level of "
            "individual sections, not just the document as a whole? Headings alone do "
            "not make a document scannable: a section can sit under a clear heading and "
            "still be a dense, multi-sentence paragraph of reasoning that a reader must "
            "read in full to follow. Check every section's body, not only whether "
            "headings exist. Also judge the other two ways structure can mismatch "
            "content: genuinely parallel items left as prose instead of a list, and "
            "content chopped into more headers or single-item sections than it "
            "warrants, forcing the reader to track many small fragments instead of a "
            "few clear groupings."
        ),
        criteria=[
            "One or more sections (regardless of how many headings the document has) are dense, multi-sentence paragraphs of reasoning or explanation that a reader must read in full to get the point; or the whole document is undifferentiated prose with no headings or lists for parallel items",
            "Most sections are scannable, but at least one section is a dense paragraph the reader must read in full, or genuinely parallel items are left as prose instead of a list, or unrelated remarks are split into their own headers when they could be grouped",
            "Every section is itself scannable: short paragraphs throughout (including inside sections that explain reasoning or trade-offs), a bullet or numbered list for any set of genuinely parallel items, and related points grouped under a shared heading rather than each given its own fragment; scanning headings, first sentences, and lists alone conveys everything important, anywhere in the document",
        ],
    ),
    "detail_separated": Score(
        instructions=(
            "Is detailed implementation/technical reference (specific code identifiers, "
            "file paths, endpoint shapes, step-by-step technical mechanics) kept separate "
            "from and below the summary, rather than interleaved with it?"
        ),
        criteria=[
            "Implementation detail is interleaved throughout, including in the opening summary",
            "Implementation detail is mostly separate, but some leaks into the summary or is not clearly demarcated",
            "Implementation detail is clearly separated into its own section(s), distinct from the summary",
        ],
    ),
}


def run_eval(case_glob, runs, plugin_root):
    out_path = Path(tempfile.mkstemp(suffix=".json")[1])
    cmd = [
        "claude", "plugin", "eval", str(plugin_root),
        "--case", case_glob,
        "--runs", str(runs),
        "--trust-plugin", "--no-publish",
        "--json", str(out_path),
    ]
    result = subprocess.run(cmd)
    if result.returncode not in (0, 1):
        # 1 means a case scored below --threshold, which is expected here:
        # the whole point is comparing a lower-scoring "without" arm.
        sys.exit(f"claude plugin eval failed (exit {result.returncode})")
    return json.loads(out_path.read_text())


def extract_texts(result):
    texts = {}
    for case in result["cases"]:
        for arm in ("with", "without"):
            for i, run in enumerate(case.get("arms", {}).get(arm, [])):
                text = next((g["evidence"] for g in run["graders"] if g.get("evidence")), None)
                if text is not None:
                    texts[f"{case['name']}__{arm}__{i}"] = text
    return texts


def score_texts(texts):
    scored = {}
    with TypeSafeClient() as client:
        for key, text in texts.items():
            response = client.system_one(state=text, questions=DIMENSIONS)
            scored[key] = {
                qid: {"score": ans.score, "confidence": ans.confidence}
                for qid, ans in response.answers.items()
            }
    return scored


def print_report(scored):
    cases = sorted({key.rsplit("__", 2)[0] for key in scored})
    for case in cases:
        print(f"=== {case} ===")
        runs_by_arm = {"with": [], "without": []}
        for key, dims in scored.items():
            name, arm, _ = key.rsplit("__", 2)
            if name == case:
                runs_by_arm[arm].append(dims)
        for arm in ("with", "without"):
            for dims in runs_by_arm[arm]:
                vals = ", ".join(f"{d}={v['score']:.2f}" for d, v in dims.items())
                print(f"  {arm:8s} {vals}")
        for dim in DIMENSIONS:
            def avg(arm):
                vals = [r[dim]["score"] for r in runs_by_arm[arm]]
                return sum(vals) / len(vals) if vals else float("nan")
            w, wo = avg("with"), avg("without")
            print(f"    delta {dim}: {w - wo:+.2f}")
        print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default="clean-mode-*", help="claude plugin eval --case glob")
    parser.add_argument("--runs", type=int, default=1, help="runs per arm per case")
    parser.add_argument("--from", dest="from_json", help="reuse an existing `claude plugin eval --json` result instead of running a new eval")
    parser.add_argument("--plugin-root", default=".", help="plugin directory passed to claude plugin eval")
    parser.add_argument("--out", help="write raw Jev scores as JSON to this path")
    args = parser.parse_args()

    result = json.loads(Path(args.from_json).read_text()) if args.from_json else run_eval(args.case, args.runs, args.plugin_root)

    texts = extract_texts(result)
    if not texts:
        sys.exit("no last_message text found in eval result")

    scored = score_texts(texts)
    print_report(scored)

    if args.out:
        Path(args.out).write_text(json.dumps(scored, indent=2))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
