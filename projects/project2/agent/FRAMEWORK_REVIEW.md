# Building Autonomous Agents: five-level review

## Assigned Source

- **Title:** AI Agents in 5 Levels of Difficulty (With Full Code Implementation)
- **Author:** Paolo Perrone
- **Published:** May 19, 2025, Data Science Collective
- **Source:** [assigned article](https://medium.com/data-science-collective/ai-agents-in-5-levels-of-difficulty-with-full-code-implementation-15d794becfb8)
- **Reviewed:** October 6, 2026. Public access exposed all five sections.

The source matches the hyperlink in local `course-materials/2509 AI Agent.docx`
and the exact assignment confirmed by the user. The current task authorizes
public access, resolving the earlier local-body gate. This is an original
student review; neither article code nor a full article copy is included.

**Framework requirement: COMPLETE.**

## Five Levels

The names below abbreviate the verified section headings. Capabilities and
representative components summarize the assigned article.

| Level | Name | Main capability | Addition over prior level | Components | Use |
| --- | --- | --- | --- | --- | --- |
| 1 | Tools and instructions | Model selects actions. | Callable tools. | Agent, search tool. | Automate bounded tasks. |
| 2 | Knowledge and session memory | Retrieve context; retain interaction history. | Retrieval and session storage. | Hybrid index, reranker, SQLite. | Reuse relevant context. |
| 3 | Long-term memory and reasoning | Recall across sessions; reason through decisions. | Reusable user memory plus reasoning. | Memory database, reasoning tools. | Maintain task continuity. |
| 4 | Multi-agent teams | Coordinate specialists. | Routing and delegation. | Leader, member agents. | Divide broad tasks. |
| 5 | Agentic systems | Serve persistent asynchronous workflows. | Job/progress management. | API, workers, state store, streaming. | Support long-running requests. |

Source: [Perrone's five sections](https://medium.com/data-science-collective/ai-agents-in-5-levels-of-difficulty-with-full-code-implementation-15d794becfb8).

## Progression

Tools/instructions → retrieval/session state → durable memory/reasoning →
specialist coordination → production workflows. Each transition adds system
capability and infrastructure responsibilities. Model intelligence alone does
not establish a level.

## Professor Baseline Mapping

**Most defensible placement: primarily Level 1, with a reasoning capability.**

Inspection of the preserved `external/aJLL/Agent/agent.py` finds six separate
Agent constructors. Their model, instructions and tool configurations include
Gemini, web search, finance, reasoning and image/media examples. Only the
reasoning-based travel request is active. These are examples, not a coordinated
team: no Team/member routing or delegation is configured. No knowledge index,
persistent session database or long-term memory configuration is present.

[professor_baseline.py](professor_baseline.py) adapts constructor keywords and
the model ID; [baseline_agent.py](baseline_agent.py) executes the active prompt.
The professor/reference ID remains historically `gemini-2.5-flash`; student
runtime defaults to `gemini-3.8-flash` with optional `GEMINI_MODEL_ID`.
A newer model ID changes API compatibility, not the architecture classification.

ReasoningTools is insufficient evidence for Level 3 because this implementation
does not configure its defining cross-session memory architecture. Separate
example agents and media support likewise do not establish Levels 4 or 5.
This placement is an engineering inference from the inspected configuration,
not an author-provided classification or a claim of successful live behavior.

## Student Do New Mapping

**Most defensible placement: primarily Level 1, with a specialized evidence tool.**

[evidence_agent.py](evidence_agent.py) constructs one Gemini Agent with explicit
instructions, ReasoningTools and `summarize_p2_evidence`. The function reads
a fixed completed P2.9 JSON summary, checks permitted directories and required
finite metrics, then returns structured final/best facts. The registered tool
can ground the response in actual experiment evidence.

This fixed JSON extraction does not configure a corpus retrieval/index pipeline,
conversation database or persistent Agent memory. Durable experiment files are
records of ModelB6 results; they do not preserve this Agent's conversational
state. The feature therefore does not establish the article's Level 2
knowledge/session-memory architecture. It also has no member agents,
delegation, background job service or progress/state management.

[do_new_tests.py](do_new_tests.py) verifies extraction, read-only behavior,
failure boundaries and actual tool registration offline. Those tests support
the architecture analysis. A subsequent live receipt verifies a Gemini-selected
evidence-tool call, eight matching metrics and a complete answer. Integration
passes; scientific interpretation caveats are recorded in
[the audit](../../../docs/PROJECT2_AUDIT.md#27-evidence-agent-live-validation-2026-10-06).
This live evidence does not change the Level 1 classification.

## Design Reflection

### Do New v2 extension

[Do New v2](DO_NEW_V2.md) adds specialized numerical tools and genuine Gemini
image input in separate diagnosis/vision/unified modes. These are primarily
Level 1 tool/instruction configurations, not a team, persistent Agent memory
or production workflow. The unified mode is one Agent with tools and an image;
multiple runner files do not establish Level 4. Offline implementation tests
do not establish successful live multimodal behavior.

The evidence reporter has a narrow engineering purpose: expose reproducible
numeric facts and their limits. Read-only access, explicit paths, structured
output and small tests make its behavior reviewable. Additional autonomy or
memory would need a concrete reporting requirement to justify their cost.
A higher framework level alone does not improve this assignment's evidence
quality. The chosen scope protects checkpoints/data and avoids unnecessary
actions while preserving useful Agent/tool integration.
