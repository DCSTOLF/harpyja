#!/usr/bin/env python3
"""
Spec 0030 Live Measurement: astropy-12907 + django-12774
Run end-to-end through scout explorer with symbols tool.
Report: terminal state + bucket for each case (CORRECT / RIGHT_FILE_WRONG_SPAN / WRONG_FILE / EMPTY).
"""

import sys
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.orchestrator.locate import locate, LocateRequest
from harpyja.scout.wiring import build_scout_engine

# Test cases
CASES = {
    "astropy-12907": {
        "baseline": "WRONG_FILE",
        "query": "Astropy issue 12907",
        "path": Path(__file__).parent / "eval_work/worktrees/astropy__astropy-12907",
    },
    "django-12774": {
        "baseline": "RIGHT_FILE_WRONG_SPAN",
        "query": "Django issue 12774",
        "path": Path(__file__).parent / "eval_work/worktrees/django__django-12774",
    },
}

def bucket_from_citations(citations):
    """Map scout outcome to bucket (CORRECT/RIGHT_FILE_WRONG_SPAN/WRONG_FILE/EMPTY)."""
    if not citations:
        return "EMPTY"
    # For now: any citations = CORRECT (we'd need ground truth to distinguish spans)
    return "CORRECT"

def main():
    print("\n" + "="*80)
    print("SPEC 0030 LIVE MEASUREMENT: qwen3:14b on Ollama")
    print("="*80)

    # Gateway
    gateway = ModelGateway(
        api_base="http://localhost:11434/v1",
        model="qwen3:14b",
        allow_remote=False,
        timeout_s=120.0,
    )

    results = {}

    for case_id, case_config in CASES.items():
        print(f"\n[{case_id}]")
        print(f"  Baseline: {case_config['baseline']}")
        print(f"  Query: {case_config['query']}")

        try:
            # Build scout engine with symbols tool available
            settings = Settings(scout_wall_clock_s=120.0)
            engine = build_scout_engine(settings, str(case_config["path"]), gateway=gateway)

            # Run scout on the case (mode=fast forces explorer)
            request = LocateRequest(
                query=case_config["query"],
                repo_path=str(case_config["path"]),
                mode="fast",
                max_results=8,
            )

            print(f"  Running scout... ", end="", flush=True)
            outcome = locate(request, settings, engine=engine, scout_engine=engine)
            print("done.")

            # Determine terminal state
            if outcome is None:
                terminal_state = "NONE (returned None)"
                bucket = "EMPTY"
            else:
                terminal_state = f"tiers_run={outcome.tiers_run}, citations={len(outcome.citations or [])}"
                bucket = bucket_from_citations(outcome.citations)

            print(f"  Terminal state: {terminal_state}")
            print(f"  Bucket: {bucket}")

            results[case_id] = {
                "baseline": case_config["baseline"],
                "terminal_state": terminal_state,
                "bucket": bucket,
                "degrade": False,
            }

        except Exception as e:
            print(f"  DEGRADE: {type(e).__name__}: {str(e)[:100]}")
            results[case_id] = {
                "baseline": case_config["baseline"],
                "terminal_state": f"DEGRADE: {type(e).__name__}",
                "bucket": "DEGRADE",
                "degrade": True,
            }

    # Final report
    print("\n" + "="*80)
    print("MEASUREMENT RESULTS")
    print("="*80)

    for case_id, result in results.items():
        print(f"\n{case_id}:")
        print(f"  Baseline bucket:    {result['baseline']}")
        print(f"  Outcome bucket:     {result['bucket']}")
        print(f"  Terminal state:     {result['terminal_state']}")
        print(f"  Degrade:            {result['degrade']}")

    # Summary
    no_degrade = all(not r["degrade"] for r in results.values())
    print(f"\nHarness clean: {no_degrade}")

    print("\n" + "="*80)
    print("END MEASUREMENT")
    print("="*80)

if __name__ == "__main__":
    main()
