"""spec 0036 T11 — operator blind-authoring run (offline, two-model, Ollama live).

PRE-DECLARED pilot selection rule (fixed before any authoring output was seen):
the alphabetically FIRST case_id of each repo, repos taken alphabetically, first
10 repos — deterministic, multi-repo by construction, no post-hoc cherry-picking.

AMENDMENT (recorded after the first run's loud stop, still query-blind — no
authoring output had been produced): `assert_author_input_blind` rejected
django__django-12774 because the ISSUE TEXT itself contains the gold-span path
('django/db/models/query.py') — such a case cannot be blind-authored at all.
The rule becomes: per repo, the alphabetically first case whose issue text
contains NO gold-span path (the same precondition the pin enforces); ineligible
cases are SKIPPED AND RECORDED below (exclude-and-count, provenance-of-a-null),
never silently dropped. This is an eligibility precondition of the protocol
itself, decided before seeing any authored query.

Protocol: 0026's `author_terse_set` (author model != verifier model, separate
invocations; gold withheld from the author; `assert_author_input_blind` runs
per case). Author: qwen3:14b. Verifier: qwen3:8b. Both must be servable —
any infra error is STOP-AND-WARN (loud abort), never a skip.

The verifier wrapper normalizes the verdict to exactly "leaky"/"clean" and
FAILS CLOSED (raises) on an ambiguous answer — `author_terse_case` compares
verdict == "leaky" by equality, so an unparsed verbose answer would silently
read as "clean" (fail-open toward keep) without this guard.

Outputs (both committed):
- harpyja/eval/fixtures/swebench_verified.authoring.json  (AuthoringArtifact)
- specs/0036-terse-query/authoring/authored_queries.json  (kept case rows,
  0026/1-shaped; T12 tags them into the final 0036/1 fixture rows)
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.authoring_provenance import write_authoring_artifact  # noqa: E402
from harpyja.eval.terse_authoring import author_terse_set  # noqa: E402

OLLAMA = "http://127.0.0.1:11434"
AUTHOR_MODEL = "qwen3:14b"
VERIFIER_MODEL = "qwen3:8b"
PILOT_N = 10

FIXTURES = REPO_ROOT / "harpyja" / "eval" / "fixtures"
RAW = FIXTURES / "swebench_verified.raw.jsonl"
OUT_QUERIES = Path(__file__).parent / "authored_queries.json"


def _chat(model: str, prompt: str, *, max_tokens: int = 4096, timeout: int = 600) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    return payload["choices"][0]["message"]["content"] or ""


def _preflight() -> None:
    with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=10) as resp:
        served = {m["name"] for m in json.loads(resp.read())["models"]}
    missing = {AUTHOR_MODEL, VERIFIER_MODEL} - served
    if missing:
        raise SystemExit(f"STOP-AND-WARN: models not servable: {sorted(missing)}")


def _blind_eligible(row: dict) -> bool:
    # The same precondition assert_author_input_blind enforces: an issue text
    # that already names a gold-span path cannot be authored blind at all.
    issue = str(row["query"])
    return not any(sp["path"] in issue for sp in row["expected_spans"])


def _select_pilot(raw_rows: list[dict]) -> tuple[list[dict], list[str]]:
    by_repo: dict[str, list[dict]] = {}
    for row in sorted(raw_rows, key=lambda r: r["case_id"]):
        by_repo.setdefault(row["repo"], []).append(row)
    picked: list[dict] = []
    skipped: list[str] = []
    for repo in sorted(by_repo):
        if len(picked) >= PILOT_N:
            break
        chosen = None
        for row in by_repo[repo]:
            if _blind_eligible(row):
                chosen = row
                break
            skipped.append(f"{row['case_id']} (issue text contains a gold-span path)")
        if chosen is not None:
            picked.append(chosen)
    return picked, skipped


def author_invoke(prompt: str) -> str:
    return _chat(AUTHOR_MODEL, prompt).strip()


def verifier_invoke(prompt: str) -> str:
    raw = _chat(VERIFIER_MODEL, prompt).strip().lower()
    has_leaky = "leaky" in raw
    has_clean = "clean" in raw
    if has_leaky and not has_clean:
        return "leaky"
    if has_clean and not has_leaky:
        return "clean"
    raise SystemExit(
        f"STOP-AND-WARN: ambiguous verifier verdict (fail closed, never a silent keep): {raw!r}"
    )


def main() -> None:
    _preflight()
    raw_rows = [json.loads(l) for l in RAW.read_text().splitlines() if l.strip()]
    pilot, skipped = _select_pilot(raw_rows)
    print(f"pilot selection ({len(pilot)} cases, rule: first blind-eligible case_id "
          f"per repo, first {PILOT_N} repos alphabetically):")
    for row in pilot:
        print(f"  {row['case_id']}")
    for s in skipped:
        print(f"  SKIPPED (blind-ineligible, recorded): {s}")

    cases, artifact = author_terse_set(
        pilot,
        author_invoke=author_invoke,
        verifier_invoke=verifier_invoke,
        author_model=AUTHOR_MODEL,
        verifier_model=VERIFIER_MODEL,
    )
    for rec in artifact.records:
        print(f"  {rec.case_id}: verdict={rec.verifier_verdict} outcome={rec.outcome}")
    print(f"kept={len(cases)} leaky={artifact.leaky_count} dropped={artifact.dropped_count}")

    # Persist the artifact beside the fixtures (repo_path = a measurement-target
    # worktree, NOT the harpyja tree — the writer guards the target repo).
    target_repo = REPO_ROOT / "eval_work" / "worktrees" / "astropy__astropy-12907"
    out = write_authoring_artifact(artifact, out_dir=FIXTURES, repo_path=target_repo)
    print(f"authoring artifact: {out}")

    rows = [
        {
            "schema_version": c.schema_version,
            "case_id": c.case_id,
            "query": c.query,
            "repo": c.repo,
            "classification": c.classification,
            "gold_withheld": c.gold_withheld,
            "query_provenance": c.query_provenance,
            "classification_provenance": c.classification_provenance,
        }
        for c in cases
    ]
    OUT_QUERIES.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"authored queries: {OUT_QUERIES}")


if __name__ == "__main__":
    main()
