# Executed verification commands (2026-10-14)

Initial inspection: git rev-parse --show-toplevel; git branch --show-current;
git rev-parse HEAD; git status --short; git remote -v. Branch develop, clean,
HEAD 0098f886e078cacbe08eb2d1282922cd78b5b1dc. Read original DOCX XML/relationships
using zipfile/ElementTree; read reference Python as text/AST, not import side effects.
Source/runtime inventory in source-audit.json and environment.json.

From repository root, environment was created with `/usr/local/bin/python3.11 -m
venv projects/project3/.venv`, then installed numpy 1.26.4, onnx 1.17.0,
onnxruntime 1.20.1, opencv-python 4.10.0.84 and psutil 6.1.1. Resolved transitive
versions saved by pip freeze to requirements.txt; pip check succeeded.

The image and exact UI reference downloads and read-only volume extraction are
shown in ../README.md. Initial `uc` download was an HTML warning, not Python;
the confirmed Drive download returned a valid 3307-byte Python file. It was
parsed and AST main exercised only through injected test doubles. Original
comments containing historical personal configuration were not copied to docs.

Executed from projects/project3:

```sh
.venv/bin/python -m p3.cli check --output evidence/environment.json
.venv/bin/python audit.py
.venv/bin/python -m unittest discover -s tests -v > evidence/tests-final.txt 2>&1
.venv/bin/python -m p3.cli run artifacts/bus.jpg --output artifacts/image
.venv/bin/python -m p3.cli run artifacts/inputs/usa.hevc --max-frames 20 --output artifacts/video
.venv/bin/python -m p3.cli run artifacts/bus.jpg --track --output artifacts/final-preview
.venv/bin/python -m p3.cli run artifacts/inputs/usa.hevc --track --max-frames 2000 --output artifacts/full-video
.venv/bin/python -m p3.cli benchmark artifacts/bus.jpg --samples 30 --output evidence/final-image.json
.venv/bin/python -m p3.cli benchmark artifacts/inputs/usa.hevc --samples 20 --output evidence/final-video-short.json
.venv/bin/python -m p3.cli benchmark artifacts/inputs/usa.hevc --samples 120 --output evidence/final-video-long.json
.venv/bin/python -m p3.cli benchmark artifacts/bus.jpg --samples 30 --confidence .5 --output evidence/final-image-conf50.json
.venv/bin/python -m p3.cli benchmark artifacts/bus.jpg --samples 30 --resolution 640x480 --output evidence/final-image-small.json
.venv/bin/python -m p3.cli benchmark artifacts/bus.jpg --samples 30 --resolution 1920x1080 --output evidence/final-image-large.json
.venv/bin/python -m p3.cli benchmark artifacts/bus.jpg --samples 30 --provider CoreMLExecutionProvider --output evidence/final-coreml.json
.venv/bin/python evaluate.py
```

Full-video run occurred before the final HUD text alignment revision; final
benchmarks and final-preview use final source hashes in their environment records.
Earlier benchmark-*.json are retained first measurements, not additional claimed
independent acceptance criteria. Model weights and detection/tracking algorithm
were unchanged between those runs. Supplemental probes use original model math.

Regression commands from root:

```sh
projects/project2/agent/.venv/bin/python -m unittest discover -s projects/project2/agent -p '*_tests.py' -v
# output saved to projects/project3/evidence/p2-regression.txt
docker compose -f docker/docker-compose.yaml config --quiet
git diff --check
```

P1/P2 services were absent at initial docker ps inspection. Their six named
volumes and existing images were present. Full P1 replay/UI and P2 TF retraining
were NOT executed; no runtime regression PASS is inferred. Hash preservation
check compares pre-task tracked files plus original course/aJLL content.

Camera capability was queried through AVFoundation authorization/device enumeration
using xcrun swift; no camera session or settings modification was requested by
that inspection. See camera-capability.txt and STATUS.md for actual result.
