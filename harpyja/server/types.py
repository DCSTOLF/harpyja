"""Result/request data shapes, verbatim from SPEC.md §2.1 / §3.

These are the contract every tier will produce. Wave 0 only constructs the
empty stub, but pinning the shapes now keeps later waves additive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["auto", "fast", "deep"]
Confidence = Literal["high", "medium", "low", "degraded"]


@dataclass
class CodeSpan:
    path: str  # repo-relative
    start_line: int
    end_line: int
    symbol: str | None = None
    language: str | None = None
    kind: str | None = None  # Wave 2: symbol kind for a definition span (else None)


@dataclass
class Citation(CodeSpan):
    rationale: str | None = None
    source_tier: int = 0
    score: float = 0.0


@dataclass
class LocateRequest:
    query: str
    repo_path: str
    mode: Mode = "auto"
    max_results: int = 8
    language_hint: str | None = None


@dataclass
class LocateResult:
    citations: list[Citation] = field(default_factory=list)
    confidence: Confidence = "low"
    tiers_run: list[int] = field(default_factory=list)
    notes: str | None = None
