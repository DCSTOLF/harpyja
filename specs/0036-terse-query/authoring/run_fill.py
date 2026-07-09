"""spec 0036 T11 fill pass — restore pilot_n=10 after leaky drops.

The first pass dropped 3 of 10 cases as leaky (mwaskom/seaborn, psf/requests,
pylint-dev/pylint — recorded in the committed artifact). Per 0026's own
protocol (leaky -> drop, re-author), this pass authors the NEXT blind-eligible
case of each dropped repo, in case_id order, until one authors clean (max 3
attempts per repo, every attempt recorded — kept, leaky-dropped, and
blind-ineligible skips alike). Same models, same prompts, same pins as the
first pass. Merges the new records into swebench_verified.authoring.json
(aggregate counts recomputed over ALL records) and appends kept rows to
authored_queries.json. STOP-AND-WARN on infra error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.authoring_provenance import (  # noqa: E402
    AuthoringArtifact,
    validate_authoring_artifact,
    write_authoring_artifact,
)
from harpyja.eval.terse_authoring import author_terse_case  # noqa: E402

from run_authoring import (  # noqa: E402  (the committed first-pass tooling)
    AUTHOR_MODEL,
    FIXTURES,
    OUT_QUERIES,
    RAW,
    VERIFIER_MODEL,
    _blind_eligible,
    _preflight,
    author_invoke,
    verifier_invoke,
)

ARTIFACT = FIXTURES / "swebench_verified.authoring.json"
# Pass 2 (recorded): mwaskom/seaborn EXHAUSTED (its only remaining case is
# blind-ineligible) — the rule's continuation moved to sphinx-doc/sphinx (repo 11),
# which went 3/3 leaky (budget exhausted, all recorded).
# Pass 3 (recorded): the LAST remaining repo, sympy/sympy (repo 12 of 12). If this
# also drops, the pilot runs at kept=9 across 9 repos — recorded, not padded.
DROPPED_REPOS = ("sympy/sympy",)
MAX_ATTEMPTS_PER_REPO = 3


def main() -> None:
    _preflight()
    artifact = validate_authoring_artifact(json.loads(ARTIFACT.read_text()))
    already = {r.case_id for r in artifact.records}
    raw_rows = [json.loads(l) for l in RAW.read_text().splitlines() if l.strip()]
    kept_rows = json.loads(OUT_QUERIES.read_text())

    records = list(artifact.records)
    for repo in DROPPED_REPOS:
        candidates = sorted(
            (r for r in raw_rows if r["repo"] == repo and r["case_id"] not in already),
            key=lambda r: r["case_id"],
        )
        attempts = 0
        for raw in candidates:
            if attempts >= MAX_ATTEMPTS_PER_REPO:
                print(f"  {repo}: attempt budget exhausted — repo stays at its drop")
                break
            if not _blind_eligible(raw):
                print(f"  SKIPPED (blind-ineligible, recorded): {raw['case_id']}")
                continue
            attempts += 1
            case, record = author_terse_case(
                raw,
                author_invoke=author_invoke,
                verifier_invoke=verifier_invoke,
                author_model=AUTHOR_MODEL,
                verifier_model=VERIFIER_MODEL,
            )
            records.append(record)
            print(f"  {record.case_id}: verdict={record.verifier_verdict} outcome={record.outcome}")
            if case is not None:
                kept_rows.append(
                    {
                        "schema_version": case.schema_version,
                        "case_id": case.case_id,
                        "query": case.query,
                        "repo": case.repo,
                        "classification": case.classification,
                        "gold_withheld": case.gold_withheld,
                        "query_provenance": case.query_provenance,
                        "classification_provenance": case.classification_provenance,
                    }
                )
                break

    merged = AuthoringArtifact(
        schema_version=artifact.schema_version,
        records=tuple(records),
        leaky_count=sum(1 for r in records if r.verifier_verdict == "leaky"),
        dropped_count=sum(1 for r in records if r.outcome == "dropped"),
    )
    target_repo = REPO_ROOT / "eval_work" / "worktrees" / "astropy__astropy-12907"
    out = write_authoring_artifact(merged, out_dir=FIXTURES, repo_path=target_repo)
    OUT_QUERIES.write_text(json.dumps(kept_rows, indent=2) + "\n", encoding="utf-8")
    print(
        f"merged artifact: {out} (records={len(records)} leaky={merged.leaky_count} "
        f"dropped={merged.dropped_count}); kept total={len(kept_rows)}"
    )


if __name__ == "__main__":
    main()
