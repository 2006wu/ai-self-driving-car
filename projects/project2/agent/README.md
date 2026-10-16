# Project 2 AI Agent

Current CLI: [執行／進度／逾時／紀錄／工具查證](RUNNING.md). Default live output is now concise Markdown; append `--json` for full JSON. Both original script paths and environment model override remain supported.

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
v2 USA/final Vision passed. Latest staged verify runs both COMPLETED:
Diagnosis4requiredtools + report29.301s; Unified2requiredtools + report6.857s.
Each has12 matching manifest entries; tool returns match canonical readers.
Selection is application-required, not autonomous. Reports are accepted only
with documented review corrections; raw results preserved. See audit §44.
The current suite passes **96/96 tests** (6 baseline + 3 model selection + 57 v2/CLI + 30 runtime),
and existing canonical exports verify **26/26**. Historical 55-test acceptance
included the 11 removed v1-only tests. Cleanup performs no Gemini API calls.

[FRAMEWORK_REVIEW.md](FRAMEWORK_REVIEW.md) preserves the completed course review.
Multimodal observations and numerical diagnostics do not establish driving
accuracy, closed-loop safety or quantitative ground truth.

### Latest user receipt and CLI fix (2026-10-14)

Diagnosis and Taiwan/best Unified both returned provider **503 high demand** in
the latest user transcript; live acceptance remains pending. Unified now exits
with a concise error instead of a RuntimeError traceback. No API was called for
this change. See [audit §34](../../../docs/PROJECT2_AUDIT.md#34-user-reported-dual-503-and-unified-cli-error-handling-2026-10-14).

### Successful Diagnosis execution with 3.5 override (2026-10-14)

The latest user receipt completes Diagnosis using `gemini-3.5-flash-lite`, with
six tool calls reporting no errors. Execution PASS; factual report acceptance
requires corrections identified in [the review](LIVE_REVIEW_20261014.md). Unified
remains pending. The default model is unchanged; this was a command-scoped override.

### Subsequent Unified completion and review (2026-10-14)

Taiwan/best Unified also completed using the 3.5 override. Execution PASS; numerical
comparison was not demonstrated, and model-lead/lane claims need correction. Full
acceptance remains pending; see the [combined review](LIVE_REVIEW_20261014.md).
New runs emit tool names/error flags and the Unified default prompt explicitly
requests sourced numerical comparison. No new live call was made for this fix.

### Both report paths corrected before manual retry (2026-10-14)

Diagnosis now receives and returns `verified_reference`: exact source-qualified
values and metric definitions distinguishing intervention conditions and encoder
activation magnitude vs input-dependent differences. Unified receives and returns
`numerical_reference` scoped to the authenticated image domain/checkpoint. It
rejects empty/placeholder comparison or a comparison without the corresponding
source path and metric key. These are provenance/structure checks, not complete
semantic verification; generated prose still requires review. Local reference
reads are separate from model-selected `tools` traces. No provider call was made
for the fix. Ten new offline tests pass (59 total); new live acceptance is pending.
The same command-scoped `GEMINI_MODEL_ID=gemini-3.5-flash-lite` commands apply.

### Diagnosis retry and numerical table guard (2026-10-14)

The retry's verified reference matches local data but its generated table contains
a Taiwan count copied from USA; causal/deployment overclaims remain unaccepted.
Diagnosis now returns a code-rendered `verified_evidence_table`, checks supported
scoped numeric Markdown rows, and exposes `content_validation` as human-review
required. The actual copied-count receipt is rejected offline. Context includes
claim classifications/causal limits/allowed action; no duplicate table is requested
from the model. This is not general semantic validation. Five added tests pass,
64 total; no API call was made. See audit §38 / combined live review.

### Latest Unified retry review (2026-10-14)

The new receipt matches the full Taiwan/best numeric reference and includes a
source-qualified comparison: execution/numeric-reference comparison PASS. It
still overinterprets spatial jitter as averaged away over the clip; full content
acceptance remains partial. Model-selected tools are empty; evidence came from
explicit preflight context. See combined review / audit §39. No API was called
or software changed for this review.

### Latest Diagnosis bounded-summary acceptance (2026-10-14)

The newest Diagnosis response passes bounded content review: full reference/table
match, seven correct classifications and appropriate causal/action limits. Zero
model-written table rows is expected because the verified table is separate.
Runtime still conservatively requests human review; the performed review is in
LIVE_REVIEW_20261014.md / audit §40. Tools remain empty (preflight-context summary,
not model-selected tool execution). No new API or software change for this review.

### Runtime/output optimizations (2026-10-14)

Progress/elapsed time, isolated worker budgets, finite transient retries, automatic
redacted records/manifests, concise fact/interpretation/unknown report sections and
optional meaningful tool-verification mode are implemented. Explicit spatial-vs-
temporal limits and a targeted averaging-overclaim check protect Unified. SDK/model/
Agent hidden retries are disabled. See RUNNING.md and audit §41 for parameters,
record structure and honest limits. Current offline suite 87/87; no live request
was made for these optimizations; model/dependency defaults remain unchanged.

### Optimized CLI user-run acceptance (2026-10-14)

Real Diagnosis/Unified success-path runs complete in 5.355s/6.667s on first
attempt; both manifests match 10/10 files. Preload-mode progress/persistence/output
is verified, not autonomous verify-mode or live retry behavior. Unified's numeric
facts match, but its Step6 median qualifier is wrong. Per-field reductions and a
targeted guard now address that wording (89/89 offline tests); no new API call.
Original successful run records are preserved; see audit §42 and combined review.

### Required-tool protocol revision (2026-10-14, 22:55 receipts)

Both verify receipts FAILED: Diagnosis lacks gradient/encoder calls; Unified
has no tool calls. Earlier preload replies completed. These are distinct evidence
levels. Revised verify selects each required tool in the application and requires
a model-issued function call with an actual result before generating the final
report. It does not demonstrate autonomous tool selection. The final Unified
structured-output request has no tools. Current suite96/96 (7 new regressions);
revised live NOT VERIFIED. See RUNNING.md and audit §43.

### Staged verify live receipts (2026-10-14,23:06–23:07)

Both required-tool protocols completed with current matching source hashes.
Assistant-assisted content review corrects fresh-gradient provenance and
still-image motion/lane wording in separate reviewed reports, preserving raw
outputs. No code changes/new APIcalls or repeat offline tests for this review.
Same-sample success-path retesting is not needed. See audit §44.
