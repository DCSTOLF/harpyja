# T20 Follow-up: Deduplicate tool-name parsers (measurement-integrity blocker)

**Status:** Open (blocker for bake-off consumption of verifier artifacts)

**Severity:** Correctness (not "tech debt")

## The Bug

Two divergent implementations of the same parsing operation in the verifier:

1. **`extract_tool_names()` in `live_verifier.py`** (verify path, line ~250):
   - Iterates `model_turns`, extracts `tool_calls[*].function.name`
   - **On unnamed call (missing `name` field): FAILS with `failure_reason = "tool-names-unextractable"`**
   - Sets `VerifierResult.tool_names_invoked = None`

2. **`build_trajectory_record()` in `live_verifier.py`** (capture path, line ~150):
   - Same iteration, same extraction
   - **On unnamed call: silently skips it**
   - Produces a `tool_names` list that omits the unnamed call

**Symptom:** A trajectory with unnamed tool_calls passes verify (FAILED with explicit code) but `build_trajectory_record` produces a tool_names list that hides the fact.

## Why It's a Correctness Bug

The verifier exists to produce **durable, trustworthy measurement artifacts**. Spec 0031 AC6 proves the instrument works by verifying:
- The tool-names invoked are extractable and named
- The trajectory is authentic and complete

Two copies of the extraction logic with divergent behavior violate this guarantee:

- **Current state (safe):** The verify path is the sole gate. If verification passes, we know all tools were named. Trajectories that hit `tool-names-unextractable` are rejected before `build_trajectory_record` runs.

- **Future risk (unsafe):** If ANY of these happen:
  - Downstream consumer reads `build_trajectory_record`'s `tool_names` list directly (bypassing verify)
  - Future spec accepts `"tool-names-unextractable"` as a valid (not-failed) outcome and processes the artifact
  - Refactor moves `extract_tool_names` logic elsewhere and someone forgets to update `build_trajectory_record`
  - A tool consumes verifier artifacts that are pre-verified elsewhere
  
  Then the silent-skip version creates a measurement hole: **a trajectory with unnamed tool calls is recorded as having complete tool names**.

## Precedent

This is the exact class of copy-divergence hazard that's bitten the project repeatedly:
- `normalize.py` split (two versions of citation normalization)
- `record_to_codespan` duplication (spec 0030's fix: deduplicated to one source)

The spec's contract is to eliminate exactly this: two measurements of the same thing with divergent semantics.

## Fix

**Single source of truth for tool-name extraction:**

Option A: Extract `build_trajectory_record` to a helper, call from both paths:
```python
def _extract_tool_names(model_turns: list[dict]) -> tuple[list[str], bool]:
    """Extract tool names from model turns.
    
    Returns: (tool_names_list, has_unnamed_calls)
    - tool_names_list: names of successfully extracted calls
    - has_unnamed_calls: True if any call lacked a 'name' field
    """
    tool_names = []
    has_unnamed = False
    for turn in model_turns:
        if isinstance(turn, dict) and 'tool_calls' in turn:
            for tc in turn['tool_calls']:
                if isinstance(tc, dict):
                    name = tc.get('function', {}).get('name')
                    if name:
                        tool_names.append(name)
                    else:
                        has_unnamed = True
    return tool_names, has_unnamed

# In extract_tool_names (verify path):
tool_names, has_unnamed = _extract_tool_names(trajectory['model_turns'])
if has_unnamed:
    return VerifierResult(status="FAILED", failure_reason="tool-names-unextractable")
result.tool_names_invoked = tool_names

# In build_trajectory_record (capture path):
tool_names, _ = _extract_tool_names(model_turns)
traj['tool_names_invoked'] = tool_names
```

Option B: Move tool-name extraction to trajectory-build time, verify against it:
```python
# Build trajectory with tool_names included
traj = build_trajectory_record(...)  # includes tool_names

# In verify: extract from the trajectory we already have
if 'tool_names_invoked' not in traj:
    return VerifierResult(status="FAILED", failure_reason="artifact-incomplete")
tool_names = traj['tool_names_invoked']
# Validate: no empty names
if any(not name for name in tool_names):
    return VerifierResult(status="FAILED", failure_reason="tool-names-unextractable")
```

## Blocker Until

- [ ] Dedup resolved (single source of truth)
- [ ] Test added: trajectory with unnamed call is rejected by verify, artifact captures tool_names correctly
- [ ] Spec 0035+ (bake-off) documents that verifier artifacts are trusted (verify gate passed), tool_names is complete

**Do not allow downstream specs to bypass verification or consume pre-verified artifacts until this is resolved.**

