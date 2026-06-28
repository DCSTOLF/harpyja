"""Wave 6a — measurement-only eval harness (spec 0009-6a).

Observes the `mode=auto` locate path through the real
`harpyja.orchestrator.locate.locate(...)` seam and reports locate accuracy,
escalation rate, and gate catch / false-escalation metrics. Emits a
recommendation for `(verify_threshold, verify_top_n)` (the OQ2 instrument); it
never modifies tier/gate/matrix behavior and never flips a `Settings` default.
"""
