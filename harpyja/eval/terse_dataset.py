"""spec 0026 — terse-query eval set loader (AC1).

A terse case references a SWE-bench case by `case_id` and carries only the terse
query + leakage-guard provenance. Its label (`expected_spans`), `base_commit`, and
source-issue text are JOINED at load time from the sha256-pinned committed raw
fixture (`swebench_verified.raw.jsonl`), which stays the SOLE authority — no span is
transcribed into the terse fixture. The sha256 pin is asserted BEFORE the join, so a
join never runs against an unverified source.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.dataset import (
    DatasetError,
    EvalCase,
    _parse_span,
    load_dataset,
)

_CLASSIFICATION_PROVENANCE = "hand-labeled-by-intent"

# The label reused verbatim from the raw fixture is the deterministic parse_patch
# output frozen at the audited network `convert` stage — never "human-confirmed".
LABEL_PROVENANCE = "patch-derived-at-convert"

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _is_code_like(tok: str) -> bool:
    """A token that reads as a code identifier, not ordinary English prose: it has an
    underscore, camelCase, or an embedded digit. Ordinary words ("nested", "models")
    are not flagged — the tripwire targets gold-span-only vocabulary."""
    return "_" in tok or bool(re.search(r"[a-z][A-Z]", tok)) or any(c.isdigit() for c in tok)


def compute_leaked_tokens(query: str, source_issue: str) -> tuple[str, ...]:
    """Layer-(a) tripwire (AC2): code-like identifiers present in `query` but ABSENT
    from `source_issue` (the joined raw problem_statement). Near-vacuous by design (a
    terse query drawn from the issue is almost always a subset) — a cheap first pass,
    NOT the load-bearing guard (that is the two-model blind protocol, layer b)."""
    issue_tokens = {t.lower() for t in _IDENTIFIER_RE.findall(source_issue)}
    leaked = {
        t
        for t in _IDENTIFIER_RE.findall(query)
        if _is_code_like(t) and t.lower() not in issue_tokens
    }
    return tuple(sorted(leaked))


@dataclass(frozen=True)
class JoinMeta:
    """Raw-record side data joined by case_id but NOT promoted onto `EvalCase`.

    `base_commit` stays a raw-record key (review B2) — resolved via provisioning for
    the offline scoring run, not a validated dataset field. `source_issue` is the raw
    `query` (the SWE-bench problem_statement), used to recompute the token-subset flag.
    """

    base_commit: str
    source_issue: str


@dataclass(frozen=True)
class TerseDataset:
    cases: list[EvalCase]
    join_meta: dict[str, JoinMeta]
    # known-correct-span-only (OQ2): cases with no locatable gold target are excluded
    # and COUNTED (provenance-of-a-null), never silently dropped.
    excluded_count: int = 0
    excluded_case_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FloorResult:
    """Whether a terse set clears the size/pairing floor (AC4)."""

    ok: bool
    usable_n: int
    num_repos: int
    min_n: int
    discordant_floor: int
    reasons: tuple[str, ...]


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def assert_raw_pin(raw_path: str | Path, provenance_path: str | Path) -> None:
    """Raise `DatasetError` unless the raw fixture's bytes match the sha256 pin."""
    prov = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
    pinned = prov.get("raw_fixture_sha256")
    if not pinned:
        raise DatasetError(f"provenance {provenance_path} has no raw_fixture_sha256 pin")
    actual = _sha256_file(raw_path)
    if actual != pinned:
        raise DatasetError(
            f"raw fixture sha256 mismatch: {actual} != pinned {pinned} "
            f"({raw_path}) — refusing to join against an unverified source"
        )


def _load_raw_index(raw_path: str | Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    text = Path(raw_path).read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        cid = row.get("case_id")
        if not cid:
            raise DatasetError(f"raw fixture line {line_no}: missing case_id")
        index[cid] = row
    return index


def load_terse_dataset(
    terse_path: str | Path,
    raw_path: str | Path,
    provenance_path: str | Path,
) -> TerseDataset:
    """Load terse cases and JOIN their labels from the sha256-pinned raw fixture."""
    # (1) integrity FIRST — never join against an unverified source.
    assert_raw_pin(raw_path, provenance_path)
    # (2) parse terse rows (terse branch: spans omitted, guard fields enforced).
    terse_cases = load_dataset(terse_path)
    raw_index = _load_raw_index(raw_path)

    joined: list[EvalCase] = []
    meta: dict[str, JoinMeta] = {}
    excluded: list[str] = []
    for c in terse_cases:
        raw = raw_index.get(c.case_id)
        if raw is None:
            raise DatasetError(
                f"terse case {c.case_id!r} not found in pinned raw fixture {raw_path}"
            )
        spans_raw = raw.get("expected_spans")
        if not isinstance(spans_raw, list) or not spans_raw:
            # known-correct-span-only: no locatable gold target → EXCLUDE and count.
            excluded.append(c.case_id)
            continue
        spans = tuple(_parse_span(s, 0) for s in spans_raw)
        source_issue = str(raw.get("query", ""))
        # Recompute the token-subset flag against the JOINED source issue — never
        # trust a `leaked_tokens` value stored in the terse file.
        leaked = compute_leaked_tokens(c.query, source_issue)
        joined.append(
            replace(
                c,
                expected_spans=spans,
                label_provenance=LABEL_PROVENANCE,
                leaked_tokens=leaked,
                classification_provenance=_CLASSIFICATION_PROVENANCE,
            )
        )
        meta[c.case_id] = JoinMeta(
            base_commit=str(raw.get("base_commit", "")),
            source_issue=source_issue,
        )
    return TerseDataset(
        cases=joined,
        join_meta=meta,
        excluded_count=len(excluded),
        excluded_case_ids=tuple(excluded),
    )


def validate_terse_set_floor(dataset: TerseDataset) -> FloorResult:
    """AC4: the set clears the paired-ranking floor — ≥ `min_n` usable cases across
    multiple repos with no single-repo domination. Cites the committed
    `benchmark_fit.PREREGISTERED_CONFIG` constants (never a re-declared magic number);
    `MIN_DISCORDANT_PAIRS` is the pairing floor a per-comparison bake-off must reach."""
    cfg = PREREGISTERED_CONFIG
    usable_n = len(dataset.cases)
    repo_counts: dict[str, int] = {}
    for c in dataset.cases:
        repo_counts[c.repo] = repo_counts.get(c.repo, 0) + 1
    num_repos = len(repo_counts)
    reasons: list[str] = []
    if usable_n < cfg.min_n:
        reasons.append(f"usable_n={usable_n} < min_n={cfg.min_n}")
    if num_repos < 2:
        reasons.append(f"only {num_repos} repo(s); need multiple")
    if usable_n and max(repo_counts.values()) > usable_n / 2:
        dom = max(repo_counts, key=lambda r: repo_counts[r])
        reasons.append(
            f"single-repo domination: {dom} holds {repo_counts[dom]}/{usable_n}"
        )
    return FloorResult(
        ok=not reasons,
        usable_n=usable_n,
        num_repos=num_repos,
        min_n=cfg.min_n,
        discordant_floor=cfg.MIN_DISCORDANT_PAIRS,
        reasons=tuple(reasons),
    )
