"""SWE-bench Verified → Harpyja eval fixtures + per-case-repo driver (spec 0010).

Prepares SWE-bench Verified for Harpyja's eval harness using the **standalone
localization protocol** (FastContext paper, arXiv:2606.14066): query the pre-fix
repo, score predicted citations against patch-derived target spans. It does NOT run
the standard SWE-bench harness — no Docker, no image builds, no test execution —
because Harpyja is a *locator*, not a patcher.

Pipeline (stages separated by network posture):

  convert    HF dataset  → swebench_verified.raw.jsonl   (portable: repo +
                                                           base_commit + patch-derived
                                                           spans; commit it; needs net)
  provision  raw.jsonl   → swebench_verified.resolved.jsonl (machine-local: `repo`
                                                           rewritten to a worktree;
                                                           gitignore it; may clone)
  run/sweep  resolved    → reports                        (fully offline; local stack)
  prune      remove materialized worktrees / free disk

Ground truth = pre-image (`--- a/…`) hunk locations parsed from the gold patch (the
repo state at base_commit, exactly what Harpyja scans). New-file hunks
(`--- /dev/null`) have no pre-image location; an instance whose targets are *all*
new files is flagged `new_file_only` and excluded from scoring (never a silent zero).

Schema seam: `_to_eval_case` emits the real `EvalCase` shape (case_id /
expected_spans list / classification). `base_commit` lives only in the raw record and
is read by `provision` directly; `load_dataset` ignores it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path

DEFAULT_TIMESTAMP = "1970-01-01T00:00:00Z"

# OQ2 sweep grid (provisional; centered on the spec-0008 incumbent 0.6 / 3).
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7)
DEFAULT_TOP_NS = (1, 3, 5)
# D-route guard: below this classifier-agreement rate the OQ2 recommendation is
# flagged low-confidence (deltas-only) rather than a calibration (review round-2).
AGREEMENT_FLOOR = 0.5

DATASET_CANDIDATES = (
    "princeton-nlp/SWE-bench_Verified",
    "SWE-bench/SWE-bench_Verified",
)
RAW_NAME = "swebench_verified.raw.jsonl"
RESOLVED_NAME = "swebench_verified.resolved.jsonl"
PROVENANCE_NAME = "swebench_verified.provenance.json"

# Standalone-localization protocol identity, recorded as a durable report field.
PROTOCOL = "standalone-localization"
# Context lines inflate each pre-image hunk range (~3 per side), biasing span-hit
# UPWARD; recorded, not hidden (D-protocol / review R5).
SPAN_INFLATION_TOLERANCE = 3
CONTAMINATION_CAVEAT = (
    "SWE-bench Verified is public; the local model may have seen these repos. "
    "Absolute accuracy is not a generalization claim — lead with relative sweep "
    "deltas and fast-vs-auto deltas."
)

# D-class: a single locatable file whose total pre-image span is at most this many
# lines is a "point" query; multi-file or larger ⇒ "broad". Provisional (re-tuned
# after the first sample run); the rule shape is frozen.
POINT_SPAN_MAX_LINES = 25


# --------------------------------------------------------------------------- #
# Patch → target spans (the oracle). Ground-truth quality lives here.
# --------------------------------------------------------------------------- #

_PRE = re.compile(r"^--- (?:a/)?(.+?)\s*$")
_POST = re.compile(r"^\+\+\+ (?:b/)?(.+?)\s*$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileTarget:
    path: str
    spans: list[tuple[int, int]] = field(default_factory=list)
    is_new_file: bool = False  # pre-image was /dev/null → no locatable position


def parse_patch(patch: str) -> list[FileTarget]:
    """Parse a unified diff into pre-image (file, line-range) targets.

    Single pass with correct ---/+++ pairing. Spans are pre-image line ranges.
    Pure-insertion hunks (pre-image length 0) anchor to a one-line span at the
    insertion point. New-file hunks (`--- /dev/null`) are flagged with no spans.
    Never raises across a set: an unparseable patch simply yields no targets.
    """
    targets: dict[str, FileTarget] = {}
    cur: str | None = None
    pre_path: str | None = None
    pre_devnull = False

    for line in patch.splitlines():
        mpre = _PRE.match(line)
        if mpre and not line.startswith("---- "):
            raw = mpre.group(1)
            pre_devnull = raw == "/dev/null"
            pre_path = None if pre_devnull else raw
            cur = None
            continue
        mpost = _POST.match(line)
        if mpost:
            raw = mpost.group(1)
            if raw == "/dev/null":
                cur = pre_path  # deletion: locatable at its pre-image path
            else:
                cur = raw
            if cur is not None and cur not in targets:
                targets[cur] = FileTarget(path=cur, is_new_file=pre_devnull)
            continue
        mh = _HUNK.match(line)
        if mh and cur is not None and cur in targets and not targets[cur].is_new_file:
            start = int(mh.group(1))
            length = int(mh.group(2)) if mh.group(2) is not None else 1
            end = start if length == 0 else start + length - 1
            targets[cur].spans.append((start, max(start, end)))

    return list(targets.values())


# --------------------------------------------------------------------------- #
# Classification + new-file handling (D-class / D-newfile)
# --------------------------------------------------------------------------- #

def _locatable(targets: list[FileTarget]) -> list[FileTarget]:
    return [t for t in targets if not t.is_new_file and t.spans]


def _total_span_lines(t: FileTarget) -> int:
    return sum(end - start + 1 for start, end in t.spans)


def classify_by_patch_shape(targets: list[FileTarget]) -> str:
    """D-class: single locatable file with a small total span ⇒ 'point', else 'broad'."""
    loc = _locatable(targets)
    if len(loc) == 1 and _total_span_lines(loc[0]) <= POINT_SPAN_MAX_LINES:
        return "point"
    return "broad"


def is_new_file_only(targets: list[FileTarget]) -> bool:
    """D-newfile: no locatable pre-image target (every target is an unlocatable new file)."""
    return len(_locatable(targets)) == 0


def partition_scorable(rows: list[dict]) -> tuple[list[dict], int]:
    """Split raw rows into the scorable population and the excluded new-file count.

    new_file_only rows have no pre-image span and are excluded from scoring (never
    scored as a silent zero); the excluded count is returned for the durable report.
    """
    scorable = [r for r in rows if not r.get("new_file_only")]
    return scorable, len(rows) - len(scorable)


# --------------------------------------------------------------------------- #
# Fixture record construction — THE schema reconciliation seam (review B2)
# --------------------------------------------------------------------------- #

def _to_eval_case(inst: dict, targets: list[FileTarget]) -> dict:
    """Map one SWE-bench instance → a record in the real `EvalCase` shape.

    `case_id` / `expected_spans` (list of {path, start_line, end_line}) /
    `classification` ∈ {point, broad} are the `EvalCase` fields. `base_commit` /
    `language` / `new_file_only` are extra raw keys: `provision` reads `base_commit`
    directly and `load_dataset` ignores them (they are not `EvalCase` fields).
    """
    expected_spans = [
        {"path": t.path, "start_line": s, "end_line": e}
        for t in targets
        if not t.is_new_file
        for (s, e) in t.spans
    ]
    return {
        "case_id": inst["instance_id"],
        "query": inst["problem_statement"],
        "repo": inst["repo"],            # "owner/name"; provision rewrites to a path
        "expected_spans": expected_spans,
        "classification": classify_by_patch_shape(targets),
        # --- extra raw-only keys (ignored by load_dataset) ---
        "base_commit": inst["base_commit"],
        "language": "python",            # SWE-bench Verified is Python-only
        "new_file_only": is_new_file_only(targets),
    }


# --------------------------------------------------------------------------- #
# Dataset loading
# --------------------------------------------------------------------------- #

def load_swebench_verified():
    try:
        from datasets import load_dataset as hf_load_dataset
    except ImportError:
        sys.exit("Missing dependency. Run: uv add datasets")

    last_err = None
    for name in DATASET_CANDIDATES:
        try:
            print(f"[convert] loading {name} (split=test) …", file=sys.stderr)
            return name, hf_load_dataset(name, split="test")
        except Exception as e:  # noqa: BLE001 — dataset id may have moved orgs
            last_err = e
            print(f"[convert]   {name} unavailable: {e}", file=sys.stderr)
    sys.exit(
        "Could not load SWE-bench Verified from known ids "
        f"{DATASET_CANDIDATES}. Check the current id on HuggingFace.\n"
        f"Last error: {last_err}"
    )


# --------------------------------------------------------------------------- #
# convert
# --------------------------------------------------------------------------- #

def cmd_convert(args: argparse.Namespace) -> None:
    dataset_id, ds = load_swebench_verified()
    rows = [dict(r) for r in ds]
    print(f"[convert] {len(rows)} instances", file=sys.stderr)

    cases, skipped = [], []
    for inst in rows:
        try:
            targets = parse_patch(inst["patch"])
        except Exception as e:  # noqa: BLE001 — a malformed patch must not abort the set
            skipped.append((inst["instance_id"], str(e)))
            continue
        if not targets:
            skipped.append((inst["instance_id"], "no parseable file targets"))
            continue
        cases.append(_to_eval_case(inst, targets))

    if args.sample:
        cases = _stratify(cases, n=args.sample, per_repo=args.per_repo, seed=args.seed)
        print(f"[convert] stratified sample → {len(cases)} cases", file=sys.stderr)

    cases.sort(key=lambda c: c["case_id"])  # deterministic output
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / RAW_NAME
    _write_jsonl(raw, cases)

    _, excluded = partition_scorable(cases)
    provenance = {
        "hf_dataset_id": dataset_id,
        "hf_split": "test",
        "hf_revision": getattr(ds, "_fingerprint", None),
        "raw_fixture_sha256": _sha256_file(raw),
        "sample_case_ids": [c["case_id"] for c in cases],
        "malformed_skipped_count": len(skipped),
        "new_file_only_excluded_count": excluded,
    }
    _write_json(out_dir / PROVENANCE_NAME, provenance)

    n_locatable = len(cases) - excluded
    print(
        f"[convert] wrote {len(cases)} cases → {raw}\n"
        f"[convert]   locatable: {n_locatable}  new-file-only (excluded): {excluded}  "
        f"patches skipped: {len(skipped)}",
        file=sys.stderr,
    )
    if skipped and args.verbose:
        for iid, why in skipped[:20]:
            print(f"[convert]   skip {iid}: {why}", file=sys.stderr)


def _stratify(cases: list[dict], n: int, per_repo: int | None, seed: int) -> list[dict]:
    """Spread the sample across repos so one big project can't dominate."""
    rng = random.Random(seed)
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        by_repo[c["repo"]].append(c)
    for v in by_repo.values():
        rng.shuffle(v)

    picked: list[dict] = []
    if per_repo:
        for v in by_repo.values():
            picked.extend(v[:per_repo])
    else:
        picked = [c for v in by_repo.values() for c in v]
    rng.shuffle(picked)
    return picked[:n]


# --------------------------------------------------------------------------- #
# provision — materialize each instance's repo at base_commit via git worktrees
# --------------------------------------------------------------------------- #

def cmd_provision(args: argparse.Namespace) -> None:
    fix_dir = Path(args.fixtures)
    raw = fix_dir / RAW_NAME
    if not raw.exists():
        sys.exit(f"{raw} not found — run `convert` first.")
    cases = _read_jsonl(raw)

    # Resolve to absolute: `_ensure_worktree` runs `git worktree add` with cwd=<clone>,
    # so a RELATIVE worktree path (e.g. the Makefile's --work-dir eval_work) would be
    # created UNDER the clone while the resolved fixture records `wt.resolve()` (relative
    # to the process cwd) — the two diverge and every recorded path 404s (spec 0015 B0).
    work = Path(args.work_dir).resolve()
    clones = work / "clones"
    trees = work / "worktrees"
    clones.mkdir(parents=True, exist_ok=True)
    trees.mkdir(parents=True, exist_ok=True)

    resolved, degraded = [], []
    for c in cases:
        owner_name = c["repo"]
        commit = c["base_commit"]  # read DIRECTLY from the raw dict (review B2)
        clone = clones / owner_name.replace("/", "__")
        wt = trees / c["case_id"]
        try:
            _ensure_clone(clone, owner_name)
            _ensure_worktree(clone, wt, commit)
            _wipe_harpyja_cache(wt)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf8", "replace")[:200]
            degraded.append((c["case_id"], e.cmd, err))
            continue
        rc = dict(c)
        rc["repo"] = str(wt.resolve())  # runner consumes a real local path
        resolved.append(rc)

    resolved.sort(key=lambda c: c["case_id"])
    out = fix_dir / RESOLVED_NAME
    _write_jsonl(out, resolved)
    print(
        f"[provision] resolved {len(resolved)}/{len(cases)} → {out}\n"
        f"[provision]   degraded (clone/checkout failed): {len(degraded)}",
        file=sys.stderr,
    )
    if degraded:
        for iid, cmd, err in degraded[:20]:
            print(f"[provision]   FAIL {iid}: {' '.join(cmd)} :: {err}", file=sys.stderr)
    print(
        "[provision] NOTE: swebench_verified.resolved.jsonl holds machine-local paths "
        "— gitignore it; commit only the .raw.jsonl.",
        file=sys.stderr,
    )


def _git(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _ensure_clone(clone: Path, owner_name: str) -> None:
    if (clone / ".git").exists():
        return
    url = f"https://github.com/{owner_name}.git"
    print(f"[provision] cloning {owner_name} …", file=sys.stderr)
    _git(["clone", "--quiet", url, str(clone)])


def _ensure_worktree(clone: Path, wt: Path, commit: str) -> None:
    if (wt / ".git").exists():
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=wt, check=True, capture_output=True
        ).stdout.decode().strip()
        if head.startswith(commit) or commit.startswith(head):
            return
        _git(["worktree", "remove", "--force", str(wt)], cwd=clone)
    have = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=clone, capture_output=True
    )
    if have.returncode != 0:
        _git(["fetch", "--quiet", "origin", commit], cwd=clone)
    _git(["worktree", "add", "--quiet", "--force", "--detach", str(wt), commit], cwd=clone)


def _wipe_harpyja_cache(wt: Path) -> None:
    cache = wt / ".harpyja"
    if cache.exists():
        shutil.rmtree(cache, ignore_errors=True)


# --------------------------------------------------------------------------- #
# prune
# --------------------------------------------------------------------------- #

def cmd_prune(args: argparse.Namespace) -> None:
    work = Path(args.work_dir)
    trees = work / "worktrees"
    clones = work / "clones"
    n = 0
    if trees.exists():
        for clone in (clones.iterdir() if clones.exists() else []):
            subprocess.run(["git", "worktree", "prune"], cwd=clone, capture_output=True)
        for wt in trees.iterdir():
            shutil.rmtree(wt, ignore_errors=True)
            n += 1
    print(f"[prune] removed {n} worktrees under {trees}", file=sys.stderr)
    if args.clones:
        shutil.rmtree(clones, ignore_errors=True)
        print(f"[prune] removed clone cache {clones}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# io helpers
# --------------------------------------------------------------------------- #

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)  # atomic


def _read_jsonl(path) -> list[dict]:
    with Path(path).open(encoding="utf8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf8")
    tmp.replace(path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# per-case-repo driver (AC5, AC6, AC7, AC8, AC11) — the multi-repo gap
# --------------------------------------------------------------------------- #

def _production_gate_ran(tiers_run, notes, mode: str) -> bool:
    """SUT-observed: did the production gate actually execute inside locate()?

    In `fast` the gate is informational (Wave-5), so it is not a production gate
    decision. In `auto` the gate runs after Scout (tier 1) unless it was skipped
    (honest-empty: `gate-skipped:scout-empty`). Kept distinct from the harness's
    Scout-probe `gate_triggered` field (review R9).
    """
    if mode == "fast":
        return False
    if 1 not in tuple(tiers_run):
        return False
    if isinstance(notes, str):
        notes_text = notes
    elif notes:
        notes_text = " ".join(str(n) for n in notes)
    else:
        notes_text = ""
    return "gate-skipped" not in notes_text


def _atomic_write_outside_repos(payload: dict, out_dir, repos, filename: str) -> Path:
    """Atomically write `payload` under `out_dir`, refusing inside ANY case repo.

    The single-repo `atomic_write_json` guard cannot express "outside *every* case
    worktree", so the multi-repo guard is enforced here, then the shared writer is
    called with a disjoint sentinel so its own guard cannot false-positive.
    """
    from harpyja.eval.report import _is_within, atomic_write_json

    out = Path(out_dir)
    for repo in repos:
        if _is_within(out, Path(repo)):
            raise ValueError(
                f"refusing to write eval artifacts inside a case repo: {repo}"
            )
    sentinel = out.resolve().parent / "__harpyja_not_a_repo__"
    return atomic_write_json(payload, out_dir=out, repo_path=sentinel, filename=filename)


def _write_report_multirepo(report: dict, out_dir, repos) -> Path:
    """Validate then write the pooled single-run report outside every case repo."""
    from harpyja.eval.report import validate_report

    validate_report(report)
    return _atomic_write_outside_repos(report, out_dir, repos, "report.json")


def run_swebench(
    cases,
    settings,
    eval_config,
    *,
    stack_factory,
    production_classifier=None,
    out_dir=None,
    write: bool = False,
    mode: str = "auto",
    provenance: dict | None = None,
    new_file_only_excluded_count: int = 0,
    malformed_skipped_count: int = 0,
    per_case_timeout: float | None = None,
    sample_cap: int | None = None,
    repo_revision: str = "swebench-verified",
    timestamp: str = DEFAULT_TIMESTAMP,
) -> dict:
    """Drive a SWE-bench case set, each case through its OWN repo + stack (AC6).

    Per case: capture the production `classify_query` label BEFORE installing the
    D-route override (codex's self-observation guard), inject a classifier that
    forces routing to the patch-shape label through `LocateStack.classifier`, drive
    `run_case`, then record both labels + the SUT-observed `production_gate_ran`.
    Outcomes pool into the unchanged `aggregate_outcomes`; the report carries the
    additive durable metadata. `per_case_timeout` / `sample_cap` bound the run.
    """
    from harpyja.eval.report import build_report
    from harpyja.eval.runner import aggregate_outcomes, compose_reliability_notes, run_case

    if production_classifier is None:
        from harpyja.orchestrator.classify import classify_query

        production_classifier = classify_query

    cases = list(cases)
    if sample_cap is not None:
        cases = cases[:sample_cap]

    runs = []
    prod_labels: list[tuple[str, str]] = []
    timed_out = 0
    executor = ThreadPoolExecutor(max_workers=1) if per_case_timeout else None
    try:
        for case in cases:
            prod_label = production_classifier(case.query)  # BEFORE the override
            base_stack = stack_factory(settings, case.repo)
            override = replace(
                base_stack,
                classifier=lambda *a, _c=case.classification, **k: _c,
            )

            def _drive(case=case, override=override):
                return run_case(
                    case, settings, eval_config,
                    repo_path=case.repo, stack=override, mode=mode,
                )

            if executor is not None:
                fut = executor.submit(_drive)
                try:
                    run = fut.result(timeout=per_case_timeout)
                except FutureTimeout:
                    timed_out += 1
                    continue
            else:
                run = _drive()

            run.event["production_gate_ran"] = _production_gate_ran(
                run.outcome.tiers_run, run.event.get("notes"), mode
            )
            run.event["patch_shape_label"] = case.classification
            run.event["production_classifier_label"] = prod_label
            runs.append(run)
            prod_labels.append((case.classification, prod_label))
    finally:
        if executor is not None:
            executor.shutdown(wait=False)

    aggregate = aggregate_outcomes(runs, eval_config)
    aggregate["classifier_agreement_rate"] = (
        sum(1 for shape, prod in prod_labels if shape == prod) / len(prod_labels)
        if prod_labels
        else None
    )

    seed_n = len(runs)
    indicative_only = seed_n < eval_config.n_floor
    # Spec 0011 — composable reliability notes (degrade-dominated + indicative-only)
    # so "12/12 scout-degraded" is impossible to miss at the report top.
    aggregate["reliability_notes"] = compose_reliability_notes(
        degraded_dominated=bool(aggregate["degraded_dominated"]),
        indicative_only=indicative_only,
    )
    run_metadata = {
        "repo_revision": repo_revision,
        "seed_n": seed_n,
        "n_floor": eval_config.n_floor,
        "indicative_only": indicative_only,
        "degraded_dominated_threshold": eval_config.degraded_dominated_threshold,
        "mode": mode,
        "k_runs": 1,
        "settings_snapshot": {
            "verify_method": settings.verify_method,
            "verify_threshold": settings.verify_threshold,
            "verify_top_n": settings.verify_top_n,
        },
        "timestamp": timestamp,
        "artifact_dir": str(out_dir) if out_dir is not None else None,
        # spec 0010 — additive durable metadata
        "protocol": PROTOCOL,
        "dataset_provenance": provenance,
        "span_inflation_tolerance": SPAN_INFLATION_TOLERANCE,
        "contamination_caveat": CONTAMINATION_CAVEAT,
        "new_file_only_excluded_count": new_file_only_excluded_count,
        "malformed_skipped_count": malformed_skipped_count,
        # extra tolerated key: budget skips (validate_report ignores unknown keys)
        "timed_out_count": timed_out,
    }

    report = build_report(run_metadata, [r.event for r in runs], aggregate)
    if write:
        if out_dir is None:
            raise ValueError("write=True requires out_dir")
        _write_report_multirepo(report, out_dir, [c.repo for c in cases])
    return report


def _mean_or_none(values) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def run_swebench_sweep(
    cases,
    base_settings,
    eval_config,
    *,
    stack_factory,
    thresholds,
    top_ns,
    production_classifier=None,
    out_dir=None,
    write: bool = False,
    provenance: dict | None = None,
    new_file_only_excluded_count: int = 0,
    malformed_skipped_count: int = 0,
    per_case_timeout: float | None = None,
    sample_cap: int | None = None,
    repo_revision: str = "swebench-verified",
    timestamp: str = DEFAULT_TIMESTAMP,
) -> dict:
    """OQ2 sweep over the multi-repo set: grid × K runs via `run_swebench`.

    Each grid point is built with `dataclasses.replace` (never mutation). The OQ2
    recommendation is **guarded by the classifier-agreement rate** (D-route): below
    `AGREEMENT_FLOOR` it is flagged low-confidence (deltas-only), not a calibration.
    """
    from harpyja.eval.config import aggregate_runs
    from harpyja.eval.recommend import SweepPoint, recommend_oq2
    from harpyja.eval.report import SCHEMA_VERSION

    wrapped_metrics = (
        "span_hit_rate_primary", "span_hit_rate_secondary", "escalation_rate",
        "tier01_resolve_rate", "gate_catch_rate", "gate_false_escalation",
    )
    sweep_points: list[dict] = []
    rank_inputs: list[SweepPoint] = []
    agreement_vals: list[float] = []

    for thr, top_n in product(thresholds, top_ns):
        point_settings = replace(base_settings, verify_threshold=thr, verify_top_n=top_n)
        per_run = [
            run_swebench(
                cases, point_settings, eval_config, stack_factory=stack_factory,
                production_classifier=production_classifier, mode="auto",
                sample_cap=sample_cap, per_case_timeout=per_case_timeout,
            )["aggregate"]
            for _ in range(eval_config.k_runs)
        ]
        wrapped = {
            m: aggregate_runs([agg[m] for agg in per_run if agg[m] is not None])
            for m in wrapped_metrics
        }
        catch_runs = [agg["gate_catch_rate"] for agg in per_run]
        false_runs = [agg["gate_false_escalation"] for agg in per_run]
        false_present = tuple(v for v in false_runs if v is not None)
        agreement_vals += [
            agg["classifier_agreement_rate"]
            for agg in per_run
            if agg["classifier_agreement_rate"] is not None
        ]

        sweep_points.append(
            {"verify_threshold": thr, "verify_top_n": top_n, "aggregate": wrapped}
        )
        rank_inputs.append(SweepPoint(
            verify_threshold=thr,
            verify_top_n=top_n,
            catch_rate_mean=_mean_or_none(catch_runs),
            false_escalation_mean=(_mean_or_none(false_runs) or 0.0),
            false_escalation_runs=false_present,
        ))

    # Spec 0019 (D2/AC9): gate-confound guard. When the base run uses the instruct
    # judge, take the BEST-achievable instruct false-escalation across the grid (the
    # minimum over points that actually measured it) as the G2 signal: if even the
    # best threshold rejects correct citations above the ceiling, the judge — not the
    # threshold — is the problem, so recommend_oq2 emits `gate-confounded` rather than
    # calibrating over it. A scout-judge baseline run (or a grid with no measured
    # point) passes None and defers to the clean recommender.
    measured_fe = None
    if base_settings.verify_method == "instruct_model":
        fe_means = [p.false_escalation_mean for p in rank_inputs if p.false_escalation_runs]
        measured_fe = min(fe_means) if fe_means else None
    rec = recommend_oq2(rank_inputs, measured_fe, eval_config)
    agreement_rate = _mean_or_none(agreement_vals)
    low_confidence = agreement_rate is None or agreement_rate < AGREEMENT_FLOOR

    seed_n = len(cases) if sample_cap is None else min(len(cases), sample_cap)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_metadata": {
            "repo_revision": repo_revision,
            "seed_n": seed_n,
            "n_floor": eval_config.n_floor,
            "indicative_only": seed_n < eval_config.n_floor,
            "mode": "sweep-auto",
            "k_runs": eval_config.k_runs,
            "settings_snapshot": {
                "verify_method": base_settings.verify_method,
                "verify_threshold": base_settings.verify_threshold,
                "verify_top_n": base_settings.verify_top_n,
            },
            "timestamp": timestamp,
            "artifact_dir": str(out_dir) if out_dir is not None else None,
            "protocol": PROTOCOL,
            "dataset_provenance": provenance,
            "span_inflation_tolerance": SPAN_INFLATION_TOLERANCE,
            "contamination_caveat": CONTAMINATION_CAVEAT,
            "new_file_only_excluded_count": new_file_only_excluded_count,
            "malformed_skipped_count": malformed_skipped_count,
            "classifier_agreement_rate": agreement_rate,
            # spec 0019 — the eval-only gate-confound ceiling in effect.
            "gate_false_escalation_ceiling": eval_config.gate_false_escalation_ceiling,
        },
        "sweep": sweep_points,
        "recommendation": {
            "verify_threshold": rec.verify_threshold,
            "verify_top_n": rec.verify_top_n,
            "catch_rate_bar": rec.catch_rate_bar,
            "advantage_exceeds_variance": rec.advantage_exceeds_variance,
            "incumbent_validated": rec.incumbent_validated,
            "rationale": rec.rationale,
            # spec 0019 — OQ2 outcome: `recommended` or the `gate-confounded` typed
            # null (carrying the measured instruct false-escalation), never a forced pick.
            "outcome": rec.outcome,
            "gate_false_escalation_measured": rec.gate_false_escalation_measured,
            # D-route agreement guard (review round-2)
            "classifier_agreement_rate": agreement_rate,
            "agreement_floor": AGREEMENT_FLOOR,
            "oq2_low_confidence": low_confidence,
            "oq2_basis": "deltas-only" if low_confidence else "calibration",
        },
    }
    if write:
        if out_dir is None:
            raise ValueError("write=True requires out_dir")
        _atomic_write_outside_repos(report, out_dir, [c.repo for c in cases], "sweep.json")
    return report


# --------------------------------------------------------------------------- #
# run / sweep (offline) — load the resolved fixture, drive the live stack
# --------------------------------------------------------------------------- #

def _eval_case_from_row(row: dict):
    from harpyja.eval.dataset import EvalCase, ExpectedSpan

    spans = tuple(
        ExpectedSpan(s["path"], s["start_line"], s["end_line"])
        for s in row["expected_spans"]
    )
    return EvalCase(row["case_id"], row["query"], row["repo"], spans, row["classification"])


def _load_resolved(fixtures_dir):
    """Load the resolved fixture into scorable EvalCases + provenance + counts.

    new_file_only rows are excluded here (their empty span list would also trip the
    strict loader); the excluded count is surfaced for the report.
    """
    fix = Path(fixtures_dir)
    resolved = fix / RESOLVED_NAME
    if not resolved.exists():
        sys.exit(
            f"{resolved} not found — run `make swebench-provision` "
            f"(python -m harpyja.eval.swebench_eval provision) first."
        )
    rows = _read_jsonl(resolved)
    scorable, excluded = partition_scorable(rows)
    prov_path = fix / PROVENANCE_NAME
    provenance = json.loads(prov_path.read_text(encoding="utf8")) if prov_path.exists() else None
    malformed = (provenance or {}).get("malformed_skipped_count", 0)
    cases = [_eval_case_from_row(r) for r in scorable]
    return cases, provenance, excluded, malformed


def _live_stack_factory():
    from harpyja.eval.runner import build_live_stack

    return lambda settings, repo: build_live_stack(settings, repo)


def _settings_from_args(args: argparse.Namespace):
    """Build `Settings` from CLI flags via `dataclasses.replace` (never mutation).

    Spec 0016: `run`/`sweep` expose `--scout-model` (Scout/gate model) and the
    canonical `--deep-model` (Deep model), with `--lm-model` retained as a deprecated
    alias. The Deep flags live on distinct argparse dests and are reconciled here so
    `--deep-model` wins regardless of CLI order (canonical `or` alias) — not via
    argparse positional last-wins. The default Deep model is now a served Ollama tag;
    a llama.cpp operator names their model explicitly through these flags.
    """
    from harpyja.config.settings import Settings

    overrides = {}
    if getattr(args, "scout_model", None):
        overrides["scout_model"] = args.scout_model
    # Canonical `--deep-model` beats the deprecated `--lm-model` alias, order-independent.
    deep = getattr(args, "deep_model", None) or getattr(args, "lm_model", None)
    if deep:
        overrides["lm_model"] = deep
    if getattr(args, "lm_api_base", None):
        overrides["lm_api_base"] = args.lm_api_base
    if getattr(args, "deep_max_subqueries", None) is not None:
        overrides["deep_max_subqueries"] = args.deep_max_subqueries
    base = Settings()
    return replace(base, **overrides) if overrides else base


class PreflightError(Exception):
    """A required served model is not pulled on the run host (spec 0019, AC1)."""


def _required_model_tags(settings) -> list[str]:
    """The deduped set of served model tags a `mode=auto` run needs.

    `scout_model` backs Tier-1 Scout (and, when `verify_method="scout_model"`, the
    gate finder); `lm_model` backs BOTH Deep (Tier-2) AND the default instruct-model
    gate judge, and is what `--deep-model` resolves to — so the "three models" of the
    spec (scout / judge / deep) dedupe to the distinct TAGS actually required.
    """
    return sorted({settings.scout_model, settings.lm_model})


def preflight_models_present(settings, tags_payload, *, resolver=None) -> list[str]:
    """Assert every required served model tag is PULLED, air-gap enforced first.

    Spec 0019 (AC1/AC2/D4): this is B1's 404 surfaced at SETUP, not mid-run. Two
    honesty constraints: (a) the presence probe runs behind `gateway.assert_local`
    on the resolved loopback endpoint FIRST, so preflight adds NO second outbound
    path (the air-gap stays enforced in the one place); (b) it verifies models are
    **pulled**, NOT co-resident-loadable — OOM under `mode=auto` remains a residual
    mid-run risk that the cheap G1 smoke catches. `tags_payload` is the already-fetched
    `/api/tags` body (injected in unit tests; fetched live by `cmd_preflight`).
    Returns the deduped required tag set on success; raises `PreflightError` naming
    the first absent tag otherwise.
    """
    from harpyja.gateway.gateway import assert_local

    assert_local(settings.lm_api_base, resolver=resolver)
    served = {m.get("name") for m in (tags_payload or {}).get("models", [])}
    required = _required_model_tags(settings)
    missing = [t for t in required if t not in served]
    if missing:
        raise PreflightError(
            f"preflight: required model(s) not pulled on the run host: {missing} "
            f"(served: {sorted(served)}); pull them before provisioning. NOTE: this "
            "verifies models are PULLED, not co-resident-loadable — OOM under "
            "mode=auto remains a mid-run risk, caught cheaply by the G1 smoke."
        )
    return required


def cmd_preflight(args: argparse.Namespace) -> None:
    """Fetch `/api/tags` behind `assert_local` and assert the required tags are pulled."""
    import json as _json
    import urllib.request
    from urllib.parse import urlsplit

    from harpyja.gateway.gateway import assert_local

    settings = _settings_from_args(args)
    # Air-gap FIRST — the /api/tags read below is the ONLY outbound call and is
    # loopback-gated exactly like the model calls it is preflighting.
    assert_local(settings.lm_api_base)
    parts = urlsplit(settings.lm_api_base)
    host = parts.hostname or "localhost"
    port = parts.port or 11434
    tags_url = f"{parts.scheme or 'http'}://{host}:{port}/api/tags"
    with urllib.request.urlopen(tags_url, timeout=5.0) as resp:  # noqa: S310 (loopback)
        payload = _json.loads(resp.read())
    verified = preflight_models_present(settings, payload)
    print(f"[preflight] models pulled: {verified}", file=sys.stderr)


def cmd_oq2(args: argparse.Namespace) -> None:
    """Spec 0020 — run the OQ2 operator protocol and write a `0020/1` gate-ledger."""
    from harpyja.eval.config import EvalConfig
    from harpyja.eval.oq2_live import run_oq2_operator

    result = run_oq2_operator(
        args.fixtures, _settings_from_args(args), EvalConfig(),
        out_dir=args.out_dir,
        thresholds=args.thresholds, top_ns=args.top_ns,
        per_case_timeout=args.per_case_timeout, write=True,
    )
    print(
        f"[oq2] disposition={result.disposition} outcome={result.outcome} "
        f"gates={[g.gate for g in result.gates]} → {args.out_dir}/gate_ledger.json",
        file=sys.stderr,
    )


def cmd_run(args: argparse.Namespace) -> None:
    from harpyja.eval.config import EvalConfig

    cases, provenance, excluded, malformed = _load_resolved(args.fixtures)
    report = run_swebench(
        cases, _settings_from_args(args), EvalConfig(), stack_factory=_live_stack_factory(),
        out_dir=args.out_dir, write=True, mode=args.mode, provenance=provenance,
        new_file_only_excluded_count=excluded, malformed_skipped_count=malformed,
        sample_cap=args.sample_cap, per_case_timeout=args.per_case_timeout,
        repo_revision="swebench-verified",
    )
    agg = report["aggregate"]
    print(
        f"[run] mode={args.mode} cases={report['run_metadata']['seed_n']} "
        f"span_hit_primary={agg['span_hit_rate_primary']:.3f} "
        f"escalation={agg['escalation_rate']:.3f} "
        f"agreement={agg['classifier_agreement_rate']} → {args.out_dir}/report.json",
        file=sys.stderr,
    )


def cmd_sweep(args: argparse.Namespace) -> None:
    from harpyja.eval.config import EvalConfig

    cases, provenance, excluded, malformed = _load_resolved(args.fixtures)
    report = run_swebench_sweep(
        cases, _settings_from_args(args), EvalConfig(), stack_factory=_live_stack_factory(),
        thresholds=tuple(args.thresholds) if args.thresholds else DEFAULT_THRESHOLDS,
        top_ns=tuple(args.top_ns) if args.top_ns else DEFAULT_TOP_NS,
        out_dir=args.out_dir, write=True, provenance=provenance,
        new_file_only_excluded_count=excluded, malformed_skipped_count=malformed,
        sample_cap=args.sample_cap, per_case_timeout=args.per_case_timeout,
    )
    r = report["recommendation"]
    print(
        f"[sweep] recommend (threshold={r['verify_threshold']}, top_n={r['verify_top_n']}) "
        f"basis={r['oq2_basis']} agreement={r['classifier_agreement_rate']} "
        f"indicative_only={report['run_metadata']['indicative_only']} → "
        f"{args.out_dir}/sweep.json",
        file=sys.stderr,
    )


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="swebench_eval", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="HF dataset → raw fixture (+ optional sample)")
    c.add_argument("--out-dir", default="harpyja/eval/fixtures")
    c.add_argument("--sample", type=int, default=0, help="cap to N stratified instances")
    c.add_argument("--per-repo", type=int, default=None, help="max instances per repo")
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--verbose", action="store_true")
    c.set_defaults(func=cmd_convert)

    v = sub.add_parser("provision", help="raw fixture → resolved fixture (git worktrees)")
    v.add_argument("--fixtures", default="harpyja/eval/fixtures")
    v.add_argument("--work-dir", default="eval_work")
    v.set_defaults(func=cmd_provision)

    pr = sub.add_parser("prune", help="remove materialized worktrees")
    pr.add_argument("--work-dir", default="eval_work")
    pr.add_argument("--clones", action="store_true", help="also delete the clone cache")
    pr.set_defaults(func=cmd_prune)

    def _add_model_flags(sp):
        # Spec 0016: `--scout-model` overrides the Scout/gate model (fixes B1 — the
        # served-model escape hatch). `--deep-model` is the canonical Deep override;
        # `--lm-model` is kept as a DEPRECATED alias (distinct dest so the canonical
        # flag wins regardless of CLI order — reconciled in `_settings_from_args`).
        sp.add_argument("--scout-model", default=None, help="Scout/gate model (served tag)")
        sp.add_argument("--deep-model", default=None, help="Deep model (e.g. qwen2.5-coder:3b)")
        sp.add_argument("--lm-model", default=None, help="[deprecated] alias of --deep-model")
        sp.add_argument("--lm-api-base", default=None, help="local OpenAI-compatible endpoint")
        sp.add_argument("--deep-max-subqueries", type=int, default=None)

    r = sub.add_parser("run", help="drive the resolved fixture through locate() (offline)")
    r.add_argument("--fixtures", default="harpyja/eval/fixtures")
    r.add_argument("--out-dir", default="eval_work/reports")
    r.add_argument("--mode", default="auto", choices=["auto", "fast"])
    r.add_argument("--sample-cap", type=int, default=None)
    r.add_argument("--per-case-timeout", type=float, default=None)
    _add_model_flags(r)
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("sweep", help="OQ2 threshold×top_n sweep over the resolved fixture")
    s.add_argument("--fixtures", default="harpyja/eval/fixtures")
    s.add_argument("--out-dir", default="eval_work/reports")
    s.add_argument("--thresholds", type=float, nargs="*", default=None)
    s.add_argument("--top-ns", type=int, nargs="*", default=None)
    s.add_argument("--sample-cap", type=int, default=None)
    s.add_argument("--per-case-timeout", type=float, default=None)
    _add_model_flags(s)
    s.set_defaults(func=cmd_sweep)

    # spec 0019 — doctor-style setup guard: assert the served models are pulled
    # (behind assert_local) BEFORE provisioning, so B1's 404 fails loudly at setup.
    pf = sub.add_parser("preflight", help="assert required served models are pulled")
    _add_model_flags(pf)
    pf.set_defaults(func=cmd_preflight)

    # spec 0020 — the OQ2 operator protocol: G0 preflight → G1 smoke → G2 gate-quality
    # → G3 sweep, stop-and-report, emitting a 0020/1 gate-ledger with one typed outcome.
    oq = sub.add_parser("oq2", help="run the OQ2 operator protocol (G0→G1→G2→G3)")
    oq.add_argument("--fixtures", default="harpyja/eval/fixtures")
    oq.add_argument("--out-dir", default="eval_work/reports")
    oq.add_argument("--thresholds", type=float, nargs="*", default=None)
    oq.add_argument("--top-ns", type=int, nargs="*", default=None)
    oq.add_argument("--per-case-timeout", type=float, default=None)
    _add_model_flags(oq)
    oq.set_defaults(func=cmd_oq2)

    return p


def main(argv: list[str] | None = None) -> None:
    p = _build_parser()
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
