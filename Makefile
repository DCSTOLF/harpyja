# Harpyja — SWE-bench Verified eval (standalone localization protocol, spec 0010)
#
# Stages are separated by network posture (the run stage matches the air-gap posture):
#   convert    needs network (HuggingFace); writes the PORTABLE raw fixture — commit it.
#   provision  may clone repos; writes the machine-local resolved fixture — gitignored.
#   run/sweep  fully offline (local Ollama only).
#
# Quick start (after `uv add datasets`):
#   make swebench-sample     # convert a stratified sample + provision repos
#   make swebench-run        # drive the resolved fixture through locate() (auto)
#   make swebench-sweep      # OQ2 threshold×top_n sweep
#   make swebench-prune      # free worktree disk

PY            := uv run python
EVAL          := $(PY) -m harpyja.eval.swebench_eval
FIXTURES      := harpyja/eval/fixtures
WORK          := eval_work
REPORTS       := $(WORK)/reports

# Sample knobs (override on the CLI: `make swebench-sample SAMPLE=100 PER_REPO=8`)
SAMPLE        := 50
PER_REPO      := 5
SEED          := 0

# Deep model: the default Settings lm_model ("local") is a llama.cpp placeholder;
# against Ollama name a served model (override: `make swebench-run LM_MODEL=...`).
LM_MODEL      := qwen2.5-coder:3b
LM_API_BASE   := http://127.0.0.1:11434/v1
MODELFLAGS    := --lm-model $(LM_MODEL) --lm-api-base $(LM_API_BASE)

.PHONY: swebench-convert swebench-convert-full swebench-provision \
        swebench-sample swebench-full swebench-run swebench-run-fast \
        swebench-sweep swebench-prune

## Convert a stratified sample (N>=30 clears N_FLOOR → not flagged indicative-only)
swebench-convert:
	$(EVAL) convert --out-dir $(FIXTURES) --sample $(SAMPLE) --per-repo $(PER_REPO) --seed $(SEED)

## Convert the full 500-instance test split (heavy on provision)
swebench-convert-full:
	$(EVAL) convert --out-dir $(FIXTURES)

## Materialize each instance's repo at base_commit (git worktrees)
swebench-provision:
	$(EVAL) provision --fixtures $(FIXTURES) --work-dir $(WORK)

## One-shot: sampled fixture + provisioned repos, ready to run
swebench-sample: swebench-convert swebench-provision

## One-shot: full set + provisioned repos (opt-in; run AFTER the sample passes)
swebench-full: swebench-convert-full swebench-provision

## Drive the resolved fixture through the real locate() auto path (offline)
swebench-run:
	$(EVAL) run --fixtures $(FIXTURES) --out-dir $(REPORTS) --mode auto $(MODELFLAGS)

## Scout-only (mode=fast) line for the apples-to-apples Table-2 comparison
swebench-run-fast:
	$(EVAL) run --fixtures $(FIXTURES) --out-dir $(REPORTS) --mode fast $(MODELFLAGS)

## OQ2: sweep verify_threshold x verify_top_n over the resolved fixture
swebench-sweep:
	$(EVAL) sweep --fixtures $(FIXTURES) --out-dir $(REPORTS) $(MODELFLAGS)

## Remove materialized worktrees (add CLONES=1 to also drop the clone cache)
swebench-prune:
	$(EVAL) prune --work-dir $(WORK) $(if $(CLONES),--clones,)
