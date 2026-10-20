# Inspection and implementation plan (2026-10-20)

Branch develop; HEAD 9a864c546f5121748079ad58df2879faf8ffb46c; initial git status clean.
No AGENTS.md found. All existing tracked files will remain byte-identical.
Baseline command initially omitted PYTHONPATH and failed imports (retained in baseline-tests.txt).
Corrected invocation: PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m unittest discover -s projects/project3/tests -v.

Architecture: existing capture → detector → greedy tracker → target selection → FollowController → overlay/journal remains unchanged. Isolated research callers use Observation → RuleBasedController / disabled AIController → SafetySupervisor → CommandReplay. Optional HungarianTracker reuses inherited selection API and existing exact assignment utility. No integration into current CLI/pipeline.

Exact existing files to modify: NONE.
New source files: projects/project3/p3/research/{__init__.py,controllers.py,tracking.py,dataset.py,export.py,simulation.py,compare.py}.
New tests: projects/project3/tests/test_research.py.
New documentation/evidence: reports/ai-control-readiness-20261020/{PLAN.md,REPORT.md,baseline-tests.txt,baseline-corrected-tests.txt,preservation-before.json,final-tests.txt,project2-tests.txt,tracking-comparison.json,export-sample.jsonl,preservation-after.json,checks.txt}.

Risk: normalized outputs must never become SI commands; historical event time is journal emission elapsed time, not capture time; partial journals lack detections/boxes; assignment alone cannot resolve identity. Mitigation: explicit units/provenance/nulls, strict validation, no runtime wiring, deterministic parity and adversarial tests. No physical backend activation or hardware access.

Tests: baseline first; legacy/new P3 suite; P2 offline *_tests.py; fixture comparison using existing ground truth/detection visibility; real local journal conversion; repeat export byte comparison; source hashes and git diff. No model training/download, Docker, device, network or API calls.
