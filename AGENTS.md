# Runtime policy

- Run application code, dependency installation, tests, model inference and training in Docker. Do not create or use host Python virtual environments, or install application dependencies on macOS.
- Use `scripts/dev.sh` for Project 2 Agent, ModelB6 and Project 3; use `scripts/openpilot.sh` for Project 1 replay/display.
- Keep the Python 3.8 ModelB6/OpenPilot runtimes separate from the Python 3.11 Agent and Project 3 runtimes.
- Preserve existing data/model/output volumes and external reference files. Do not remove host environments or Docker volumes as part of migration.
- Write new Project 3 results under a fresh `projects/project3/artifacts/` directory. Distinguish synthetic results, offline simulation and real hardware acceptance.
