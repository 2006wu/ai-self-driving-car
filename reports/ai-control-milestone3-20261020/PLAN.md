# Milestone 3 focused plan — 2026-10-20

Branch develop; HEAD 9a864c546f5121748079ad58df2879faf8ffb46c. Milestone 1/2 sources/tests/reports are uncommitted and must be preserved. No AGENTS.md found.

Review existing annotations.py, dataset_v2.py, recorder.py, evaluate_dataset.py and offline.py; reuse their file extraction, annotation validation and identical-detection evaluation interfaces. No new runtime/framework/schema/CLI functionality is needed to prepare a blocked human benchmark. No source files will be changed.

Inspection finding to verify: the full historical 1200-frame USA log contains at most one detected person per frame (10 frames total), whereas Milestone 2's first 120 frames contain none. Detector outputs are not human labels or proof of person absence. bus.jpg has four detections but is one image. Overlay AVIs are derived and excluded. The only existing annotation example is synthetic; Milestone 2 templates are drafts.

Actions: snapshot all existing work/assets; inspect/hash local video candidates; decode original USA source and create a clearly labeled AI-inspection contact sheet including historically person-detected frames, without assigning labels; validate existing bundles/templates using existing validators; report annotation coverage with zero reviewed frames. Prepare a three-scenario/300-dense-frame input contract, independent human review protocol, acceptance checklist and exact existing CLI commands. Do not run real identity metrics without trusted human GT. Run full P3 and relevant P2 offline regressions plus preservation checks.

New files only in this directory: PLAN.md, REPORT.md, INPUT_CONTRACT.md, HUMAN_WORKFLOW.md, benchmark-input.template.json, acceptance.json, annotation-readiness.json, media-inventory.json, existing-tool-validation.json, local-audit.py, audit-contact-sheet.jpg, audit-frame-index.json, p3-tests.txt, p2-tests.txt, preservation-before.json, preservation-after.json, checks.json. Contact sheet is an unannotated original-frame visual survey, not training/evaluation media or human ground truth. local-audit.py is an evidence-only script, reusing existing tools, not a replacement recorder/evaluator.

Stop condition: if suitable media or actual human-reviewed annotations are absent, final state PREPARED/BLOCKED. Do not create a fictional suite, fill in reviewer identities, or relabel predictions as truth. Existing algorithms/defaults/physical interfaces/professor materials/weights stay byte-identical. No network, training, hardware, commit or push.
