"""Spec 0023 (AC2) — the dual distiller (the Axis-1 honesty guard).

Two arms, asymmetric roles:

- `mechanical_distill` — the PRIMARY, verdict-driving arm. A single case-agnostic
  extraction rule: take the first non-empty line, drop code-identifier tokens (file
  paths, dotted/CamelCase symbols, stack-trace frames, quoted/exact error strings), and
  keep the natural-language words. Because it only ever SELECTS from the issue's own
  tokens, its output tokens are a subset of the issue tokens — it is *structurally*
  incapable of injecting gold-span vocabulary, so it cannot manufacture a false
  QUERY_SHAPE. It never receives the gold span.
- `llm_distill_guarded` — the LABELED, non-primary SENSITIVITY arm. A more natural
  reformulation from an injected `Callable`, gated by a post-hoc token-subset HARD
  REJECT: any output token absent from the issue raises `DistillRejected`, so a biased
  LLM cannot slip gold vocabulary through either.

Both the mechanical rule id and the LLM prompt are pre-registered via a recorded hash.
"""

from __future__ import annotations

import hashlib
import re
import string
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class DistillResult:
    """A distilled terse query plus the identifier tokens stripped, for the audit trail."""

    query: str
    stripped_tokens: tuple[str, ...]


class DistillRejected(Exception):
    """Raised when a guarded (LLM) distillation introduces tokens absent from the issue."""


# ---- pre-registration -------------------------------------------------------

_MECHANICAL_RULE_ID = "first-nonempty-line-nl-tokens-strip-identifiers-v1"
MECHANICAL_RULE_HASH = hashlib.sha256(_MECHANICAL_RULE_ID.encode()).hexdigest()

LLM_PROMPT = (
    "Rewrite the following software issue as a short natural-language search query for "
    "locating the relevant code. Use ONLY words that already appear in the issue. Do "
    "not add file names, symbols, identifiers, or any word the issue does not contain.\n\n"
    "Issue:\n{issue}\n\nTerse query:"
)
LLM_PROMPT_HASH = hashlib.sha256(LLM_PROMPT.encode()).hexdigest()


# ---- shared tokenization ----------------------------------------------------

_WORD_RE = re.compile(r"[a-z]+")


def issue_tokens(text: str) -> set[str]:
    """Lowercase alphabetic word tokens — the basis for the subset property/guard."""
    return set(_WORD_RE.findall(text.lower()))


# ---- mechanical distiller (primary) ----------------------------------------

_TRACEBACK_RE = re.compile(r"^\s*Traceback\b.*$", re.MULTILINE)
_TRACE_FRAME_RE = re.compile(r'^\s*File\s+"[^"]*",\s*line\s+\d+.*$', re.MULTILINE)
_QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")
_PUNCT = string.punctuation


def _is_identifier(core: str) -> bool:
    """A code-identifier token to strip: file paths, dotted/CamelCase symbols, or any
    token carrying digits — anything that would let the distilled query become a
    symbol-lookup shortcut rather than a natural-language query."""
    if "/" in core or "." in core:
        return True
    if any(ch.isdigit() for ch in core):
        return True
    # internal capital: camelCase / CamelCase (a lowercase followed by an uppercase, or
    # two uppercase letters) — leaves a sentence-initial single capital alone.
    if re.search(r"[a-z][A-Z]", core) or re.search(r"[A-Z].*[A-Z]", core):
        return True
    return False


def mechanical_distill(issue_text: str) -> DistillResult:
    """PRIMARY distiller: first non-empty line → NL words, code identifiers stripped.

    Case-agnostic and gold-span-blind by signature (only `issue_text`). Output words are
    lowercased cores drawn from the issue's own tokens, so `issue_tokens(query)` is a
    subset of `issue_tokens(issue_text)`.
    """
    text = _TRACEBACK_RE.sub(" ", issue_text)
    text = _TRACE_FRAME_RE.sub(" ", text)
    text = _QUOTED_RE.sub(" ", text)

    first = ""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            break

    kept: list[str] = []
    stripped: list[str] = []
    for tok in first.split():
        core = tok.strip(_PUNCT)
        if not core:
            continue
        if _is_identifier(core):
            stripped.append(tok)
        else:
            kept.append(core.lower())
    return DistillResult(query=" ".join(kept), stripped_tokens=tuple(stripped))


# ---- LLM sensitivity arm (labeled, non-primary) ----------------------------


def llm_distill_guarded(issue_text: str, *, llm: Callable[[str], str]) -> DistillResult:
    """SENSITIVITY distiller: an injected reformulation, guarded by a post-hoc
    token-subset HARD REJECT. Any output token absent from the issue → `DistillRejected`
    (never passed through), so the LLM cannot introduce gold vocabulary."""
    raw = llm(issue_text)
    foreign = issue_tokens(raw) - issue_tokens(issue_text)
    if foreign:
        raise DistillRejected(f"foreign tokens not in issue: {sorted(foreign)}")
    return DistillResult(query=raw.strip(), stripped_tokens=())
