"""Spec 0049 — greedy serving: the deterministic Modelfile fingerprint + driver.

PATH A (0049): greedy is served via NEW ``*-greedy`` variant tags built from the
committed ``serving/Modelfile.*`` (base tags UNTOUCHED). This module owns:

- ``parse_modelfile_fingerprint`` — the ONE deterministic grammar reducing a
  Modelfile to ``FROM`` + a sorted ``PARAMETER`` map + ``TEMPLATE`` + ``SYSTEM``,
  failing loud on duplicate keys / out-of-set directives (never a lossy coerce).
  The SAME parser computes the committed fingerprint (for the config hash) and
  the live ``ollama show`` fingerprint (for conformance), so they are comparable
  by construction.
- ``build_greedy_variant`` — idempotent ``ollama create`` driver; NOOP on a
  semantic match, STOP-AND-WARN (never overwrite) on drift, CREATE when absent.
  Every subprocess seam is bound to the resolved local daemon: resolve host once
  → ``assert_local`` that exact host FIRST → pass it explicitly via ``OLLAMA_HOST``
  in a sanitized env (the provisioning-egress invariant — provisioning, not
  inference; no completions-Gateway change).

Pure/injected: no real subprocess or network here — the host resolver,
``assert_local``, ``ollama show``, and ``ollama create`` seams are all passed in,
so the unit surface runs offline.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import os
import warnings
from collections.abc import Callable

# The exactly-representable directive set. Anything else fails loud (a registry
# extension we cannot fingerprint losslessly is rejected, not silently dropped).
_ALLOWED_DIRECTIVES = frozenset({"FROM", "PARAMETER", "TEMPLATE", "SYSTEM"})


class ModelfileGrammarError(ValueError):
    """A Modelfile the one-parser cannot represent losslessly — loud, never coerced."""


@dataclasses.dataclass(frozen=True)
class ModelfileFingerprint:
    """The canonical semantic reduction of a Modelfile (order-independent)."""

    from_base: str
    parameters: tuple[tuple[str, str], ...]  # sorted (key, value)
    template: str | None = None
    system: str | None = None


def _normalize(text: str) -> list[str]:
    """CRLF/CR → LF, split to lines (comments/blanks handled by the scanner)."""

    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _strip_quotes(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"""') and raw.endswith('"""') and len(raw) >= 6:
        return raw[3:-3].strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return raw


def parse_modelfile_fingerprint(text: str) -> ModelfileFingerprint:
    """Reduce ``text`` to a ``ModelfileFingerprint`` via the one deterministic grammar."""

    lines = _normalize(text)
    from_base = ""
    params: dict[str, str] = {}
    template: str | None = None
    system: str | None = None

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        parts = stripped.split(None, 1)
        directive = parts[0].upper()
        remainder = parts[1] if len(parts) > 1 else ""

        if directive not in _ALLOWED_DIRECTIVES:
            raise ModelfileGrammarError(f"out-of-set directive: {parts[0]!r}")

        if directive == "FROM":
            from_base = remainder.strip()
            i += 1
            continue

        if directive == "PARAMETER":
            kv = remainder.split(None, 1)
            if len(kv) != 2:
                raise ModelfileGrammarError(f"malformed PARAMETER: {stripped!r}")
            key, value = kv[0], kv[1].strip()
            if key in params:
                raise ModelfileGrammarError(f"duplicate PARAMETER key: {key!r}")
            params[key] = value
            i += 1
            continue

        # TEMPLATE / SYSTEM — single-line or a ``"""`` multiline block.
        rem = remainder.lstrip()
        if rem.startswith('"""') and '"""' not in rem[3:]:
            # Opening a multiline block; gather RAW lines until the closing fence.
            collected = [rem[3:]]
            i += 1
            while i < n and '"""' not in lines[i]:
                collected.append(lines[i])
                i += 1
            if i >= n:
                raise ModelfileGrammarError(f"unterminated {directive} block")
            collected.append(lines[i][: lines[i].index('"""')])
            value = "\n".join(collected).strip()
            i += 1
        else:
            value = _strip_quotes(remainder)
            i += 1

        if directive == "TEMPLATE":
            if template is not None:
                raise ModelfileGrammarError("duplicate TEMPLATE directive")
            template = value
        else:  # SYSTEM
            if system is not None:
                raise ModelfileGrammarError("duplicate SYSTEM directive")
            system = value

    return ModelfileFingerprint(
        from_base=from_base,
        parameters=tuple(sorted(params.items())),
        template=template,
        system=system,
    )


@dataclasses.dataclass(frozen=True)
class ParamDelta:
    """The semantic delta between two fingerprints — FROM EXCLUDED (a live-``show``
    FROM is a blob path, not a definition change)."""

    added: tuple[tuple[str, str], ...]  # (key, greedy_value)
    removed: tuple[tuple[str, str], ...]  # (key, base_value)
    changed: tuple[tuple[str, str, str], ...]  # (key, base_value, greedy_value)
    template_changed: bool
    system_changed: bool


def fingerprint_delta(
    base: ModelfileFingerprint, greedy: ModelfileFingerprint
) -> ParamDelta:
    """Diff ``greedy`` against ``base`` over the canonical PARAMETER map (+ template/
    system flags); ``FROM`` is deliberately excluded."""

    b = dict(base.parameters)
    g = dict(greedy.parameters)
    added = tuple(sorted((k, g[k]) for k in g.keys() - b.keys()))
    removed = tuple(sorted((k, b[k]) for k in b.keys() - g.keys()))
    changed = tuple(
        sorted((k, b[k], g[k]) for k in b.keys() & g.keys() if b[k] != g[k])
    )
    return ParamDelta(
        added=added,
        removed=removed,
        changed=changed,
        template_changed=base.template != greedy.template,
        system_changed=base.system != greedy.system,
    )


def is_exactly_temperature_delta(delta: ParamDelta) -> bool:
    """True iff the ONLY difference is the ``temperature`` PARAMETER (added or
    changed) — any other touched key, or a template/system change, fails."""

    touched = (
        {k for k, _ in delta.added}
        | {k for k, _ in delta.removed}
        | {k for k, _, _ in delta.changed}
    )
    return (
        touched == {"temperature"}
        and not delta.template_changed
        and not delta.system_changed
    )


def fingerprint_digest(fp: ModelfileFingerprint) -> str:
    """sha256 over the canonical rendering — the value committed into the config."""

    rendered = "\n".join(
        [
            f"FROM {fp.from_base}",
            *[f"PARAMETER {k} {v}" for k, v in fp.parameters],
            f"TEMPLATE {fp.template!r}",
            f"SYSTEM {fp.system!r}",
        ]
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


# ---- build driver -----------------------------------------------------------


class GreedyBuildOutcome(enum.Enum):
    """The per-tag build answer space — mutually exclusive, never a silent overwrite."""

    CREATED = "created"
    NOOP_MATCH = "noop-match"
    STOP_AND_WARN_MISMATCH = "stop-and-warn-mismatch"


def local_ollama_env(host: str) -> dict[str, str]:
    """A SANITIZED env binding the CLI to the resolved local daemon.

    A minimal allowlist: ``OLLAMA_HOST`` pinned to the exact ``assert_local``-ed
    host, plus the operational necessities ``PATH`` (so ``ollama`` is findable)
    and ``HOME`` (so the CLI can read ``~/.ollama``). It NEVER inherits the ambient
    env — in particular a stray ``OLLAMA_HOST`` cannot redirect the CLI to a
    different daemon.
    """

    env = {"OLLAMA_HOST": host, "PATH": os.environ.get("PATH", "")}
    home = os.environ.get("HOME")
    if home is not None:
        env["HOME"] = home
    return env


# ---- Live-Modelfile tolerant PARAMETER extraction (AC4a) --------------------
#
# ``ollama show --modelfile`` emits the FULLY-EXPANDED definition (blob FROM, a
# big TEMPLATE, a LICENSE block, MULTI-VALUED ``PARAMETER stop``) — the strict
# committed-file grammar rejects it by design. The live base-diff compares only
# the PARAMETER maps, so it needs a tolerant, PARAMETER-only extractor.


def parse_live_parameters(text: str) -> dict[str, tuple[str, ...]]:
    """Extract the PARAMETER map from a live ``ollama show --modelfile`` output.

    Tolerant (ignores TEMPLATE/SYSTEM/LICENSE/etc.) and MULTI-VALUED: a repeated
    key (e.g. ``stop``) collects all values as a sorted tuple.
    """

    collected: dict[str, list[str]] = {}
    for raw in _normalize(text):
        stripped = raw.strip()
        if not stripped.upper().startswith("PARAMETER"):
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 3:
            continue
        _, key, value = parts
        collected.setdefault(key, []).append(value.strip())
    return {k: tuple(sorted(v)) for k, v in collected.items()}


def live_param_delta(base_text: str, greedy_text: str) -> set[str]:
    """The set of PARAMETER keys whose value-set differs between base and greedy
    (added, removed, or changed) — FROM/TEMPLATE/SYSTEM/LICENSE excluded."""

    base = parse_live_parameters(base_text)
    greedy = parse_live_parameters(greedy_text)
    return {k for k in base.keys() | greedy.keys() if base.get(k) != greedy.get(k)}


def is_exactly_temperature_live(base_text: str, greedy_text: str) -> bool:
    """True iff the ONLY differing PARAMETER between the live base and greedy
    Modelfiles is ``temperature`` (the AC4a live base-diff predicate)."""

    return live_param_delta(base_text, greedy_text) == {"temperature"}


def _semantic_match(a: ModelfileFingerprint, b: ModelfileFingerprint) -> bool:
    """Equal on the generation-bearing fields — FROM EXCLUDED (live ``show``
    normalizes ``FROM`` to a blob path, so a FROM diff is not a definition drift)."""

    return (
        a.parameters == b.parameters
        and a.template == b.template
        and a.system == b.system
    )


def build_greedy_variant(
    tag: str,
    modelfile_path: object,
    committed_fp: ModelfileFingerprint,
    *,
    host_resolver: Callable[[], str],
    assert_local_fn: Callable[[str], None],
    show_fn: Callable[..., str],
    create_fn: Callable[..., None],
) -> GreedyBuildOutcome:
    """Idempotent ``ollama create`` from the committed Modelfile.

    Order (load-bearing): resolve host once → ``assert_local`` FIRST → live
    ``show`` (absent tag raises ``FileNotFoundError``) → semantic compare. Match →
    NOOP; drift → STOP-AND-WARN (never overwrites); absent → CREATE.
    """

    host = host_resolver()
    assert_local_fn(host)  # FIRST — before any subprocess seam
    env = local_ollama_env(host)

    try:
        live_text = show_fn(tag, env=env)
    except FileNotFoundError:
        live_text = None

    if live_text is None:
        create_fn(tag, modelfile_path, env=env)
        return GreedyBuildOutcome.CREATED

    live_fp = parse_modelfile_fingerprint(live_text)
    if _semantic_match(live_fp, committed_fp):
        return GreedyBuildOutcome.NOOP_MATCH

    warnings.warn(
        f"greedy tag {tag!r} exists with a DIFFERENT definition — refusing to "
        f"overwrite (STOP-AND-WARN); reconcile the Modelfile or drop the tag.",
        stacklevel=2,
    )
    return GreedyBuildOutcome.STOP_AND_WARN_MISMATCH


def read_live_modelfile(
    tag: str,
    *,
    host: str,
    run_fn: Callable[..., str],
) -> str:
    """Run ``ollama show --modelfile <tag>`` bound to the resolved local daemon."""

    env = local_ollama_env(host)
    return run_fn(["ollama", "show", "--modelfile", tag], env=env)


__all__ = [
    "GreedyBuildOutcome",
    "ModelfileFingerprint",
    "ModelfileGrammarError",
    "ParamDelta",
    "build_greedy_variant",
    "fingerprint_delta",
    "fingerprint_digest",
    "is_exactly_temperature_delta",
    "is_exactly_temperature_live",
    "live_param_delta",
    "local_ollama_env",
    "parse_live_parameters",
    "parse_modelfile_fingerprint",
    "read_live_modelfile",
]
