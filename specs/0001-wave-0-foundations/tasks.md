---
id: "0001"
title: "Wave 0 — Foundations"
plan: specs/0001-wave-0-foundations/plan.md
created: 2026-06-26
---

# Tasks 0001 — Wave 0 — Foundations

Execution order. Every RED precedes its GREEN. See `plan.md` for detail.

- [x] 1. RED: Failing import test for the eight subpackages + cli.py
- [x] 2. GREEN: pyproject.toml + harpyja package skeleton (shells)
- [x] 3. REFACTOR: ruff check + pytest gate green on skeleton
- [x] 4. RED: Config precedence test (defaults < toml < env < request)
- [x] 5. GREEN: Implement layered settings load/resolve
- [x] 6. RED: harpyja.toml discovery-order test
- [x] 7. GREEN: Implement discover_config_path (explicit > cwd > repo-root)
- [x] 8. RED: assert_local air-gap test (loopback pass / remote raise / no network)
- [x] 9. GREEN: Implement ModelGateway shell + assert_local
- [x] 10. RED: LocateResult shape + locate stub test
- [x] 11. GREEN: Implement result dataclasses + locate_stub
- [x] 12. RED: FastMCP app builds and registers harpyja_locate (loopback default)
- [x] 13. GREEN: Implement build_app + harpyja_locate registration + transport runners
- [x] 14. RED: stdio stdout-hygiene / stderr-logging test
- [x] 15. GREEN: Implement stderr-only configure_logging
- [x] 16. RED: CLI serve wiring test (stdio/http, loopback default, opt-out)
- [x] 17. GREEN: Implement CLI serve subcommand + console script
- [x] 18. RED: harpyja doctor test (rg/deno/endpoint/air-gap, no live call)
- [x] 19. GREEN: Implement run_doctor + doctor subcommand
- [x] 20. MANUAL: Add + verify .mcp.json (Claude Code) and Codex config.toml recipes
      (recipes in docs/registration/; AC11/12 manual, automated proxy = integration test)
- [x] 21. REFACTOR: Final ruff+pytest gate (60 passed, ruff clean); fixtures kept local
