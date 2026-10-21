# Project 3 commands and verification — 2026-10-21

Use the repository-root [ordered guide](../README.md) for complete recipes.
All supported application commands use the Python 3.11 Project 3 Docker service;
outputs belong under a fresh `projects/project3/artifacts/` directory. Existing
volumes, local media and reference files are preserved. Synthetic results,
offline simulation and real hardware acceptance remain distinct.

```sh
./scripts/dev.sh build project3
./scripts/dev.sh p3 check
./scripts/dev.sh test-p3
```

The setup/run/verify wrappers still delegate to `scripts/dev.sh` (`build project3`,
`p3`, `test-p3`). Its `p3-display`, `p3-stream` and `p3-python` cases also exist.
`p3-display run ... --display` uses VNC; `p3-stream` delegates to `p3.cli run`
with a `stream:` source and forwards run flags. The Mac capture helper supports
`--device`, `--size`, `--fps`, `--port` and `--help`; it requires existing ffmpeg
on the Mac and does not move Python inference out of Docker.

## CLI help and documented flags checked

Every parser/subcommand below was invoked with `--help` using the user-authorized
existing `/workspace/scratch/venv-p3/bin/python` from `projects/project3`, because
Docker is unavailable on this box. This checks the code's CLI contracts, not a
new Docker/model/hardware run. Module-level help was checked as well as each
listed subcommand. Flags below include those in examples and explanatory text.
Positionals are shown in parentheses. Research modules have prefix `p3.research.`.

| Module / subcommand | Verified arguments used by these docs |
|---|---|
| `p3.cli check` | `--output` |
| `p3.cli run` | `(source)`, `--output`, `--track`, `--display`, `--max-frames`, `--max-seconds`, `--simulate-follow`, `--target-id`, `--no-record`, `--camera` |
| `p3.cli benchmark` | `(source)`, `--output`, `--samples`, `--warmup`, `--resolution`, `--confidence`, `--provider`, `--track`, `--simulate-follow` |
| `p3.cli tracking-fixtures` | `--output` |
| `p3.cli tracking-eval` | `(source)`, `--iou`, `--output` |
| `offline record` | `(source)`, `--output`, `--max-frames`, `--media-root` |
| `offline validate` | `(dataset)`, `--output`, `--media-root`, `--require-media`, `--verify-pixels` |
| `offline template` | `(dataset)`, `--output` |
| `offline extract` | `(dataset)`, `--output`, `--frames`, `--media-root` |
| `offline import-mot` | `(dataset source)`, `--output`, `--target-person-id`, `--human-verified`, `--annotator`, `--reviewer`, `--frame-offset`, `--frame-count`, `--box-origin`, `--clip-boxes` |
| `offline validate-annotations` | `(dataset annotations)` |
| `offline evaluate` | `(dataset)`, `--output`, `--annotations`, `--trackers` (`all` = greedy_iou/hungarian/kalman_iou) |
| `tracker_benchmark` | `--output` |
| `pid_sim` | `--controller`, `--gains`, `--scenarios`, `--steps`, `--seed`, `--output` |
| `control_dataset build-sim` | `--output`, `--controllers`, `--episodes-per-scenario`, `--seed`, `--steps`, `--scenarios`, `--perturb`, `--ratios` |
| `control_dataset build-recorded` | `--events`, `--output`, `--media-root` |
| `control_dataset validate`, `control_dataset stats` | `(directory)` |
| `bc_baseline train` | `--dataset`, `--model` (ridge/mlp), `--output`, `--seed`, `--teacher`, `--all-states` |
| `bc_baseline eval-offline` | `--dataset`, `--model-file`, `--output` |
| `bc_baseline eval-closed-loop` | `--model-file`, `--output`, `--steps` |
| `body_interface replay-sim` | `--scenario`, `--controller`, `--steps`, `--output`, `--transport` (mock/dry_run; real is refused) |
| `body_interface replay-log` | `(file)`, `--output`, `--transport` |
| `real_session to-control-dataset` | `(session_dir)`, `--output` |
| `run2_acceptance` | `(session_dir)`, `--report`, `--json`, `--max-frame-age-p95`, `--max-stop-latency`, `--max-drop-fraction`, `--max-id-switches`, `--max-lost-segments` |
| `report3_figures` | `--output`, `--draft` (legacy reports destination; use explicit artifacts output in Docker) |
| `export` | `(source destination)`; destination parent must already exist |
| `validate_vision.py` | `--output` |
| `reports/ai-control-milestone3-20261020/local-audit.py` | `--output`; needs Project 3 on PYTHONPATH and repository-root working directory |
| `unittest discover` | `-s`, `-p`, `-v` |

`./scripts/dev.sh --help` and the Mac helper's `--help` succeeded. The dev script
case names and wrapper forwarding were also inspected directly. Regeneration of
the contact sheet now uses `p3-python -c` with an explicit repository-root chdir;
Compose supplies Project 3 PYTHONPATH. No Docker command was executed here.

## Historical script limits and documentation mismatches fixed

- `audit.py`, `evaluate.py`, `summarize.py` have no argparse/help interface.
  `--help` attempts in isolated temporary copies exited 1 on missing local inputs;
  source inspection confirmed that the argument is ignored. They must not be
  used as safe help commands against the real evidence tree. `audit.py` writes
  fixed `evidence/source-audit.json`; `evaluate.py` writes fixed
  `evidence/supplemental.json` and requires CoreML. `summarize.py` can rewrite
  dated validation reports through `report_validation.py`, or current STATUS.
  The README now directs new measurements/figures to configurable-output tools.
- Replaced outdated native-venv reproduction instructions with Docker commands.
  Historical native/CoreML measurements remain historical, not Linux Docker claims.
- Converted body replay and Run2 example commands to `./scripts/dev.sh` and moved
  contact-sheet regeneration behind the same wrapper with the correct working directory.
- Added the missing parent-directory creation before the JSONL export recipe;
  `export` itself does not create directories. `report3_figures --draft` targets
  historical `reports/`; Docker users must select a fresh artifacts output.
- Removed stale current-status claims of 107/163/203 tests and blanket webcam
  BLOCKED text. Historical reports retain their original counts; Mac smoke is
  separated from full manual acceptance and the present 286-test suite.
- Clarified that new pipeline logs provide Run2 age/stop/drop measurements;
  stop latency needs an operator stop, and continuity needs human identity labels.
  PID/BC descriptions now acknowledge the too-close gate and mock body boundary.
- Every referenced Project 3 `test_*.py` file exists, including the documented
  stream/PID/BC/figure patterns; no test-file or test-name substitution was needed.
  Repository links, script/config/fixture/sample-bundle paths were checked.
  Original model/course/reference assets and `artifacts/` media are local prerequisites;
  removed large evidence paths are explicitly documented as regenerable.
  Final checks covered **56 Docker CLI examples, 47 local Markdown links and
  12 distinct Project 3 test filenames**, with no unresolved flag/link mismatch.

## Test result and historical evidence

Executed from `projects/project3` (the explicit docs-check exception):

```sh
/workspace/scratch/venv-p3/bin/python -m unittest discover -s tests
```

Result: **Ran 286 tests in 11.898s — OK (skipped=8)**. No dependency installation,
model training, device access, commit/push or Python behavior changes occurred.
For supported user reproduction run `./scripts/dev.sh test-p3` from repository root.

Original source audit, downloads, volume extraction and native benchmarks date
from 2026-10-14. Their JSON/test evidence remains in this directory; the exact
Drive reference was parsed/AST-tested with injected APIs, never run on hardware.
The [2026-10-16 validation report](validation-20261016/REPORT.md) and
[2026-10-21 Docker report](docker-20261021/RESULTS.md) preserve their executed
commands and scope. They do not imply any new hardware acceptance.
