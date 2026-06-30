# Domain requirement archive

Verbatim superseded requirement text demoted from a domain file by spec consolidation. Append-only.

## orchestrator | spec 0003 | MODIFY
- `harpyja_locate` runs a full incremental index refresh before searching (the `(mtime, size)` gate makes an up-to-date tree cost only a walk), building the manifest from scratch when none exists, so a query reflects added/modified/deleted files with no explicit re-index call. (spec 0002)

## orchestrator | spec 0006 | MODIFY
- Routing is mode-driven: `mode=auto` runs Tier 0 only with no model/Gateway call, `mode=fast` runs Scout (Tier 1) and stops, and `mode=deep` routes to the best-available higher tier; `harpyja_index`, `harpyja_read`, and `auto` `harpyja_locate` make zero model/Gateway calls. (spec 0005)

## orchestrator | spec 0008 | MODIFY
- Routing is mode-driven: `mode=auto` runs Tier 0 only with no model/Gateway call, `mode=fast` runs Scout (Tier 1) and stops, and `mode=deep` runs its own Tier-0 seed then skips Scout and runs Tier 2 Deep (`tiers_run=[0,2]`, `source_tier=2`); `harpyja_index`, `harpyja_read`, `auto` `harpyja_locate`, and `fast` make zero Deep calls. (specs 0005, 0006)

## symbols | spec 0004 | MODIFY
- The build pins individual tree-sitter grammar packages (`tree-sitter-python`, `tree-sitter-go`) plus the `tree-sitter` runtime at explicit versions — never the aggregate `tree-sitter-languages` wheel; parsing runs fully locally with bundled grammars and introduces no runtime network egress, leaving `gateway.assert_local` and the inbound-bind defaults untouched. (spec 0003)

## scout | spec 0011 | MODIFY
- Backend output is normalized into valid `CodeSpan`s clamped and repo-confined; hostile/malformed output (out-of-repo path, nonexistent file, out-of-range/inverted range, duplicates, over-budget) is clamped or dropped, never propagated, bounded by `scout_max_citations` (clamped to `min(scout_max_citations, req.max_results)`) and `scout_max_span_lines`. (spec 0005)

## packaging | spec 0013 | MODIFY
- FastContext is a pinned `git` dependency (no PyPI) installed via a portable `git+https` pin at SHA `1522d6d6b5e040e817b468e12826662aa069a8b0`; `requires-python >=3.12`. (spec 0007)
