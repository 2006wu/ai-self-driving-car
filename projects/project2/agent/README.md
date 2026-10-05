# Project 2 AI Agent

This is the isolated student-owned environment for the Project 2 Agent. It is
separate from the OpenPilot/ModelB6 Python 3.8 runtime.

The professor reference remains under the ignored `external/aJLL/Agent/` tree.
The reference baseline uses Agno, Gemini `gemini-2.5-flash`, YFinanceTools,
DuckDuckGoTools, ReasoningTools and an image-to-text example. It expects the
API key at runtime through `GOOGLE_API_KEY`; no key belongs in this repository.

## Environment

The local Python 3.11 virtual environment is ignored. From the repository root:

```sh
/usr/local/bin/python3.11 -m venv projects/project2/agent/.venv
projects/project2/agent/.venv/bin/python -m pip install -r projects/project2/agent/requirements.txt
```

`requirements.txt` is generated from the tested environment after installation.
Do not install these packages into the Project 1 compute container.

## Baseline checks

Run the no-network import and source audit first:

```sh
projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_check.py
```

The optional live baseline requires a runtime key and network access:

```sh
GOOGLE_API_KEY=provided-at-runtime \
  projects/project2/agent/.venv/bin/python projects/project2/agent/baseline_agent.py
```

The live command is intentionally not run without an authorized key. Its output
is diagnostic only and is not written to the repository.

## Original “Do New” feature

`evidence_agent.py` adds a read-only Project 2 evidence reporter. Its tool
extracts saved P2.9 metrics from `/output/p29-gradient-audit/` and lets Gemini
format the result. It never loads a checkpoint, runs inference, writes output,
or changes source/data. `do_new_tests.py` exercises the tool without a network
or API key. The live wrapper remains optional and requires `GOOGLE_API_KEY` at
runtime.

The local course document names the five-level framework but does not include
its definitions; `FRAMEWORK_REVIEW.md` records that evidence boundary.
