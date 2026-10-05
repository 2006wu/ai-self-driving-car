# 5-Level framework review boundary

The local course file `course-materials/2509 AI Agent.docx` names “Building
Autonomous Agents 5-Level Framework” and asks the student to read it, but does
not contain the five level definitions or a local copy of that referenced text.
The repository therefore records the requirement without inventing a framework
summary. The external reference must be supplied or reviewed before claiming
that the five levels have been completed.

The original feature implemented here is intentionally narrower and testable:
the evidence agent uses a read-only local tool to summarize saved Project 2
gradient results, then lets Gemini present that structured evidence when a
runtime API key is available. It does not modify models, datasets, checkpoints,
or source files.
