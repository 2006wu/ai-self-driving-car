# Project 2 AI Agent

The current student extension is **Do New v2**: read-only ModelB6 Diagnosis,
Vision Verification and Unified modes. See [DO_NEW_V2.md](DO_NEW_V2.md) for
architecture, evidence boundaries and detailed commands.

## Current files

| Purpose | Files |
| --- | --- |
| Numerical diagnosis | `diagnosis_agent.py`, `v2_evidence.py` |
| Vision and unified reports | `vision_agent.py` |
| Canonical evidence export | `prepare_v2.py`, ignored `artifacts/do-new-v2/` |
| Required professor baseline | `baseline_agent.py`, `professor_baseline.py`, `baseline_check.py` |
| Shared runtime model | `model_config.py` |
| Offline regression tests | `baseline_tests.py`, `model_config_tests.py`, `v2_tests.py` |
| Course framework review | [FRAMEWORK_REVIEW.md](FRAMEWORK_REVIEW.md) |

On 2026-10-12, the superseded v1 Evidence Agent, its export script and dedicated
tests were removed, along with its local exports and Python bytecode cache.
The v1 source remains in Git history at `e1a1bc5`. Historical results and
commands in the audit/experiment log describe that earlier revision.
ModelB6 Steps 5–10 are distinct experiments used by v2, not obsolete versions.
The course baseline and its compatibility adapter remain required.

## Environment

Use the isolated Python 3.11 environment, separate from ModelB6 Python 3.8
and Project 1/OpenPilot. Existing locked dependencies are unchanged.

```sh
/usr/local/bin/python3.11 -m venv projects/project2/agent/.venv
projects/project2/agent/.venv/bin/python -m pip install -r projects/project2/agent/requirements.txt
projects/project2/agent/.venv/bin/python -m pip check
```

`model_config.py` supplies the default runtime model (`gemini-3.8-flash`), with
an optional `GEMINI_MODEL_ID` override. The professor reference retains its
historical `gemini-2.5-flash` configuration. The AST adapter maps incompatible
Agno constructor arguments without executing professor top-level API calls.

## Offline commands (repository root)

```sh
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_check.py
projects/project2/agent/.venv/bin/python -m unittest discover -s projects/project2/agent -p '*_tests.py' -v
projects/project2/agent/.venv/bin/python projects/project2/agent/prepare_v2.py --verify
projects/project2/agent/.venv/bin/python projects/project2/agent/diagnosis_agent.py --offline
projects/project2/agent/.venv/bin/python projects/project2/agent/vision_agent.py --list-images
```

For a fresh evidence export, run `prepare_v2.py` without `--verify`; it reads
the existing Docker output volume and refuses to overwrite different exports.
Offline vision validates inputs only; it does not generate image analysis.

## Live commands (fish)

Use the configured terminal. If necessary, collect the key without echoing it:

```fish
if not set -q GOOGLE_API_KEY
    read --silent --prompt-str 'GOOGLE_API_KEY: ' GOOGLE_API_KEY
    set -gx GOOGLE_API_KEY $GOOGLE_API_KEY
end
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_agent.py
projects/project2/agent/.venv/bin/python projects/project2/agent/diagnosis_agent.py
projects/project2/agent/.venv/bin/python projects/project2/agent/vision_agent.py --image step6/usa/final/frame_00001.png
projects/project2/agent/.venv/bin/python projects/project2/agent/vision_agent.py --image step6/taiwan/best/frame_00001.png --unified
```

## Recorded acceptance status

[Audit §32](../../../docs/PROJECT2_AUDIT.md#32-baseline-complete-diagnosis-and-unified-waiting-on-quota-2026-10-08)
records the original course scope as 22/22 complete, including a completed
baseline response. The earlier v1 Evidence Agent integration also passed.
v2 USA/final Vision passed; the last recorded Diagnosis and Taiwan/best Unified
attempts remain unverified and are currently deferred. The latest recorded
2026-10-13 attempts identify Diagnosis 429 input-token-per-minute limits and
Unified 503 high demand; the older daily-quota errors are historical. See
[audit §33](../../../docs/PROJECT2_AUDIT.md#33-current-checkout-cleanup-and-report-delivery-2026-10-14).
The current suite passes **44/44 tests** (6 baseline + 3 model selection + 35 v2),
and existing canonical exports verify **26/26**. Historical 55-test acceptance
included the 11 removed v1-only tests. Cleanup performs no Gemini API calls.

[FRAMEWORK_REVIEW.md](FRAMEWORK_REVIEW.md) preserves the completed course review.
Multimodal observations and numerical diagnostics do not establish driving
accuracy, closed-loop safety or quantitative ground truth.
