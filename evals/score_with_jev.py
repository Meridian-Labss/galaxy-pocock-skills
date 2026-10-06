#!/usr/bin/env python3
"""Score clean-mode with/without outputs on TypeSafe Jev dimensions.

    pip install typesafe-sdk
    export TYPESAFE_API_KEY=...
    python3 evals/score_with_jev.py

Runs `claude plugin eval` for the given case glob (default: every clean-mode
case), then scores each captured with/without output on dimensions taken
from clean-mode's own general principles: whether the opening leads with the
core information rather than the mechanism behind it, whether it scans (short
paragraphs, lists for parallel items, proportionate headings), whether
implementation detail is kept separate from the summary, whether it's padded
with hedging or restatement, and whether every section earns its place. The
questions themselves (instructions plus ordered criteria levels) live in
dimensions.json next to this script - edit that file to change what gets
measured. The response text is read directly from each run's trace, not from
a grader - the cases carry no LLM graders, so this is the only scoring in
play; Jev is the sole judge. Use --from to re-score an
existing `claude plugin eval --json` result instead of running a new eval.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import jev_core
except ImportError:
    sys.exit("typesafe-sdk is not installed. Run: pip install typesafe-sdk")

# The questions live in dimensions.json next to this script and are loaded by
# jev_core, which the clean-mode CI check shares, so both ask Jev identical
# questions. Scannability isn't one snap judgment: it depends on independent
# factors, so each gets its own atomic question per Jev's guidance, combined
# by jev_core.score_text. The composite is the MEAN of its factors: a min()
# was tried first and collapsed the composite to section_scannability alone
# (uniformly the lowest factor for both arms), masking the other factors.
#
# Some questions need the source material the document was written from, which
# means a second Jev call against a different state. They are kept as separate
# calls on purpose: the sources are deliberately unedited prose, and a judge
# that has just read one anchors on it when scoring the document's register.
try:
    CONFIG = jev_core.load_config()
except jev_core.ConfigError as e:
    sys.exit(str(e))
COMPOSITES = CONFIG.composites
REPORT_DIMENSIONS = CONFIG.report_dimensions

# A Jev score is a position on the dimension's own criteria ladder, so its
# range is set by how many levels that dimension defines: 0-2 for a 3-level
# question, 0-4 for a 5-level one. Raw scores stay on their native ladder
# everywhere (--out keeps them, so a score still maps onto its criterion
# text); the report divides by the dimension's top level and prints a 0-1
# fraction, so columns built from different ladders are comparable and a
# delta between two of them carries no unit to misread. A composite is
# already 0-1, so its top level is 1.
DIMENSION_TOP = {name: CONFIG.top(name) for name in [*CONFIG.dimensions, *CONFIG.composites]}


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


def load_sources(plugin_root="."):
    """The prompt each case was generated from, keyed by case name.

    A with_source question compares the document against this. The design
    case's code fixture is deliberately not included: that case's prompt says
    to write for a reader who will not open the code, so a fact available only
    in the fixture is an addition, not a retention.
    """
    sources = {}
    for case_dir in sorted((Path(plugin_root) / "evals").glob("*/")):
        prompt_md, case_yaml = case_dir / "prompt.md", case_dir / "case.yaml"
        if prompt_md.exists():
            parts = prompt_md.read_text().split("---", 2)
            sources[case_dir.name] = parts[2].strip() if len(parts) > 2 else prompt_md.read_text()
        elif case_yaml.exists():
            import yaml
            loaded = yaml.safe_load(case_yaml.read_text()) or {}
            prompt = (loaded.get("execution") or {}).get("prompt")
            if prompt:
                sources[case_dir.name] = prompt.strip()
    return sources


def texts_from_report(report_path):
    """Pull the captured outputs back out of a previous run's report.md.

    Re-scoring these costs one Jev call per output and no eval runs at all, so
    a dimension change can be measured against outputs that already exist
    rather than against freshly generated ones.
    """
    text = Path(report_path).read_text()
    bounds = [(m.group(1), m.start()) for m in re.finditer(r"^## (clean-mode-[\w-]+)$", text, re.M)]
    texts = {}
    for i, (case, start) in enumerate(bounds):
        block = text[start:bounds[i + 1][1] if i + 1 < len(bounds) else len(text)]
        for arm in ("with", "without"):
            found = re.search(rf"<details><summary>{arm} outputs.*?</summary>\n(.*?)\n</details>", block, re.S)
            if not found:
                continue
            for j, part in enumerate(re.split(r"^\*\*Run \d+\*\*$", found.group(1), flags=re.M)[1:]):
                body = part.strip()
                if not (body.startswith("```markdown") and body.endswith("```")):
                    sys.exit(f"could not parse {case} {arm} run {j + 1} out of {report_path}")
                texts[f"{case}__{arm}__{j}"] = body[len("```markdown"):-3].strip("\n")
    return texts


def cleanup_kept_dirs(kept_dirs):
    for d in kept_dirs:
        if not d.exists():
            continue
        subprocess.run(["chmod", "-R", "u+rwx", str(d)], check=False)
        shutil.rmtree(d, ignore_errors=True)


def score_texts(texts, sources=None):
    sources = sources or {}
    skipped = set()
    scored = {}
    with jev_core.make_client() as client:
        for key, text in texts.items():
            case = key.rsplit("__", 2)[0]
            if case not in sources:
                skipped.add(case)
            scored[key] = jev_core.score_text(client, CONFIG, text, source=sources.get(case))
    for case in sorted(skipped):
        print(f"warning: no source found for {case}; its with_source dimensions were not scored",
              file=sys.stderr)
    return scored


def mean_length(texts, case, arm):
    lengths = [len(v) for k, v in texts.items() if k.startswith(f"{case}__{arm}__")]
    return sum(lengths) / len(lengths) if lengths else float("nan")


def length_change(texts, case):
    """Percent change in mean output length, with vs without. Negative is shorter."""
    w, wo = mean_length(texts, case, "with"), mean_length(texts, case, "without")
    if wo != wo or w != w or not wo:  # nan guard
        return float("nan")
    return (w - wo) / wo * 100


def length_line(texts, case):
    w, wo = mean_length(texts, case, "with"), mean_length(texts, case, "without")
    change = length_change(texts, case)
    if change != change:
        return None
    return f"Mean output length: with {w:,.0f} characters, without {wo:,.0f} ({change:+.0f}%)."


def group_by_case(scored):
    """{case_name: {"with": [dims, ...], "without": [dims, ...]}}"""
    grouped = {}
    for key, dims in scored.items():
        name, arm, _ = key.rsplit("__", 2)
        grouped.setdefault(name, {"with": [], "without": []})[arm].append(dims)
    return grouped


def average(runs_by_arm, arm, dim):
    """Mean score for an arm, as a 0-1 fraction of the dimension's top level.

    A dimension can be missing from a run: a with_source question is skipped
    when its case has no source. Those runs drop out of the mean rather than
    raising, and a dimension missing from every run reports nan.
    """
    vals = [r[dim]["score"] for r in runs_by_arm[arm] if dim in r]
    if not vals:
        return float("nan")
    return (sum(vals) / len(vals)) / DIMENSION_TOP[dim]


def normalised(score, dim):
    return score / DIMENSION_TOP[dim]


def overall(runs_by_arm, arm):
    """Unweighted mean of the report dimensions, all already on the same 0-1 scale.

    Equal weight is a choice, not a measurement: it says a point of brevity
    counts the same as a point of plain language. scannability enters as one
    dimension, so its three factors share a sixth of the total between them.
    """
    vals = [average(runs_by_arm, arm, d) for d in REPORT_DIMENSIONS]
    vals = [v for v in vals if v == v]  # a dimension with no runs scores nan
    return sum(vals) / len(vals) if vals else float("nan")


def print_report(scored, texts=None):
    grouped = group_by_case(scored)
    for case in sorted(grouped):
        print(f"=== {case} ===")
        runs_by_arm = grouped[case]
        for arm in ("with", "without"):
            for dims in runs_by_arm[arm]:
                vals = ", ".join(f"{d}={normalised(dims[d]['score'], d):.2f}" for d in REPORT_DIMENSIONS)
                print(f"  {arm:8s} {vals}")
        for dim in REPORT_DIMENSIONS:
            w, wo = average(runs_by_arm, "with", dim), average(runs_by_arm, "without", dim)
            print(f"    delta {dim}: {w - wo:+.2f}")
            for factor in COMPOSITES.get(dim, ()):
                fw, fwo = average(runs_by_arm, "with", factor), average(runs_by_arm, "without", factor)
                print(f"      . {factor}: {fw - fwo:+.2f} (with {fw:.2f}, without {fwo:.2f})")
        ow, owo = overall(runs_by_arm, "with"), overall(runs_by_arm, "without")
        print(f"    OVERALL: with {ow:.2f}, without {owo:.2f}, delta {ow - owo:+.2f}")
        if texts and (line := length_line(texts, case)):
            print(f"    {line}")
        print()


def write_markdown_report(scored, texts, plugin_root, case_glob, out_dir=None):
    grouped = group_by_case(scored)
    runs = max((len(arms["with"]) for arms in grouped.values()), default=0)
    generated_at = datetime.now(timezone.utc)
    out_dir = Path(out_dir) if out_dir else Path(plugin_root) / "evals" / "results" / (generated_at.strftime("%Y-%m-%dT%H-%M-%S") + "-jev")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"

    lines = [
        "# Clean-mode Jev scoring report",
        "",
        f"Generated {generated_at.strftime('%Y-%m-%dT%H:%M:%SZ')} · case filter `{case_glob}` · {runs} run(s) per arm.",
        "",
        f"Dimensions: {', '.join(REPORT_DIMENSIONS)}.",
        "",
        "Each score is a 0-1 fraction of its dimension's top criteria level, averaged over the arm's runs. Delta is the plain difference between the two.",
        "",
    ]
    lines += ["## Overall", "", "| Case | With | Without | Delta | Length |", "|---|---|---|---|---|"]
    changes = []
    for case in sorted(grouped):
        ow, owo = overall(grouped[case], "with"), overall(grouped[case], "without")
        change = length_change(texts, case)
        if change == change:
            changes.append(change)
        lines.append(f"| {case} | {ow:.2f} | {owo:.2f} | {ow - owo:+.2f} | "
                     f"{f'{change:+.0f}%' if change == change else 'n/a'} |")
    every = {arm: [overall(grouped[c], arm) for c in grouped] for arm in ("with", "without")}
    mean = {arm: sum(v for v in every[arm] if v == v) / max(sum(1 for v in every[arm] if v == v), 1)
            for arm in ("with", "without")}
    every_change = f"**{sum(changes) / len(changes):+.0f}%**" if changes else "n/a"
    lines.append(f"| **all cases** | **{mean['with']:.2f}** | **{mean['without']:.2f}** | "
                 f"**{mean['with'] - mean['without']:+.2f}** | {every_change} |")
    lines += ["", "Overall is the unweighted mean of the dimensions below it. Length is the change in "
              "mean output length with the skill against without; negative is shorter, and it is "
              "reported alongside rather than folded into the score.", ""]

    for case in sorted(grouped):
        runs_by_arm = grouped[case]
        lines.append(f"## {case}")
        lines.append("")
        lines.append("| Dimension | With | Without | Delta |")
        lines.append("|---|---|---|---|")
        for dim in REPORT_DIMENSIONS:
            w, wo = average(runs_by_arm, "with", dim), average(runs_by_arm, "without", dim)
            lines.append(f"| {dim} | {w:.2f} | {wo:.2f} | {w - wo:+.2f} |")
            for factor in COMPOSITES.get(dim, ()):
                fw, fwo = average(runs_by_arm, "with", factor), average(runs_by_arm, "without", factor)
                lines.append(f"| &nbsp;&nbsp;· {factor} | {fw:.2f} | {fwo:.2f} | {fw - fwo:+.2f} |")
        ow, owo = overall(runs_by_arm, "with"), overall(runs_by_arm, "without")
        lines.append(f"| **overall** | **{ow:.2f}** | **{owo:.2f}** | **{ow - owo:+.2f}** |")
        lines.append("")
        if line := length_line(texts, case):
            lines.append(line)
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
    (out_dir / "scores.json").write_text(json.dumps(scored, indent=2, sort_keys=True))
    return report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default="clean-mode-*", help="claude plugin eval --case glob")
    parser.add_argument("--runs", type=int, default=1, help="runs per arm per case")
    parser.add_argument("--from", dest="from_json", help="reuse an existing `claude plugin eval --json` result instead of running a new eval")
    parser.add_argument("--from-report", help="re-score the outputs captured in a previous run's report.md, with no eval run at all")
    parser.add_argument("--plugin-root", default=".", help="plugin directory passed to claude plugin eval")
    parser.add_argument("--out", help="write raw Jev scores as JSON to this path")
    args = parser.parse_args()

    if args.from_report:
        texts = texts_from_report(args.from_report)
    else:
        result = json.loads(Path(args.from_json).read_text()) if args.from_json else run_eval(args.case, args.runs, args.plugin_root)
        texts, kept_dirs = extract_texts(result)
        cleanup_kept_dirs(kept_dirs)
    if not texts:
        sys.exit("no last_message text found in eval result")

    scored = score_texts(texts, load_sources(args.plugin_root))
    print_report(scored, texts)

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
