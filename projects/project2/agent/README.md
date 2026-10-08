# Project 2 AI Agent

Student-owned Python 3.11 environment, separate from Project 1/OpenPilot and
ModelB6 Python 3.8. Current evidence:
[PROJECT2_AUDIT section 32](../../../docs/PROJECT2_AUDIT.md#32-baseline-complete-diagnosis-and-unified-waiting-on-quota-2026-10-08).

## Do New v2 extension

[DO_NEW_V2.md](DO_NEW_V2.md) documents the new read-only Model B6 Diagnosis,
Vision Verification and Unified modes, canonical artifacts, safety boundaries,
architecture, tests and fish live commands. Original baseline/Evidence runners
remain intact. v2 offline tests pass **55/55**. The user-submitted USA/final
Vision live report is verified PASS; Diagnosis and Taiwan/best Unified returned
503; latest retries returned 429 daily quota exhaustion (audit §§31–32). They
remain pending quota reset. The original Baseline Agent now has a completed
live response (audit §32), so the original 22-group course scope is complete.
No new API call was made here. Wait for quota reset before retrying Diagnosis
and Unified; this is distinct from the earlier temporary high-demand failures.
Vision attaches authenticated PNG bytes; offline mode does not fabricate analysis.

## Validated environment

Python **3.11.4**, pip **26.2.1**; system site packages are excluded.
All **63** locked versions match the installed environment; `pip check` passes.
Agno 3.1.1, Google GenAI 2.28.0, duckduckgo-search 8.1.1, ddgs 9.16.0,
YFinance 1.7.0, Pydantic 2.13.5, pydantic-settings 2.15.0, pydantic-core 2.46.5.

If recreating the ignored environment, from the repository root:

```sh
/usr/local/bin/python3.11 -m venv projects/project2/agent/.venv
projects/project2/agent/.venv/bin/python -m pip install -r projects/project2/agent/requirements.txt
projects/project2/agent/.venv/bin/python -m pip check
```

Do not install Agent dependencies into Project 1 or ModelB6.

## Professor baseline compatibility

Reference: ignored `external/aJLL/Agent/agent.py`, unchanged. It defines six
Gemini `gemini-2.5-flash` examples with web, financial, reasoning and image
tools. Only `agno2` has an active response call: its literal travel request.
`baseline_agent.py` runs that request with ReasoningTools using the professor
configuration through `professor_baseline.py`. It no longer substitutes an
unrelated explanation prompt.

### Reference model versus student runtime

| Purpose | Model ID |
| --- | --- |
| Professor/reference configuration (historical, unchanged) | `gemini-2.5-flash` |
| Current default student compatibility runtime | `gemini-3.8-flash` |
| Optional runtime override | `GEMINI_MODEL_ID` |

The user executed the live baseline and reached Gemini with a runtime key.
The API returned **404 NOT_FOUND**, stating
that 2.5 Flash is no longer available to new users and naming
`models/gemini-3.8-flash` as the replacement. This is an external model
lifecycle compatibility issue; it does not invalidate the baseline concept.
Google's [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
also lists `gemini-3.8-flash` as a stable model ID.

After that compatibility update, the user reports repeated live attempts of
**both** baseline_agent.py and evidence_agent.py with the printed runtime
`gemini-3.8-flash`. Both reached Gemini and returned **503 UNAVAILABLE**, with
the provider reporting temporary high demand. These are user-provided live
results; no raw provider log or secret is stored here. They establish that the
credentials/request path reach provider/model handling. They do not establish
a successful end-to-end response or all account capabilities. A subsequent
terminal transcript now shows baseline `think`/`analyze` calls, two reasoning
steps and a partial answer (displayed response timer: 349.8 s), together with
503 and `Error in Agent run`. The captured answer stops during its first table.
Evidence Agent shows 503 and only the input message, without a tool call or
answer. Baseline tool-flow progress is now observed; neither run is complete.

**Latest live status:** Evidence Agent integration PASS. The subsequent receipt
shows `gemini-3.8-flash`, `summarize_p2_evidence()`, all eight final/best metrics
matching saved JSON, 144 records/18 samples and a complete answer (displayed
response timer 316.7 s), with no error line. Its “machine precision zero”
wording and causal state-dominance claim are too strong: the evidence supports
strong local image-gradient attenuation, not numerical zero or universal
state dependence. See audit §27. At that point, Baseline still needed a clean
complete response beyond its earlier 503/partial answer. Missing credentials
and the stale model ID are resolved; the subsequent successful Baseline run is
recorded in audit §32.

A prior baseline retry (2026-10-06, user-submitted output) again reports
503 UNAVAILABLE/high demand and Error in Agent run. It shows one `think`
entry but no final answer. This is historical. On 2026-10-08, the user supplied
a complete baseline run with visible `think`/`analyze` calls and a full travel
planning answer, closing the baseline live acceptance. See audit §32.

The newest receipt (audit §28) shows `think`/`analyze`, no visible ERROR/503,
and a Response timer of 67.2 s, but its answer contains only an unfinished
opening sentence. The model-ID header is absent. Full baseline completion
remains unverified; the receipt does not justify claiming another 503 failure.
First establish whether the pasted response is complete or a copied fragment,
and inspect any existing remaining output before requesting another API run.

`model_config.py` selects the current runtime default for both the baseline
AST adapter (all six Gemini constructors) and `evidence_agent.py`. It reads
`GEMINI_MODEL_ID` when constructing the model, trims whitespace and rejects
empty overrides. Model selection is separate from the runtime secret
`GOOGLE_API_KEY`; no key is read, printed or persisted by the model selector.
The reference IDs are inspected independently for historical validation.

The adapter reads the local AST and evaluates only approved constructor
literals; it never executes professor top-level response calls. Agno 3.1.1
rejects old YFinance switches (`stock_price`, `analyst_recommendations`,
`company_info`, `company_news`); they map to `enable_*`. Old `agent_id`
maps to `id`, `add_datetime_to_instructions` to
`add_datetime_to_context`, and removed display flag `show_tool_calls` is
omitted. Professor source is unchanged.

```sh
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_check.py
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_tests.py
projects/project2/agent/.venv/bin/python projects/project2/agent/do_new_tests.py
projects/project2/agent/.venv/bin/python projects/project2/agent/model_config_tests.py
```

All six examples construct offline. Imports, active prompt/model/tool
selection and finance function registration pass. **6 baseline + 11 Do New +
3 model-selection tests = 20 PASS**, all offline. Expected live behavior is a
reasoned travel response using the baseline tools. The earlier baseline trace contains tools and partial output with 503.
The subsequent Evidence receipt establishes successful live integration with
matching tool facts and a complete answer; its interpretation caveat remains.
No additional API call was made to assess these reports.

Agno can display accumulated content after a streaming error, so a Response
panel alone is insufficient. The latest Evidence receipt has no error and a
complete answer; the earlier baseline receipt does not establish completion.
Only the baseline now requires a clean completed live response.

## Original “Do New”: actual evidence → read-only tool → Agent

The baseline supplies general-purpose tools. This extension supplies
`summarize_p2_evidence`: structured extraction of saved P2.9 final/best loss
and image/state gradients. `build_agent()` registers the function and
ReasoningTools on Gemini. Offline tests verify registration, not model-generated
tool invocation.

Allowed roots are exactly host `artifacts/p29-gradient-audit` and Docker
`/output/p29-gradient-audit`; arbitrary `/tmp` and `/output` directories
are rejected. Missing/malformed/incomplete/nonfinite evidence and escaping
symlinks fail closed. The tool has no write, inference, training or checkpoint
operation.

The host venv cannot directly see the Docker volume. Export only the small
verified summaries using the fixed read-only collector:

```sh
projects/project2/agent/.venv/bin/python projects/project2/agent/prepare_demo.py
projects/project2/agent/.venv/bin/python projects/project2/agent/evidence_agent.py --offline
projects/project2/agent/.venv/bin/python projects/project2/agent/prepare_demo.py --verify
```

The export validates P2.9/P2.10 manifests, coverage and numerical aggregates.
Identical exports may be reused; differing exports are never overwritten.
Ignored `artifacts/` holds the summaries, P2.10 verification, a 269-file
integrity snapshot and `offline_demo.json`. No binaries or professor source
are exported.

The executed demo has `mode: offline_tool_only`, `gemini_executed: false`,
and extracts **144 P2.9 records / 18 samples**:

| Saved metric (median) | Final | Best |
| --- | ---: | ---: |
| Supervised loss | 30.77054787 | 29.91626549 |
| Image gradient RMS | 9.774764271e-15 | 2.579593744e-15 |
| State gradient RMS | 0.1906711418 | 0.2902863671 |
| Image/state RMS ratio | 6.735230071e-14 | 2.217528308e-14 |

These are sample diagnostic medians, not epoch losses or driving accuracy.
P2.10 verification separately reports **P2.10-A**, 54 trials and 18 cached
samples. The Agent tool currently extracts P2.9; it does not pretend to expose
P2.10 metrics.

Demo SHA-256:
`946ea6b16734ad0e73dac4eba4d930b82323b3fe060ccb9956f7c74f3b82fef1`.
This is an executed **tool** demonstration; Gemini interpretation is blocked.

## Live commands (user terminal, fish)

After the export, enter the key through a hidden prompt. Do not paste it into
chat, command arguments, repository files, logs or screenshots:

```fish
cd /Users/2006wu/Desktop/ai-self-drive-car-ws
set -gx GEMINI_MODEL_ID gemini-3.8-flash
if not test -n "$GOOGLE_API_KEY"
    read --silent --global --export --prompt-str 'Gemini API key: ' GOOGLE_API_KEY
else
    set -gx GOOGLE_API_KEY "$GOOGLE_API_KEY"
end

# A. Professor baseline via the student compatibility adapter
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_agent.py

# B. Original read-only evidence Agent
projects/project2/agent/.venv/bin/python projects/project2/agent/evidence_agent.py

set -e GOOGLE_API_KEY GEMINI_MODEL_ID
```

If the key is already available in fish it is exported without displaying it;
otherwise `read --silent` collects it without a literal key in command history.
The explicit model variable is optional; omitting it selects the same default.
Both live runners print only the selected model ID before invoking Gemini.

Record only model name, success/failure, tool behavior and a sanitized response
summary. Do not publish raw provider diagnostics without checking them. These
calls require working Gemini access and network.

## Framework requirement

**COMPLETE.** The assigned Paolo Perrone article was read through the public
URL with authorization in the current task. [FRAMEWORK_REVIEW](FRAMEWORK_REVIEW.md)
contains the student review and repository-based mappings. Both implementations
are primarily Level 1; their reasoning tools alone do not establish long-term
memory. This closes the former source/review blocker. Only successful live
baseline completion remains pending within the audited course scope.
