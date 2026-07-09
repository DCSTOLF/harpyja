"""spec 0036 — mechanical lexical-reachability classifier (AC2, OQ2).

Tags whether a case's gold span is findable by the query's OWN code-like
vocabulary (`lexical`) or only by structural/conceptual navigation
(`conceptual`) — the axis that keeps a bake-off from confounding "models can't
localize" with "lexical tools can't reach conceptual gold" (the
RETRIEVAL_FUNDAMENTAL trap). Plain-English overlap deliberately does not count:
the classifier intersects only code-like identifiers (the same `_is_code_like`
tripwire semantics as the leakage guard).

Operator-side, NON-PRODUCT (0026 posture): runs strictly POST-authoring (it
needs gold visibility), is never surfaced to the author model, and imports no
gateway/SUT module — pinned by an ast import-absence guard in its tests. Pure,
no I/O.
"""

from __future__ import annotations

from harpyja.eval.terse_dataset import _IDENTIFIER_RE, _is_code_like

# Per-case reachability-tag provenance (recorded so OQ2's mechanical/hand-labeled
# mix stays auditable); values mirror dataset.REACHABILITY_PROVENANCES.
MECHANICAL = "mechanical"
HAND_LABELED = "hand-labeled"


def classify_reachability(query: str, span_text: str) -> str:
    """Return ``"lexical"`` when the gold-span text contains any code-like
    identifier from the query (case-insensitive), else ``"conceptual"``."""
    span_tokens = {t.lower() for t in _IDENTIFIER_RE.findall(span_text)}
    for tok in _IDENTIFIER_RE.findall(query):
        if _is_code_like(tok) and tok.lower() in span_tokens:
            return "lexical"
    return "conceptual"
