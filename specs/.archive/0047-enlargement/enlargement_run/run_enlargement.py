#!/usr/bin/env python3
"""Spec 0047 — operator driver: audited convert → blind authoring → tagging → power
re-check, end-to-end and RESUMABLE. Runs ON THE DEV HOST (needs the HF `datasets`
fetch + the operator's Claude/Codex CLIs). The reusable, unit-tested pipeline lives in
`harpyja.eval.enlargement_run`; this file only wires the REAL out-of-process arms:

  - snapshot   : `load_swebench_verified()` (HF SWE-bench_Verified, split=test)
  - author     : Claude   via `claude -p` (authors the terse query, gold WITHHELD)
  - verifier   : Codex    via `codex exec` (independent leak check, separate context)
  - concept    : Codex    via `codex exec` (same/divergent, gold VISIBLE — a hand-label)
  - span text  : `git show <base_commit>:<path>` from a bare-ish clone (for reachability)

Blindness is enforced STRUCTURALLY inside the frozen 0036 protocol (the author prompt is
built from issue intent with the gold span withheld, and `assert_author_input_blind`
fires if the issue itself names the gold path — those cases are counted blind-ineligible,
never authored). Every drift/integrity failure is a StopAndWarn: the process exits
non-zero with the ledger preserved, and re-running resumes losslessly.

Usage (via run_enlargement.sh, the one command):
    python run_enlargement.py --fixtures harpyja/eval/fixtures \
        --out-dir harpyja/eval/fixtures --work-dir eval_work \
        --author-model <claude-tag> --verifier-model <codex-tag>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Ensure the repo root is importable when run as a bare script on the dev host.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harpyja.eval.enlargement import (  # noqa: E402
    PREREGISTERED_ENLARGEMENT_CONFIG_0047,
    validate_sampling_frame,
)
from harpyja.eval.enlargement_arms import (  # noqa: E402
    ArmError,
    make_invoke,
    preflight_arm,
    resolve_backends,
)
from harpyja.eval.enlargement_run import (  # noqa: E402
    EnlargementDeps,
    StopAndWarn,
    run_pipeline,
)
from harpyja.eval.swebench_eval import (  # noqa: E402
    PROVENANCE_NAME,
    RAW_NAME,
    _read_jsonl,
    load_swebench_verified,
)

_FRAME_PATH = Path(__file__).resolve().parent / "sampling_frame.json"
_AUTHORING_NAME = "swebench_verified.authoring.json"
_TERSE_NAME = "swebench_verified.terse.jsonl"
_MODEL_RETRIES = 3


# ---- real out-of-process arms -------------------------------------------------


def _run_cli(cmd: list[str], *, stdin_text: str | None = None, timeout: float = 240.0) -> str:
    """Invoke an operator CLI with bounded retries; StopAndWarn on repeated failure.
    The diagnostic includes BOTH stdout and stderr (some CLIs report errors on stdout)."""
    last = ""
    for attempt in range(1, _MODEL_RETRIES + 1):
        try:
            proc = subprocess.run(
                cmd, input=stdin_text, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
            last = (
                f"rc={proc.returncode} "
                f"stdout={proc.stdout.strip()[:200]!r} stderr={proc.stderr.strip()[:200]!r}"
            )
        except FileNotFoundError:
            raise StopAndWarn(
                f"operator CLI {cmd[0]!r} not found on PATH — install/authenticate it "
                "before running the enlargement driver"
            ) from None
        except subprocess.TimeoutExpired:
            last = f"timeout after {timeout}s"
        print(f"[run] {cmd[0]} attempt {attempt} failed: {last}", file=sys.stderr)
    raise StopAndWarn(f"operator CLI {cmd[0]} failed after {_MODEL_RETRIES} attempts: {last}")


def _make_verifier(backend: str, claude_model: str | None):
    invoke = make_invoke(backend, _run_cli, claude_model=claude_model)

    def _verify(prompt: str) -> str:
        return "leaky" if "leaky" in invoke(prompt).lower() else "clean"
    return _verify


def _make_concept_labeler(backend: str, claude_model: str | None):
    invoke = make_invoke(backend, _run_cli, claude_model=claude_model)

    def _label(case_id: str, query: str, gold_paths: tuple[str, ...], span_text: str) -> str:
        prompt = (
            "You are labeling a code-localization case. Given the developer's terse "
            "QUERY, the GOLD file(s), and the gold SPAN TEXT, answer with EXACTLY one "
            "word: 'same' if the concept the query asks about lives at the gold span, or "
            "'divergent' if the gold patch site differs from where the concept "
            "conceptually lives (a fix applied away from the concept's definition).\n\n"
            f"Query: {query}\nGold files: {', '.join(gold_paths)}\nSpan text:\n{span_text}\n"
        )
        return "divergent" if "divergent" in invoke(prompt).lower() else "same"
    return _label


def _span_text_reader(clones_dir: Path):
    """Read gold-span text via `git show <base_commit>:<path>` from a per-repo clone."""
    def _read(raw: dict) -> str:
        spans = raw.get("expected_spans") or []
        if not spans:
            return ""
        first = spans[0]
        owner_name = raw["repo"]  # "owner/name" at convert time
        clone = clones_dir / owner_name.replace("/", "__")
        if not (clone / ".git").exists():
            clone.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--quiet", f"https://github.com/{owner_name}.git", str(clone)],
                check=True, capture_output=True,
            )
        commit = raw["base_commit"]
        have = subprocess.run(
            ["git", "-C", str(clone), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True,
        )
        if have.returncode != 0:
            subprocess.run(["git", "-C", str(clone), "fetch", "--quiet", "origin", commit],
                           check=True, capture_output=True)
        blob = subprocess.run(
            ["git", "-C", str(clone), "show", f"{commit}:{first['path']}"],
            capture_output=True, text=True, check=True,
        ).stdout
        lines = blob.splitlines()
        s, e = int(first["start_line"]), int(first["end_line"])
        return "\n".join(lines[max(0, s - 1):e])
    return _read


# ---- entrypoint ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="spec 0047 enlargement operator driver")
    ap.add_argument("--fixtures", default="harpyja/eval/fixtures")
    ap.add_argument("--out-dir", default="harpyja/eval/fixtures")
    ap.add_argument("--work-dir", default="eval_work")
    ap.add_argument(
        "--author", "--author-model", dest="author", default="claude",
        help="author-arm backend: 'claude' or 'codex' (default claude)",
    )
    ap.add_argument(
        "--verifier", "--verifier-model", dest="verifier", default=None,
        help="verifier-arm backend (default: the complement of --author)",
    )
    ap.add_argument("--claude-model", default=None, help="optional Claude model tag")
    ap.add_argument("--effect-band", type=float, default=0.1)
    ap.add_argument("--check-arms", action="store_true",
                    help="preflight the author+verifier CLIs and exit")
    args = ap.parse_args(argv)

    # Resolve the two arms to DIFFERENT backends (blindness), then preflight them fast.
    try:
        author_backend, verifier_backend = resolve_backends(args.author, args.verifier)
    except ArmError as e:
        print(f"[STOP-AND-WARN] {e}", file=sys.stderr)
        return 2
    print(f"[run] arms: author={author_backend} verifier={verifier_backend}", file=sys.stderr)
    try:
        for role, backend in (("author", author_backend), ("verifier", verifier_backend)):
            preflight_arm(backend, _run_cli, claude_model=args.claude_model)
            print(f"[run] preflight OK: {role}={backend}", file=sys.stderr)
    except StopAndWarn as e:
        print(f"\n[STOP-AND-WARN] arm preflight failed: {e}\n"
              "(fix the CLI / auth, then re-run — nothing was converted)", file=sys.stderr)
        return 2
    if args.check_arms:
        print("[run] --check-arms: both arms healthy; exiting before convert.", file=sys.stderr)
        return 0

    fixtures = Path(args.fixtures)
    frame = validate_sampling_frame(json.loads(_FRAME_PATH.read_text(encoding="utf-8")))

    # Freeze-guard: the committed raw fixture must match the frame's pinned prior sha.
    from harpyja.eval.terse_dataset import _sha256_file

    prior = _sha256_file(fixtures / RAW_NAME)
    if prior != frame.prior_raw_fixture_sha256:
        raise StopAndWarn(
            f"committed raw fixture sha {prior} != frame prior "
            f"{frame.prior_raw_fixture_sha256} — the frame was frozen against a different "
            "raw fixture; refusing to enlarge"
        )

    existing_raw = _read_jsonl(fixtures / RAW_NAME)
    existing_terse = (
        [json.loads(x) for x in (fixtures / _TERSE_NAME).read_text().splitlines() if x.strip()]
        if (fixtures / _TERSE_NAME).is_file() else []
    )
    existing_authoring = (
        json.loads((fixtures / _AUTHORING_NAME).read_text())
        if (fixtures / _AUTHORING_NAME).is_file()
        else {"schema_version": "0026/1", "leaky_count": 0, "dropped_count": 0, "records": []}
    )
    existing_provenance = json.loads((fixtures / PROVENANCE_NAME).read_text())

    def _load_snapshot():
        _name, ds = load_swebench_verified()
        rows = [dict(r) for r in ds]
        for r in rows:
            r.setdefault("query", r.get("problem_statement", ""))
        return getattr(ds, "_fingerprint", None), rows

    clones = Path(args.work_dir).resolve() / "clones"
    deps = EnlargementDeps(
        frame=frame,
        cfg=PREREGISTERED_ENLARGEMENT_CONFIG_0047,
        out_dir=Path(args.out_dir),
        ledger_path=Path(__file__).resolve().parent / "ledger.json",
        existing_raw_rows=existing_raw,
        existing_terse_rows=existing_terse,
        existing_authoring=existing_authoring,
        load_snapshot=_load_snapshot,
        author_invoke=make_invoke(author_backend, _run_cli, claude_model=args.claude_model),
        verifier_invoke=_make_verifier(verifier_backend, args.claude_model),
        concept_label=_make_concept_labeler(verifier_backend, args.claude_model),
        read_span_text=_span_text_reader(clones),
        author_model=author_backend,
        verifier_model=verifier_backend,
        concept_model=verifier_backend,
        effect_band=args.effect_band,
        existing_provenance=existing_provenance,
    )

    try:
        result = run_pipeline(deps)
    except StopAndWarn as e:
        print(f"\n[STOP-AND-WARN] {e}\n(ledger preserved — fix, then re-run to resume)",
              file=sys.stderr)
        return 2

    prov = fixtures / PROVENANCE_NAME
    print(
        "\n[run] enlargement complete.\n"
        f"  conceptual_n={result.conceptual_n} lexical_n={result.lexical_n}\n"
        f"  attrition: leaky={result.leaky_count} "
        f"blind_ineligible={result.blind_ineligible_count} dropped={result.dropped_count}\n"
        f"  verdicts: {json.dumps(result.questions, indent=2)}\n"
        f"  AUDIT ME: {Path(args.out_dir) / 'audit_sample.json'} (20 cases)\n"
        f"  provenance: {prov}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
