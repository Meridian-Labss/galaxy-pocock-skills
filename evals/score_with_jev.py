#!/usr/bin/env python3
"""Score clean-mode with/without outputs on TypeSafe Jev dimensions.

    pip install typesafe-sdk
    export TYPESAFE_API_KEY=...
    python3 evals/score_with_jev.py

Runs `claude plugin eval` for the given case glob (default: every clean-mode
case), then scores each captured with/without output on dimensions taken
from clean-mode's own general principles: whether the opening states the
outcome before implementation detail, whether it scans (short paragraphs,
lists for parallel items, proportionate headings), whether implementation
detail is kept separate from the summary, and whether it's padded with
hedging or restatement. The questions themselves (instructions plus ordered
criteria levels) live in dimensions.json next to this script - edit that
file to change what gets measured. The response text is read directly from each run's
trace, not from a grader - the cases carry no LLM graders, so this is the
only scoring in play; Jev is the sole judge. Use --from to re-score an
existing `claude plugin eval --json` result instead of running a new eval.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from typesafe_sdk import Score, TypeSafeClient
except ImportError:
    sys.exit("typesafe-sdk is not installed. Run: pip install typesafe-sdk")

# The questions live in dimensions.json next to this script: one entry per
# Jev Score question (instructions + ordered worst-to-best criteria levels),
# plus which factors compose "scannability" and which dimensions the report
# shows. Scannability isn't one snap judgment - it depends on independent
# factors, so each gets its own atomic question per Jev's guidance, combined
# in code by score_texts(). The composite is the MEAN of its factors: a min()
# was tried first and collapsed the composite to section_scannability alone
# (uniformly the lowest factor for both arms), masking the other factors.
DIMENSIONS_FILE = Path(__file__).with_name("dimensions.json")
_config = json.loads(DIMENSIONS_FILE.read_text())

DIMENSIONS = {
    name: Score(instructions=d["instructions"], criteria=d["criteria"])
    for name, d in _config["dimensions"].items()
}
SCANNABILITY_FACTORS = tuple(_config["scannability_factors"])
REPORT_DIMENSIONS = list(_config["report_dimensions"])

# Dimensions may use different numbers of criteria levels, so a raw score of
# 2 means "top" on a 3-level scale but "middle" on a 5-level one. The
# composite normalises each factor by its own top level, then rescales to
# 0-2 so it reads like the other report dimensions.
DIMENSION_TOP = {name: len(d["criteria"]) - 1 for name, d in _config["dimensions"].items()}


def run_eval(case_glob, runs, plugin_root):
    out_path = Path(tempfile.mkstemp(suffix=".json")[1])
    cmd = [
        "claude", "plugin", "eval", str(plugin_root),
        "--case", case_glob,
        "--runs", str(runs),
        "--trust-plugin", "--no-publish", "--scaffold", "--keep-temp",
        "--json", str(out_path),
    ]
    try:
        result = subprocess.run(cmd)
    except KeyboardInterrupt:
        # claude plugin eval catches the same Ctrl-C and finishes up on its
        # own; give it a moment, then clean whatever sandboxes it kept for us.
        _cleanup_partial(out_path)
        sys.exit(130)
    if result.returncode not in (0, 1):
        # 1 means a case scored below --threshold, which is expected here:
        # the whole point is comparing a lower-scoring "without" arm.
        sys.exit(f"claude plugin eval failed (exit {result.returncode})")
    return json.loads(out_path.read_text())


def _cleanup_partial(out_path):
    """After an interrupt, sweep the kept sandboxes of any runs that finished."""
    try:
        partial = json.loads(out_path.read_text())
        _, kept_dirs = extract_texts(partial)
        cleanup_kept_dirs(kept_dirs)
        print("interrupted - cleaned up completed runs' sandboxes", file=sys.stderr)
    except (OSError, ValueError, KeyError):
        print(
            "interrupted - if the log shows kept /private/tmp/e-* directories, "
            "remove them by hand (chmod -R u+rwx then rm -rf)",
            file=sys.stderr,
        )


def last_assistant_text(trace_path):
    """Final assistant reply from a claude plugin eval trace.jsonl, independent
    of any grader - so cases need no LLM grader just to capture the response."""
    text = None
    for line in Path(trace_path).read_text().splitlines():
        event = json.loads(line)
        if event.get("type") != "assistant":
            continue
        blocks = event.get("message", {}).get("content", [])
        chunks = [b["text"] for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        if chunks:
            text = "\n".join(chunks)
    return text


def kept_dir_for(trace_path):
    # tracePath looks like /private/tmp/e-XXXXXX/out/trace.jsonl
    return Path(trace_path).parent.parent


def extract_texts(result):
    texts = {}
    kept_dirs = []
    for case in result["cases"]:
        for arm in ("with", "without"):
            for i, run in enumerate(case.get("arms", {}).get(arm, [])):
                trace_path = run.get("tracePath")
                text = None
                if trace_path and Path(trace_path).exists():
                    text = last_assistant_text(trace_path)
                    kept_dirs.append(kept_dir_for(trace_path))
                if text is None:
                    # Fall back to an LLM grader's captured evidence, for
                    # --from results produced before this script kept its
                    # own traces (or by a case that still has an llm grader).
                    text = next((g["evidence"] for g in run["graders"] if g.get("evidence")), None)
                if text is not None:
                    texts[f"{case['name']}__{arm}__{i}"] = text
    return texts, kept_dirs


def cleanup_kept_dirs(kept_dirs):
    for d in kept_dirs:
        if not d.exists():
            continue
        subprocess.run(["chmod", "-R", "u+rwx", str(d)], check=False)
        shutil.rmtree(d, ignore_errors=True)


def score_texts(texts):
    scored = {}
    with TypeSafeClient() as client:
        for key, text in texts.items():
            response = client.system_one(state=text, questions=DIMENSIONS)
            raw = {
                qid: {"score": ans.score, "confidence": ans.confidence}
                for qid, ans in response.answers.items()
            }
            normalised = [raw[f]["score"] / DIMENSION_TOP[f] for f in SCANNABILITY_FACTORS]
            factor_confidences = [raw[f]["confidence"] for f in SCANNABILITY_FACTORS]
            raw["scannability"] = {
                "score": 2 * sum(normalised) / len(normalised),
                "confidence": sum(factor_confidences) / len(factor_confidences),
            }
            scored[key] = raw
    return scored


def group_by_case(scored):
    """{case_name: {"with": [dims, ...], "without": [dims, ...]}}"""
    grouped = {}
    for key, dims in scored.items():
        name, arm, _ = key.rsplit("__", 2)
        grouped.setdefault(name, {"with": [], "without": []})[arm].append(dims)
    return grouped


def average(runs_by_arm, arm, dim):
    vals = [r[dim]["score"] for r in runs_by_arm[arm]]
    return sum(vals) / len(vals) if vals else float("nan")


def print_report(scored):
    grouped = group_by_case(scored)
    for case in sorted(grouped):
        print(f"=== {case} ===")
        runs_by_arm = grouped[case]
        for arm in ("with", "without"):
            for dims in runs_by_arm[arm]:
                vals = ", ".join(f"{d}={dims[d]['score']:.2f}" for d in REPORT_DIMENSIONS)
                print(f"  {arm:8s} {vals}")
        for dim in REPORT_DIMENSIONS:
            w, wo = average(runs_by_arm, "with", dim), average(runs_by_arm, "without", dim)
            print(f"    delta {dim}: {w - wo:+.2f}")
            if dim == "scannability":
                for factor in SCANNABILITY_FACTORS:
                    fw, fwo = average(runs_by_arm, "with", factor), average(runs_by_arm, "without", factor)
                    print(f"      . {factor}: {fw - fwo:+.2f} (with {fw:.2f}, without {fwo:.2f})")
        print()


def write_markdown_report(scored, texts, plugin_root, case_glob):
    grouped = group_by_case(scored)
    runs = max((len(arms["with"]) for arms in grouped.values()), default=0)
    generated_at = datetime.now(timezone.utc)
    out_dir = Path(plugin_root) / "evals" / "results" / (generated_at.strftime("%Y-%m-%dT%H-%M-%S") + "-jev")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"

    lines = [
        "# Clean-mode Jev scoring report",
        "",
        f"Generated {generated_at.strftime('%Y-%m-%dT%H:%M:%SZ')} · case filter `{case_glob}` · {runs} run(s) per arm.",
        "",
    ]
    for case in sorted(grouped):
        runs_by_arm = grouped[case]
        lines.append(f"## {case}")
        lines.append("")
        lines.append("| Dimension | With | Without | Delta |")
        lines.append("|---|---|---|---|")
        for dim in REPORT_DIMENSIONS:
            w, wo = average(runs_by_arm, "with", dim), average(runs_by_arm, "without", dim)
            lines.append(f"| {dim} | {w:.2f} | {wo:.2f} | {w - wo:+.2f} |")
            if dim == "scannability":
                for factor in SCANNABILITY_FACTORS:
                    fw, fwo = average(runs_by_arm, "with", factor), average(runs_by_arm, "without", factor)
                    lines.append(f"| &nbsp;&nbsp;· {factor} | {fw:.2f} | {fwo:.2f} | {fw - fwo:+.2f} |")
        lines.append("")
        for arm in ("with", "without"):
            arm_texts = [texts[k] for k in texts if k.startswith(f"{case}__{arm}__")]
            lines.append(f"<details><summary>{arm} outputs ({len(arm_texts)} run(s))</summary>")
            lines.append("")
            for i, text in enumerate(arm_texts, start=1):
                lines.append(f"**Run {i}**")
                lines.append("")
                lines.append("```markdown")
                lines.append(text)
                lines.append("```")
                lines.append("")
            lines.append("</details>")
            lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default="clean-mode-*", help="claude plugin eval --case glob")
    parser.add_argument("--runs", type=int, default=1, help="runs per arm per case")
    parser.add_argument("--from", dest="from_json", help="reuse an existing `claude plugin eval --json` result instead of running a new eval")
    parser.add_argument("--plugin-root", default=".", help="plugin directory passed to claude plugin eval")
    parser.add_argument("--out", help="write raw Jev scores as JSON to this path")
    args = parser.parse_args()

    result = json.loads(Path(args.from_json).read_text()) if args.from_json else run_eval(args.case, args.runs, args.plugin_root)

    texts, kept_dirs = extract_texts(result)
    cleanup_kept_dirs(kept_dirs)
    if not texts:
        sys.exit("no last_message text found in eval result")

    scored = score_texts(texts)
    print_report(scored)

    report_path = write_markdown_report(scored, texts, args.plugin_root, args.case)
    print(f"Jev report: {report_path}")

    if args.out:
        Path(args.out).write_text(json.dumps(scored, indent=2))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
