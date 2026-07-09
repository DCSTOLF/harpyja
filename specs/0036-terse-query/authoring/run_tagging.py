"""spec 0036 T12 — operator post-authoring tagging + fixture assembly.

Runs STRICTLY AFTER blind authoring (the tags need gold visibility; the author
model never sees them). For each kept authored case:

- reachability: MECHANICAL — `classify_reachability(query, span_text)` over the
  gold span text read from the case's provisioned worktree at base_commit
  (all expected spans concatenated: reachable if ANY gold span carries a
  query code-token).
- concept_patch_relation: HAND-LABELED. `divergent` only where documented
  evidence exists — astropy__astropy-12907 (the 0033 arc: the query's honest
  answer is `separability_matrix()` itself, astropy/modeling/separable.py:66-102,
  while the patch span is `_cstack` at lines 242-248). All other pilot cases:
  `same` (no evidence of concept/patch divergence in their issues).

Assembles the final `0036/1` rows and REPLACES the five placeholder rows in
harpyja/eval/fixtures/swebench_verified.terse.jsonl (placeholders cannot serve
as pilot cases and would pollute the floor count). The loud loader validates
the result end-to-end at the end of this script (fail here, not mid-test).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.dataset import DATASET_SCHEMA_VERSION_0036, load_dataset  # noqa: E402
from harpyja.eval.terse_dataset import load_terse_dataset  # noqa: E402
from harpyja.eval.terse_reachability import MECHANICAL, classify_reachability  # noqa: E402

FIXTURES = REPO_ROOT / "harpyja" / "eval" / "fixtures"
RAW = FIXTURES / "swebench_verified.raw.jsonl"
PROV = FIXTURES / "swebench_verified.provenance.json"
TERSE = FIXTURES / "swebench_verified.terse.jsonl"
QUERIES = Path(__file__).parent / "authored_queries.json"
WORKTREES = REPO_ROOT / "eval_work" / "worktrees"

# Hand-labels (documented-evidence-only; everything else is `same`).
DIVERGENT: dict[str, dict] = {
    "astropy__astropy-12907": {
        "concept_span": {
            "path": "astropy/modeling/separable.py",
            "start_line": 66,
            "end_line": 102,
        },
        "concept_span_provenance": "hand-labeled-concept-span",
    }
}


def _span_text(case_id: str, spans: list[dict]) -> str:
    wt = WORKTREES / case_id
    parts: list[str] = []
    for sp in spans:
        f = wt / sp["path"]
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        parts.append("\n".join(lines[sp["start_line"] - 1 : sp["end_line"]]))
    return "\n".join(parts)


def main() -> None:
    raw_index = {
        json.loads(l)["case_id"]: json.loads(l)
        for l in RAW.read_text().splitlines()
        if l.strip()
    }
    authored = json.loads(QUERIES.read_text())
    if not authored:
        raise SystemExit("STOP-AND-WARN: no authored queries found — run T11 first")

    rows: list[dict] = []
    for row in authored:
        cid = row["case_id"]
        raw = raw_index[cid]
        span_text = _span_text(cid, raw["expected_spans"])
        reach = classify_reachability(row["query"], span_text)
        tagged = {
            **row,
            "schema_version": DATASET_SCHEMA_VERSION_0036,
            "reachability": reach,
            "reachability_provenance": MECHANICAL,
            "concept_patch_relation": "divergent" if cid in DIVERGENT else "same",
        }
        if cid in DIVERGENT:
            tagged.update(DIVERGENT[cid])
        rows.append(tagged)
        print(f"  {cid}: reachability={reach} relation={tagged['concept_patch_relation']}")

    TERSE.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )
    print(f"replaced fixture: {TERSE} ({len(rows)} rows)")

    # Loud end-to-end validation: the loader + pinned join must accept the result.
    cases = load_dataset(TERSE)
    assert all(c.schema_version == "0036/1" for c in cases)
    ds = load_terse_dataset(TERSE, RAW, PROV)
    print(
        f"validated: {len(ds.cases)} joined cases, excluded={ds.excluded_count}, "
        f"reachability={[c.reachability for c in ds.cases]}"
    )


if __name__ == "__main__":
    main()
