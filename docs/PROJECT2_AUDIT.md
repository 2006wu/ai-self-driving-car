# Project 2 readiness audit

Audit date: 2026-10-04. This is an inspection of the current checkout, Docker metadata, repository documentation, and local course files. No training, package installation, container startup, volume write, commit, or push was performed. Historical Project 1 validation is cited as historical evidence; the Project 1 workloads were not rerun for this audit.

## 1. Executive summary and readiness

**BLOCKER — the professor source is missing from its expected checkout location, but a preserved local duplicate is available for inspection.** `external/aJLL/ModelB6/` contains only empty `saved_model/` and `output/` directories; `external/aJLL/Agent/` is empty. The entire ignored `external/aJLL/` tree currently has one `.pyc` file, and `external/installop-assets/` is empty. The preserved `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/` contains 181 files, including the ModelB6 and Agent source and a 53 MB `supercombo079.keras`. The audit below read this duplicate without copying or modifying it. Restore/verify it to a durable ignored location before any Project 2 execution; `/private/tmp` is not durable project storage.

**HIGH — preserve Project 1.** The current Compose design uses named volumes for OpenPilot and data. Docker lists all four expected volumes and both project images, but `docker compose ps -a` lists no project containers. Thus volume *existence* was checked, while their current contents and runtime health were not. Project 1's documented replay results remain historical evidence, not a fresh pass today.

The course plan assigns Steps 5–6 and an AI Agent to Project 2. The local Steps 5–6 slides and Agent document support the broad requirements in `docs/PROJECT2.md`. The preserved Python files also reveal concrete baseline issues that the slides do not show. Steps 7–8 and the document's later robot examples are outside the stated Project 2 scope.

## 2. ModelB6 architecture and evidence limits

The preserved source confirms this pipeline: `serverB6.py` selects files and serves batches over ZeroMQ PUSH on **5557** (training) or **5558** (`--validation`); `train_modelB6.py` connects with PULL, builds `modelB6.py`, concatenates 12 teacher targets into 2383 values, applies custom loss and Adam, and writes `saved_model/B6.keras`, `saved_model/B6BW.hdf5`, `output/B6Loss.png`, and `output/B6LossT.txt`. `datagenB6.py` uses `supercombo079.keras` to generate `outSC.h5` in each dataset directory if absent. `modelB6.py` builds an EfficientNet-like convolutional trunk, RNN/state path, three output forks, and one concatenated 2383-value output. `parserB6.py` interprets the 12 slices as path/lane/lead/longitudinal/meta/pose/state values. `simulatorB6.py` loads `B6.keras`, transforms video frames, predicts, slices, parses, and plots. `hevc2yuvh5.py` prepares `yuv.h5` from `video.hevc`; `cameraB3.py` and `lanes_image_space.py` provide camera/plot transformations. `pose_plot.py` is ancillary analysis, not on the basic training path.

The actual generator uses float32 model inputs `(batch,12,128,256)`, `(batch,8)`, `(batch,2)`, and `(batch,512)`; its current batch size is 2. Each image input stacks two `(6,128,256)` YUV frames. The simulator stages two `(384,512)` YUV frames and transforms them similarly. The generator sends these four inputs plus 12 target arrays. `hevc2yuvh5.py` imports OpenPilot `tools.lib.framereader.FrameReader` and `common.transformations.model.medmodel_intrinsics`; `cameraB3.py` and `lanes_image_space.py` import `common.transformations.orientation`. Those modules must be checked against the current OpenPilot volume before execution.

| Output | Half-open indices | Length |
| --- | ---: | ---: |
| path | 0:385 | 385 |
| left lane | 385:771 | 386 |
| right lane | 771:1157 | 386 |
| lead | 1157:1215 | 58 |
| longitudinal x / velocity / acceleration | 1215:1415 / 1415:1615 / 1615:1815 | 200 each |
| desire / meta / prediction / pose / state | 1815:1823 / 1823:1827 / 1827:1859 / 1859:1871 / 1871:2383 | 8 / 4 / 32 / 12 / 512 |

The lengths sum to 2383. The actual custom loss compares slices `0:384`, `385:769`, `771:1155`, and the full vector with weights 0.3/0.3/0.3/0.1, omitting the ends of the first three blocks in the weighted terms. Current constants are `BATCH_SIZE=2`, `STEPS=20`, `STEPSv=10`, `EPOCHS=60`; `serverB6.py` globs `/home/*/dataB6/*/yuv.h5`, seeds and shuffles, then uses files `[0:2]` for training and `[2:3]` for validation. **HIGH:** this assumes at least three files; no check establishes a nonempty validation set. Some slide examples overlap splits, but the current source's default slices are disjoint when three distinct files are found. **HIGH:** `datagenB6.py` opens the `oSCfile` variable left from its earlier file loop for every training file and indexes teacher targets with `bcount` rather than `bcount+i`; this can pair the wrong target with each image. **HIGH:** the training script calls `load_weights('./saved_model/B6BW.hdf5')` unconditionally before its first fit; that checkpoint is absent from the preserved ModelB6 directory. The checkpoint monitors `loss` (training), despite slides describing best validation weights. It saves the final model separately. These are baseline code findings to resolve only after preserving the original files.

For Step 6, the active simulator source hard-codes USA segment `--37/video.hevc`; a Taiwan `dataC/.../fcamera.hevc` path is commented out. It loads `saved_model/B6.keras`, predicts up to three frames, plots four views, and pauses for terminal input. **MEDIUM:** despite slide claims about `B6Sim.png` and `sim_output*.txt`, the active code does not save these files; existing pictures/text in the archive are prior reference artifacts. `train_modelB6.py` has a second test/plot block, including `B6YMC.png`, inside a triple-quoted string, so it does not execute. Camera geometry adjustments differ by video type in comments and helper code. Course examples explicitly show overfitting, wrong-way left predictions, and zigzag paths, so successful training alone is not verification.

Potential large or generated files include `outSC.h5`, `yuv.h5`, `.keras`, `.hdf5`, video, text dumps, plots, and logs. Sizes and count are unknown without the source and volume contents. Do not write them into the OpenPilot source volume by default.

## 3. Agent architecture and evidence limits

The professor's Agent document specifies Python **3.11**, `agno`, `duckduckgo-search`, `google-genai`, `GOOGLE_API_KEY`, and `python3.11 agent.py`, followed by reading a five-level agent framework and doing original “Do New” work. The preserved `agent.py` imports `agno.agent.Agent`, `agno.models.google.Gemini`, `YFinanceTools`, `DuckDuckGoTools`, `ReasoningTools`, and `agno.media.Image`. It constructs several example agents using **`gemini-2.5-flash`**. The only active `print_response` is a streaming trip-planning prompt using `ReasoningTools`; the search, finance, and image examples are commented out. Its image example hard-codes `/home/jinn/dataB6/.../preview.png`. No OpenPilot import appears. No API key value or assignment appears in `agent.py`; the key is expected from the environment. Exact Agno and `google-genai` versions remain **unknown** because neither course document nor source pins them.

The active Gemini call needs network/API access; search and finance examples would need network access if enabled. The `YFinanceTools` import also implies an additional finance package/API dependency, to establish from a resolved Agno environment. The Agent should not share the Python 3.8 OpenPilot interpreter. For later student work, keep the professor `agent.py` in ignored reference material and create a small tracked student implementation only after reproducing and understanding it. Supply `GOOGLE_API_KEY` at runtime from the environment or an ignored local secret file; do not place a value in code, Compose, logs, or Git.

## 4. Professor path to current path mapping

Docker metadata confirms named volumes, not their contents. On macOS the Docker volume mountpoint is inside Docker's Linux VM, not a normal project directory.

| Professor path or artifact | Current host location | Current container location | Storage/status |
| --- | --- | --- | --- |
| `/home/jinn/openpilot` | No host checkout of this OpenPilot tree | `/opt/openpilot` | `ai-self-driving-car_openpilot-repo` named volume; existing source/build baseline, contents not checked today |
| `/home/jinn/dataB6` | No project copy; ignored `dataB6/` absent | `/data/dataB6` per Project 1 record | `ai-self-driving-car_replay-data` named volume; dataset content not checked today |
| Professor `dataC` under OpenPilot replay tools | No host project copy | `/opt/openpilot/tools/replay/dataC` per Project 1 record | OpenPilot named volume; content not checked today |
| `/home/jinn/openpilot/aJLL/ModelB6` | `external/aJLL/ModelB6/` is empty of source; source preserved in `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/ModelB6/` | **No mount** | Ignored professor reference; temporary duplicate is not a durable work location |
| `/home/jinn/openpilot/aJLL/Agent` | `external/aJLL/Agent/` empty; `agent.py` in the preserved `/private/tmp` duplicate | **No mount** | Ignored professor reference |
| Professor `saved_model/`, `output/` | Empty directories in `external/aJLL/ModelB6/`; reference model and sample output in `/private/tmp` duplicate | **No current mapping** | Future generated artifacts need a separate location; never assume the professor path exists |
| Course `.docx` / `.pptx` | `course-materials/` | Not mounted | Ignored local professor reference material |
| Student source (future) | Prefer a small Git-tracked `projects/project2/` tree | Mount read-only into a Project 2 runtime when implemented | Git for source/config; no mount exists today |

`docker/docker-compose.yaml` mounts `/opt/openpilot`, `/data`, `/run/openpilot`, and `/tmp`; it does not mount this host workspace or `external/aJLL`. `docker/Dockerfile.compute` installs OpenPilot v0.9.1 into the image, but the existing `/opt/openpilot` volume masks that image path at runtime. `docker/compute-entrypoint` starts the health socket and idles; it does not run ModelB6. `scripts/openpilot.sh` has no Project 2 command.

## 5. Dependency and compatibility matrix

| Component | Evidence-backed requirement/current state | Confidence / consequence |
| --- | --- | --- |
| Project 1 compute | Ubuntu 20.04, `linux/amd64`, Python 3.8.10 per Project 1 validation; Dockerfile installs Poetry 1.3.2, SCons 4.4.0, NumPy and OpenPilot build packages | High for configuration; no live interpreter check today |
| ModelB6 Python | Professor's `sconsvenv`/InstallOP uses Python 3.8.x; source uses `tensorflow.keras` and no explicit Python pin | 3.8 is the intended baseline, exact supported range depends on the chosen TensorFlow release |
| TensorFlow / Keras | Source imports `tensorflow.keras`, callbacks/backend and `.keras`/HDF5 model files; archived `supercombo079.keras` is HDF5 format despite its extension | **BLOCKER:** no pinned TensorFlow release; compute Dockerfile does not install it. Legacy save/optimizer API and file-format compatibility need an isolated compatibility test |
| ModelB6 other packages | Direct imports: NumPy, `h5py`, `pyzmq` (`zmq`), `six`, OpenCV (`cv2`), Matplotlib, `tqdm`, TensorFlow | Exact versions unpinned. `hevc2yuvh5.py` also needs OpenPilot `FrameReader` and suitable video decoding libraries |
| ModelB6 OpenPilot modules | `tools.lib.framereader`, `common.transformations.model`, `common.transformations.orientation` | Current v0.9.1 module/API compatibility needs a read-only import test in an isolated runtime |
| GPU/CUDA | `train_modelB6.py` sets `CUDA_VISIBLE_DEVICES=0`; slides recommend larger batches with more GPUs | GPU is assumed by author but no explicit GPU-only operator found. CPU execution is plausible, with time/memory unverified. Current amd64 emulation has no configured GPU passthrough |
| ModelB6 architecture | Current compute is Linux amd64 through Apple Silicon emulation; professor code may load native OpenPilot modules | Source or binary dependencies may be x86-specific; no ModelB6 import/run check possible |
| Agent | Professor says Python 3.11, `agno`, `duckduckgo-search`, `google-genai`; source imports Agno finance/search/reasoning/media tools | Add finance dependency if needed by installed Agno API; exact package/API versions unpinned. Python 3.11 requires a separate interpreter |
| Runtime network | Agent search/Gemini; ModelB6 local server ports 5557/5558 | Agent needs external network/API authorization; ModelB6 ports need only intra-runtime connectivity unless source says otherwise. No port publishing is configured |

**Conclusion:** ModelB6 cannot be declared safe inside the existing compute interpreter. TensorFlow is absent from its Dockerfile, version compatibility is unknown, and installing it in place risks OpenPilot's validated Python dependency set. CPU execution may be possible but could be slow under amd64 emulation. The archived teacher model's HDF5 format under a `.keras` suffix is an additional compatibility risk. No evidence supports upgrading the Project 1 interpreter or modifying its named volumes.

## 6. Isolation choice and Project 1 regression risks

| Workload | Existing compute interpreter | Separate environment inside compute | Separate service/container |
| --- | --- | --- | --- |
| ModelB6 | Reject for now: unverified TensorFlow and possible dependency conflicts | Possible, but shares compute filesystem/CPU and can accidentally write `/opt/openpilot` or `/data` | **Preferred after durable source preservation:** separate Project 2 image/service, pin dependencies, mount OpenPilot and datasets read-only, use a separate writable output path; verify OpenPilot imports first |
| Agent | Reject: professor specifies Python 3.11 | A host Python 3.11 virtual environment is the smallest practical isolation if local Python 3.11 and network access are available | Use a separate service only if reproducibility or host setup calls for it; do not modify compute |

For ModelB6, avoid a full architecture change: add only the isolated runtime and mounts required after restoring source and confirming imports. Separate output storage is necessary because the professor scripts use relative `saved_model/` and `output/` paths. The data generator also writes `outSC.h5` beside `yuv.h5`; a read-only dataset mount will require a copy or a configured writable derived-data location. Preserve the original dataset volume while designing that path. Avoid concurrent training and Replay until CPU, memory, and disk load are measured. Do not alter the existing OpenPilot repo volume, replay binaries, dataB6/dataC, IPC/PID sharing, or display service during this audit.

## 7. Git and security

`git status --short --branch` at audit time: `develop...origin/develop`, modified `.gitignore`, untracked `docs/COURSE_PLAN.md` and `docs/PROJECT2.md`; this audit adds only this Markdown file. The `.gitignore` modification predated this audit and adds `course-materials/`. Ignored paths include `external/aJLL/`, `external/installop-assets/`, `dataB6/`, `.env`/`.env.*`, and `*.ppk`. `git ls-files` reports no tracked professor source/data, course files, `.env`, `.ppk`, HDF5/model files, or obvious Google API key assignments. This is a current-tree scan, not a Git-history secret audit.

**MEDIUM:** generic future `*.keras`, `*.hdf5`, `*.h5`, generated output, and nested secret naming patterns are not broadly ignored. Before generating any artifacts, add narrowly scoped Project 2 output/secret ignores. Avoid broad `*.png`/`*.txt` rules because small intentional results may be tracked. The ignored professor archive and original course files must remain outside Git. A public repository may track student code, environment definitions, configuration examples, and short audit/experiment metadata.

## 8. Student structure and milestones

Start with `docs/PROJECT2_AUDIT.md` and the existing docs. Once source is restored, a small `projects/project2/modelb6/` for student wrappers/config and `projects/project2/agent/` for original Agent work is enough. Add `experiments/` only when multiple model cases exist. There is no current evidence for top-level `models/` or `integration/`. Keep professor baseline under ignored `external/aJLL/`, datasets in existing volumes, generated checkpoints in a dedicated ignored output location, and secrets in runtime environment/ignored local configuration.

1. **P2.0 Readiness audit:** this report; durable source preservation remains open.
2. **P2.1 ModelB6 compatibility:** restore/verify the preserved source, identify working TensorFlow/legacy Keras version, resolve the four source issues above in a student-owned copy, and test an isolated environment without writing Project 1 volumes.
3. **P2.2 Step 5 baseline:** reproduce training and validation data servers and confirm generated inputs.
4. **P2.3 Model artifacts:** train and record final `B6.keras`, best weights, metrics, and resource cost.
5. **P2.4 Step 6 baseline:** run simulator with the trained model and inspect output.
6. **P2.5 USA/Taiwan verification:** confirm the video and data paths and inspect path/lane/lead predictions.
7. **P2.6 Analysis:** check split independence, overfitting, loss, and hyperparameters.
8. **P2.7 Agent baseline:** recover `agent.py`, pin a Python 3.11 environment, run with a runtime API key, and study the assigned framework.
9. **P2.8–P2.9 Do New:** specify an original change, then implement and evaluate it against the baseline.

Steps 2–7 and 8 can proceed independently once their respective sources are available. The slides' `outSC.h5` generation should be verified before training; P2.2 is not just launching the three terminal commands.

## 9. Issues and exact next action

- **BLOCKER:** Preserve the 181-file `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/` archive in the ignored `external/aJLL/` location or another durable private location, verifying filenames and hashes first. Do not overwrite the Project 1 volumes or the professor files. Then test dependency compatibility in a separate Project 2 runtime; no package installation was authorized during this audit.
- **HIGH:** Current Docker services are absent; volume contents and Project 1 runtime health were not checked today. Before any Project 2 execution, perform a read-only inventory or normal non-destructive validation of the existing baseline.
- **HIGH:** Default training cannot start from the preserved source as-is: the initial best-weights file is absent; the data generator appears to pair inputs with incorrect teacher rows and can use the wrong teacher file; the checkpoint monitors training loss instead of validation loss. Verify these findings with small isolated fixtures before any actual training.
- **HIGH:** Exact TensorFlow/Keras and Agno package versions are unpinned and untested. Do not infer them from file extensions or current package releases.
- **MEDIUM:** The Agent's baseline calls Gemini over the network and imports optional tool integrations. Its actual execution and runtime API compatibility remain unverified.
- **MEDIUM:** Project 1 has documented limits: no clean empty-volume restoration and no full tools092 overlay rebuild verification. These are not reasons to modify the current baseline during Project 2 setup.
- **LOW:** Add precise ignore rules when Project 2 output paths are selected.

Evidence: `README.md`; `docs/COURSE_PLAN.md`, `PROJECT2.md`, `IMPLEMENTATION.md`, `INSTALLOP_AUDIT.md`, `INSTALLOP_ASSETS.md`; `course-materials/2509_AI_Steps5-6.pptx` and `2509 AI Agent.docx`; preserved private source at `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/ModelB6/` and `/Agent/`; `.gitignore`; `docker/docker-compose.yaml`, `Dockerfile.compute`, `compute-entrypoint`; `scripts/openpilot.sh`; read-only `git` and `docker` metadata commands. Course documents and professor source were not copied into this report.

## 10. 2026-10-04 remediation status

This section supersedes the earlier source-preservation and stopped-container status statements; earlier sections remain the record of the initial readiness audit.

The 181-file professor archive was restored from `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/` to the durable ignored location `external/aJLL/`. Before copying, the existing destination had one file; it was present in the source archive with the same SHA-256, so it was retained and only missing files were copied. The source and destination now each have 181 files, identical relative-path and SHA-256 manifests, and the same 76,416 KiB disk usage. The shared manifest SHA-256 is `6ad820f7258ca4035e20b9896d8c9d0a770aa83d7733e77f9de798407bd4b09a`. Required references are present: ModelB6 source, `Agent/agent.py`, `saved_model/supercombo079.keras`, and example output artifacts. The `/private/tmp` source was not moved or deleted.

Git safety remains PASS. `external/aJLL/`, `course-materials/`, `external/installop-assets/`, `dataB6/`, `.env`, `.env.*`, and `*.ppk` all match explicit ignore rules. No files beneath these paths are tracked or staged. Project 2 now has narrow ignore rules for the future `projects/project2/modelb6/derived-data/`, `artifacts/`, and `logs/` paths; no Project 2 directories were created.

Project 1 regression check PASS: the normal `./scripts/openpilot.sh up` command started the existing services with cached image layers and retained named volumes. Both `compute` and `display` are healthy; `compute` reports Python 3.8.10 and a present health socket. `./scripts/openpilot.sh validate` passed its checks for the four expected volumes, 129 `dataB6` files, required `dataC` files, original and compatible JLL SHA-256 values, UI dependencies, VNC on 5910, and noVNC on 6080. This remains an environment regression check and does not certify replay video; replay was not run.

The ModelB6 source findings are all **CONFIRMED** by static inspection of the restored reference source:

| Finding | Status | Evidence |
| --- | --- | --- |
| A. Training loads `./saved_model/B6BW.hdf5` before `model.fit` | CONFIRMED | `train_modelB6.py` calls `model.load_weights` at line 165 before fitting at line 167 |
| B. Starting `B6BW.hdf5` is absent | CONFIRMED | Restored `saved_model/` contains only `supercombo079.keras` and its summary |
| C. Generator can reuse the wrong `oSCfile` | CONFIRMED | `datagenB6.py` assigns `oSCfile` in its preliminary file loop, then opens that retained variable for every later `cfile` |
| D. Generator indexes teacher rows with `bcount`, not `bcount+i+t0` | CONFIRMED | Input frames use the advancing index at lines 137–138, but teacher output uses `oSCX[bcount]` at line 142 |
| E. Checkpoint monitors training loss | CONFIRMED | `ModelCheckpoint(..., monitor='loss', ...)` at line 129; it does not monitor `val_loss` |

Any correction must be a student-owned, Git-tracked wrapper or reproducible overlay, with the restored professor archive kept unchanged.

The minimum Project 2 storage/runtime design is now:

| Boundary | Location and access |
| --- | --- |
| Professor reference | `external/aJLL/`; Git-ignored and treated read-only |
| Student source/configuration | Future `projects/project2/modelb6/` and `projects/project2/agent/`; Git-tracked |
| Original datasets and OpenPilot | Existing named volumes, mounted read-only in a future ModelB6 service where imports require them |
| Derived ModelB6 data and outputs | Future ignored `projects/project2/modelb6/derived-data/`, `artifacts/`, and `logs/`, mounted writable only in the Project 2 service |
| Secrets | Runtime environment or ignored local configuration; never image, Compose, source, or Git |

Because the baseline generator writes `outSC.h5` next to `yuv.h5`, the Project 2 runtime must generate teacher labels in a copied/derived dataset tree, not the original replay-data volume. The minimum reproducible ModelB6 direction is a separate service/container with pinned TensorFlow/Keras, read-only professor/OpenPilot/data inputs, and the dedicated writable Project 2 locations above. The Agent now uses an isolated host Python 3.11 virtual environment; it does not share the ModelB6 runtime.

## 11. P2.1 ModelB6 runtime and compatibility scaffold (2026-10-04)

P2.1 adds a profile-gated `modelb6` Compose service. It inherits from the already validated `ai-self-driving-car-compute:latest` image only as a build base, retaining its Ubuntu 20.04, Python 3.8.10, amd64, and OpenPilot system-library baseline. It does not alter the running `compute` or `display` services, their images, or their named volumes. The service is excluded from normal Compose startup unless `--profile project2` is supplied.

The service mounts `external/aJLL/ModelB6` at `/workspace/professor`, `openpilot-repo` at `/opt/openpilot`, and `replay-data` at `/data`, each read-only. Its root filesystem is read-only, with only `/tmp` as a temporary filesystem and `modelb6-derived` plus `modelb6-output` as dedicated writable named volumes. The former is reserved for copied/generated input preparations such as `outSC.h5`; the latter is reserved for checkpoints, models, plots, metrics, and logs. P2.1 does not generate derived data, train, predict, write model artifacts, or alter the professor reference.

The tracked compatibility script is designed to perform the required no-write checks after the image builds: Python/dependency imports; the exact OpenPilot imports `tools.lib.framereader`, `common.transformations.model`, and `common.transformations.orientation`; the ModelB6 helper imports; construction of `modelB6.get_model()`; assertion of output shape `(None, 2383)`; HDF5 teacher loading from `supercombo079.keras` with `compile=False`; dataB6/dataC sample discovery; and read-only mount reporting. `simulatorB6.py` is assessed only in a separate subprocess because it has executable top-level code. It is expected to be non-import-safe while `B6.keras` is absent, which is a professor baseline condition rather than a P2.1 source change.

The chosen runtime pins are `tensorflow-cpu==2.13.1`, `numpy==1.24.3`, `h5py==3.8.0`, `opencv-python-headless==4.8.1.78`, `pyzmq==25.1.2`, `six==1.16.0`, `matplotlib==3.7.5`, `tqdm==4.66.2`, `atomicwrites==1.4.1`, `lru-dict==1.2.0`, and `requests==2.31.0`. TensorFlow 2.13 is the final TensorFlow line supporting Python 3.8 and supplies the legacy `tf.keras` HDF5 paths used by the archived teacher. The remaining pins satisfy the professor's direct imports and the transitive OpenPilot Python imports identified in this checkout. The Dockerfile uses the direct PyPI index because the configured package mirror falsely reported `tqdm==4.66.2` unavailable; PyPI metadata then resolved that exact Python 3-compatible release.

Compose configuration validation passed with `docker compose -f docker/docker-compose.yaml --profile project2 config --quiet`. The isolated image build did not complete: dependency resolution succeeded and began downloading the 186.5 MB `tensorflow_cpu-2.13.1` wheel, but the transfer from `files.pythonhosted.org` remained stalled without progress for more than ten minutes. It was interrupted safely before an image was created. An earlier direct-index attempt failed during dependency metadata retrieval with `ReadTimeoutError`; these are package-delivery failures, not evidence of a TensorFlow/Keras import or teacher-model incompatibility. Consequently, the P2.1 runtime tests have not run and their results remain unverified.

Project 1 post-scaffold regression validation passed after the interrupted isolated build: `./scripts/openpilot.sh status` reported healthy `compute` and `display` containers, and `./scripts/openpilot.sh validate` passed its Python, health-socket, volume, dataB6/dataC, JLL, and VNC/noVNC checks. No Project 1 data or OpenPilot volume was mounted writable by the P2.1 service.

| Priority | Remaining item |
| --- | --- |
| **BLOCKER** | Obtain the pinned TensorFlow wheel through a reliable network path and finish the isolated image build. |
| **HIGH** | Run the scripted imports, ModelB6 construction, teacher model load, and read-only data visibility checks; capture the actual results before P2.2. |
| **HIGH** | Keep the five confirmed professor training issues unchanged until a student-owned P2.2 correction layer is designed and tested. |
| **INFO** | The next action is to rerun `docker compose -f docker/docker-compose.yaml --profile project2 build modelb6`, then run `docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6` after the wheel can be fetched. |

### P2.1 retry result (2026-10-04)

A second unchanged image build again resolved the pinned requirements and reached the `tensorflow_cpu-2.13.1` 186.5 MB wheel, then produced no completion or transfer-progress output for an extended period. It was stopped without creating the image. Docker connectivity itself is available: an amd64 container received HTTP 200 from `https://pypi.org/simple/tensorflow-cpu/`, and a ranged request for the exact wheel from `files.pythonhosted.org` returned 1 MiB with HTTP 206 in 8.27 seconds. The observed condition is therefore a slow/stalled large pip transfer within the BuildKit build, rather than a missing release, DNS failure, or a TensorFlow/Keras compatibility failure. Package versions and the isolated runtime design remain unchanged. Runtime compatibility tests cannot run until that wheel transfer completes.

After this retry, `./scripts/openpilot.sh status` and `./scripts/openpilot.sh validate` again passed. Both Project 1 services remained healthy; no Project 1 volume, source, or dataset was modified.

### P2.1 completed compatibility validation (2026-10-04)

The large-wheel problem was an acquisition/caching issue. The original Dockerfile used `pip --no-cache-dir` inside one BuildKit `RUN`; failed builds discarded incomplete pip downloads, so each retry fetched the 186.5 MB TensorFlow wheel from zero. BuildKit itself and PyPI metadata were reachable. A direct 1 MiB ranged request to the exact PyPI wheel URL succeeded, but large quiet pip transfers repeatedly stalled.

`projects/project2/modelb6/fetch_tensorflow_wheel.py` now retrieves the exact Python 3.8 amd64 `tensorflow-cpu==2.13.1` wheel URL from PyPI release metadata at run time. It downloads 1 MiB HTTP 206 ranges into the Git-ignored `projects/project2/modelb6/wheelhouse/`; completed ranges survive interruption, while an incomplete range is fetched again. It requires the expected Content-Range and length for each response, assembles the wheel, then checks its full size and SHA-256 against pinned PyPI metadata before giving it a `.whl` filename. The verified result was **186,523,151 bytes**, SHA-256 **`ba6eec4d9a1e86d36fd7e7d010e07ce69702bb3cb68bc33a02a668b1928772a9`**; an independent `shasum -a 256` agreed. No temporary CDN URL or binary wheel is tracked. On a new machine, run `python3 projects/project2/modelb6/fetch_tensorflow_wheel.py` before building.

`docker/Dockerfile.modelb6` bind mounts the verified local wheel during its install step so the wheel does not remain in an image layer. The wheel is installed with `--no-deps`, then the pinned requirements resolve its dependencies from the official PyPI index. A BuildKit pip cache mount now preserves completed smaller package downloads across failed builds. `.dockerignore` omits range fragments from the Docker context. The final `docker compose -f docker/docker-compose.yaml --profile project2 build modelb6` **passed**. No TensorFlow, Keras, or Python version was changed for the network issue.

The first built-image check exposed one actual missing transitive OpenPilot dependency: `tools.lib.url_file` imports `tenacity` through `tools.lib.framereader`; the traceback ended in `ModuleNotFoundError: No module named 'tenacity'`. `tenacity==8.2.3` was added to the isolated Project 2 requirements (Python 3.8 compatible). The rebuilt image and the existing compatibility script then **passed**. `MPLCONFIGDIR=/tmp/matplotlib` prevents a harmless Matplotlib cache warning on the read-only container root. No professor or Project 1 source was changed.

| Check | Actual result |
| --- | --- |
| Image build | **PASS**, `ai-self-driving-car-modelb6:latest` |
| Python | **PASS**, 3.8.10 |
| TensorFlow / Keras | **PASS**, `tensorflow-cpu` 2.13.1 / `keras` 2.13.1 |
| Other pinned distributions | **PASS**: NumPy 1.24.3, h5py 3.8.0, `opencv-python-headless` 4.8.1.78 (`cv2.__version__` 4.8.1), pyzmq 25.1.2, six 1.16.0, Matplotlib 3.7.5, tqdm 4.66.2, atomicwrites 1.4.1, lru-dict 1.2.0, requests 2.31.0, tenacity 8.2.3 |
| Professor imports | **PASS**: `modelB6`, `datagenB6`, `serverB6`, `parserB6`, `cameraB3`, `lanes_image_space`, `hevc2yuvh5` |
| OpenPilot imports | **PASS**: `tools.lib.framereader`, `common.transformations.model`, `common.transformations.orientation` |
| ModelB6 construction | **PASS**: inputs `(None,12,128,256)`, `(None,8)`, `(None,2)`, `(None,512)`; 13,039,435 parameters |
| ModelB6 output | **PASS**, actual `(None,2383)` equals expected `(None,2383)` |
| Teacher model | **PASS**, `supercombo079.keras` loaded with `compile=False`; four inputs and 12 outputs with dimensions 385, 386, 386, 58, 200, 200, 200, 8, 4, 32, 12, 512 |
| dataB6 / dataC visibility | **PASS**: `dataB6/UHD--2018-08-02--08-34-47--37/video.hevc` and `tools/replay/dataC/8bfda98c9c9e4291\|2020-05-11--03-00-57/61/fcamera.hevc` were visible |
| Mount isolation | **PASS**: filesystem flags show professor, OpenPilot, dataB6, dataC, and the student image root read-only. Scratch-file probes succeeded only in dedicated `/derived` and `/output` volumes; the scratch files were closed and removed. |
| Project 1 regression | **PASS**: `./scripts/openpilot.sh status` reported healthy compute/display; `./scripts/openpilot.sh validate` passed after the final ModelB6 run. |

`simulatorB6.py` cannot be safely imported as a pure library before training because its top-level code immediately loads `saved_model/B6.keras`; its separate subprocess probe reported `OSError: No file or directory found at saved_model/B6.keras`. This is the expected missing student model artifact, not a TensorFlow loading failure. The teacher model loaded successfully. The professor archive still matches the preserved source (`diff -qr` found no differences).

**Remaining P2.2 work (HIGH):** create a Git-tracked student correction layer for the five confirmed training/data issues, test it with small isolated fixtures, and map any future label generation to `/derived` rather than the original replay-data volume. P2.1 performed no training, prediction, or `outSC.h5` generation. The compatibility stage itself has no remaining blocker.

## 12. P2.2 student correction layer and fixtures (2026-10-04)

The selected strategy is a small student adapter, `projects/project2/modelb6/corrections.py`, plus fixture tests. It imports professor batch/trim constants but copies no professor script. It defines corrected data iteration, derived label mapping, and checkpoint helpers; it does not launch training or generate labels at import. The five audit findings remain explicitly A–E below. The request's fifth safety condition—the original generator writing beside original data—is documented separately, so the absent checkpoint finding is not silently replaced.

| Audit issue and professor behavior | Why it matters | Student correction and fixture |
| --- | --- | --- |
| **A — unconditional resume**: `train_modelB6.py:165` calls `model.load_weights('./saved_model/B6BW.hdf5')` before `fit` | A fresh run fails before training | `initialize_model` keeps initialized weights when no resume path is supplied; test 1 uses a model spy that fails on any load. An explicit output checkpoint invokes `load_weights`; test 2 saves and restores a tiny Keras model without training. |
| **B — absent initial checkpoint**: restored `saved_model/` contains no `B6BW.hdf5` | There is nothing valid to load on the first run | The fresh path requires no invented/copy-supplied checkpoint. Resume accepts only a real checkpoint under `/output`; test 1 confirms absence and test 2 supplies one. |
| **C — retained teacher file**: `datagenB6.py:100` assigns `oSCfile` in an initial loop, and line 117 reuses that last value for every `cfile` | Multiple sequences can read one sequence's teacher rows | `corrected_datagen` computes `derived_teacher_path(camera_file)` inside each sequence loop. Test 3 uses two distinguishable sequences (100-series and 200-series) and asserts both image/label pairs. |
| **D — wrong teacher row**: `datagenB6.py:137–142` indexes images with `bcount+i+t0` but teacher rows with `bcount` | Later batches silently reuse early labels | The adapter uses one `row = bcount+i+t0` for both frames and teacher output. Test 4 asserts image IDs 102/103 match teacher IDs 102/103 in the second batch and differ from the old 100/101 behavior. |
| **E — checkpoint criterion**: `train_modelB6.py:129` monitors training `loss` | Best training loss is not the best held-out validation result | `validation_checkpoint` uses `monitor='val_loss'`, `mode='min'`, `save_best_only=True`, and `/output/B6BW.hdf5`. Test 5 checks configuration, saves a tiny model on an improved value, rejects a worse value, and reloads the saved weights. |

The associated storage behavior is `datagenB6.py:46–55`, which derives `outSC.h5` from the `yuv.h5` path and writes it in that same directory. This is unsafe for the read-only original data mount. The student mapping is `/data/dataB6/<sequence>/yuv.h5` to `/derived/dataB6/<sequence>/outSC.h5`, preserving sequence identity. `generate_derived_teacher` creates a tiny HDF5 external link to the original `X` dataset in a staging directory under `/derived`, calls a supplied label generator there, verifies the resulting shape, then publishes it under `/derived`. The fixtures use a deterministic fake label generator; they do not run professor teacher inference or make full-size labels. Tests 6–7 verify paths are outside originals, original hashes and directory contents stay unchanged, and no original `outSC.h5` appears. The actual runtime keeps the original mounts read-only as verified in P2.1.

The isolated command `docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/fixture_tests.py` **passed 7/7 tests**. The two fixture sequences each have eight synthetic `(6,128,256)` frames with distinct numeric IDs and seven tiny synthetic 2383-value teacher rows. The callback exercise saved only a tiny model in `/tmp` and performed no fit. The tests completed in 0.265 seconds after startup. `docker/Dockerfile.modelb6` now copies only the student adapter and fixture file in addition to the P2.1 script. The existing TensorFlow/Keras pins, ModelB6 architecture, 2383 layout, custom loss, optimizer, schedule, batch size, steps, epochs, and professor train/validation split were not changed.

The original `serverB6.py` and `train_modelB6.py` still invoke their professor implementations and hard-coded paths. **P2.3 Step 5 prerequisite (HIGH):** create student-owned server/training entry points that call this tested adapter, keep all outputs in `/output`, and perform a controlled small preparation/stream check before any real training or full data label generation. The current adapter is tested but is not wired into the professor command-line workflow. The ModelB6 training performance and split adequacy remain unverified. No professor or original dataset file was modified in P2.2.

Professor-source integrity **PASS**: `diff -qr` found no difference between the preserved `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/` and `external/aJLL/`. Both contain 181 files with the same relative-path/content manifest SHA-256, `5673b403e0a129d3eb0a8071275e03aa064cb3c8c4910323d9db3fba9555b259` (computed using the same manifest algorithm on both trees). Project 1 regression **PASS**: `./scripts/openpilot.sh status` showed healthy compute/display, and `./scripts/openpilot.sh validate` passed after fixture validation. No Docker volumes were deleted.

## 13. P2.3 corrected Step 5 small pipeline smoke test (2026-10-05)

Student-owned entry points now complete the corrected chain without invoking professor command-line workflows: `prepare_smoke.py` prepares selected teacher labels, `server_corrected.py` serves one explicit sequence using `corrected_datagen`, `train_corrected.py` runs a tightly bounded fit using professor `modelB6.get_model`, `custom_loss`, `maxae`, Adam settings, and learning-rate callbacks, `verify_smoke_model.py` loads outputs in a fresh process, and `smoke_pipeline.py` gates the stages and stops the two server subprocesses. The P2.2 adapter gained an explicit smoke-only `frame_limit`; normal generator semantics are unchanged. `docker/Dockerfile.modelb6` copies these student files. No professor file, TensorFlow pin, model architecture, output slicing, loss weights, default batch size, or normal training hyperparameter was changed.

The exact real-data selection was `UHD--2018-08-02--08-34-47--33` for training (1,199 available YUV frames) and the distinct `UHD--2018-08-02--08-34-47--32` for validation (1,200 available frames). Both original `yuv.h5` datasets have frame shape `(6,128,256)` and dtype `float32`; the `--33` file is marginally smaller on disk. The smoke-only selection used the first **five frames per sequence**, the minimum that yields one two-sample batch with the professor's `lastIdx = frame_count - 2 - BATCH_SIZE` loop. No training/validation sequence overlap occurred. This explicit split is only a smoke configuration; it does not change the professor's normal split policy.

The teacher model `supercombo079.keras` was loaded with `compile=False` and the professor's `oSC_Gen` was invoked on staged five-frame copies under `/derived`, never on original dataset paths. Each sequence produced **four** `(2383,)` teacher rows in a 40,176-byte `float32` HDF5 file. Rows were finite, the two sequence names mapped to separate `/derived/smoke/dataB6/<sequence>/outSC.h5` paths, and the corrected generator's image pairs and first two concatenated targets exactly matched original frame indices 0/1/2 and derived teacher rows 0/1. The 12 target slice widths sum to 2383. The two remaining generated rows per sequence are unused by this one-batch smoke run; no full dataset labels were created. Pre/post SHA-256 of original `--33/yuv.h5` was `d9b5ba57df9f19d5efa0f9287ea06c58fce2d54e14d248e99c1aac57ce49b424`; for `--32/yuv.h5` it was `49bfea9bb37cf77c6f465319e53e67cf270d27d0eb6aaa758b052a448588d436`.

Both corrected ZeroMQ streams were probed independently before fit: train port **5557** served `--33`, validation port **5558** served `--32`, and both probes passed source-frame/derived-target equality. Each serialized batch contained `Ximgs (2,12,128,256)`, `Xin1 (2,8)`, `Xin2 (2,2)`, `Xin3 (2,512)`, and 12 target blocks of widths `385,386,386,58,200,200,200,8,4,32,12,512`; concatenated `Ytrue` was `(2,2383)`. The controller stopped both server processes after verification.

The gated smoke override was **one epoch, one training step, one validation step, batch size 2**. A fresh ModelB6 started without an initial `B6BW.hdf5`. Measured starting loss was **42.9546012878418**, final reported training loss **42.9546012878418**, and validation loss **31.80754852294922**. Equal starting and final logged training loss is expected with this single batch: Keras reports its loss for that batch rather than a post-update evaluation. The fit exercised forward pass, professor custom loss, gradient update, Adam optimizer, validation, and the `val_loss`/`min`/best-only checkpoint callback. The training entry point took **11.148 seconds**; the full gated pipeline reported **36.461 seconds**. These values are execution evidence, not a model-quality comparison.

The validation callback created `/output/smoke/B6BW.hdf5` (157,495,320 bytes), and the final save created `/output/smoke/B6.keras` (157,259,010 bytes). A fresh process loaded both as models, confirmed four expected inputs and output `(None,2383)`, and separately loaded the checkpoint weights into a newly constructed ModelB6. `/output/smoke/` also holds `metrics.json`, stream-probe JSON, and stage/server logs. Only the two 40,176-byte smoke label files appeared under `/derived/smoke/`. The professor, OpenPilot, and original data mounts remained read-only; the 181-file professor archive still matches its preserved source. Project 1 `status` and `validate` both passed after the smoke test, with healthy compute/display services. No Step 6 simulator was run.

Observed integration detail: professor learning-rate callbacks reference a module-level `model`, so the student training entry point supplies that reference while retaining the professor schedule. The HDF5 best-checkpoint format emits Keras's legacy-format warning but saved and reloaded successfully. No new correctness blocker was found in the one-step path. **Next action:** plan the real Step 5 run separately, including an explicit multi-sequence split and resource/storage budget, then prepare only the approved training data in `/derived`; do not treat this smoke model as a trained or verified B6 result.

## 14. P2.4 real Step 5 plan and read-only dataset preparation (2026-10-05)

**Scope:** planning and preflight only. No full teacher targets, full training, or Step 6 were run. The preserved professor tree still has no differences from `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003/` (`diff -qr` exit 0). The P2.3 smoke files remain intact.

### Source inventory and split

The complete visible `/data/dataB6` contains three directories. All have `X` dtype `float32`, per-frame shape `(6,128,256)`, `yuv.h5` and `video.hevc`; none has a source `outSC.h5`. All are usable by `corrected_datagen`. Sizes are exact bytes, measured through the read-only ModelB6 mount.

| Sequence suffix | Frames / `X` shape | `yuv.h5` bytes | `video.hevc` bytes | Source `outSC.h5` | Plan |
| --- | ---: | ---: | ---: | --- | --- |
| `--32` | 1,200 / `(1200,6,128,256)` | 943,720,448 | 37,513,418 | absent | validation |
| `--33` | 1,199 / `(1199,6,128,256)` | 942,934,016 | 37,495,802 | absent | train |
| `--37` | 1,200 / `(1200,6,128,256)` | 943,720,448 | 37,534,986 | absent | train |

Totals: **3 sequences, 3 usable, 3,599 frames**, 2,830,374,912 bytes of YUV HDF5 and 112,544,206 bytes of HEVC, or **2,942,919,118 bytes** combined. The corrected training stream uses YUV and teacher HDF5, not HEVC; HEVC is inventoried for later verification. `dataC` is excluded from Step 5 and reserved for Taiwan Step 6.

**Professor baseline:** `serverB6.py` gathers `glob('/home/*/dataB6/*/yuv.h5')` without sorting, then calls `random.seed(0); random.shuffle(all_yuvs)`, taking `all_yuvs[0:2]` for train and `[2:3]` for validation. Seed 0 alone does not guarantee the same names if glob order changes. The comments show one observed order `--37,--32,--33`, but it is not a binding split. The active slices are disjoint with three distinct files. The professor Step 5 prose/examples include alternative overlapping small-data splits, but those commented alternatives are not the active source behavior.

**Student proposal:** `step5_split.json` records `TRAIN_SEQUENCES=[--33,--37]`, `VALIDATION_SEQUENCES=[--32]`, in that explicit order. These are full names in the JSON file. This stays close to the professor's two-sequence/one-sequence experiment, preserves the successful P2.3 train `--33`/validation `--32` pairing, adds `--37` to training, and avoids any train/validation sequence overlap or dependence on glob ordering. Validation has 1,196 usable examples, more than the baseline 20 validation examples per Keras epoch. It is still only one source drive segment, so generalization cannot be inferred from its `val_loss` alone.

For `BATCH_SIZE=2`, `TrimImgs=0`, each sequence uses `last_idx=N-2-2` and `range(0,last_idx,2)` from the actual corrected generator. Targets must have `N-1` rows because the teacher pairs consecutive frames. The generator deliberately leaves trailing frames/rows unused and drops incomplete batches:

| Sequence | Raw frames | Required teacher rows | Usable examples | Usable batches | Raw target bytes (`rows×2383×4`) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `--33` train | 1,199 | 1,198 | 1,196 | 598 | 11,419,336 |
| `--37` train | 1,200 | 1,199 | 1,196 | 598 | 11,428,868 |
| **Train** | **2,399** | **2,397** | **2,392** | **1,196** | **22,848,204** |
| `--32` validation | 1,200 | 1,199 | 1,196 | 598 | 11,428,868 |
| **All** | **3,599** | **3,596** | **3,588** | **1,794** | **34,277,072** |

The P2.3 4-row HDF5 was 40,176 bytes versus 38,128 raw bytes, an observed **2,048-byte** overhead. At that structure, three full files are about **34,283,216 bytes** (32.7 MiB); exact full-file allocation could differ. The label-generation staging directory temporarily holds the file before atomic publication, so allow roughly one extra sequence file during generation. P2.3 model artifacts measure **157,259,010 bytes** for `B6.keras` and **157,495,320 bytes** for `B6BW.hdf5`, or **314,754,330 bytes** together. Budget at least 20 MiB for text logs/JSON/plots and another 157.5 MB per optional retained checkpoint; the preflight requires label bytes plus **1 GiB** free as a conservative output/staging reserve. The planned layout is `/derived/step5/dataB6/<sequence>/outSC.h5` and `/output/step5/{B6.keras,B6BW.hdf5,logs/,metrics/,plots/}`. Nothing in `/derived/smoke` or `/output/smoke` is reused or overwritten.

Docker `statvfs` from both writable volumes reported **981,331,828,736 bytes** free at preflight (the two values describe shared Docker backing, not additive capacity). Docker Desktop reported 30.13 GB images, 6.132 GB volumes, 18.89 GB build cache. The macOS host filesystem reported **190 GiB available**; its physical capacity is the practical upper bound despite the larger virtual guest figure. Recheck both before actual generation because Docker Desktop quota/host free space can change. Current capacity is far above the approximately 34 MB labels plus approximately 315 MB final/best models and 1 GiB preflight reserve.

### Compute and unchanged baseline settings

The environment is Apple Silicon macOS with Docker Desktop `linux/amd64` emulation and TensorFlow CPU 2.13.1. A **read-only** teacher probe loaded `supercombo079.keras` in 1.526 seconds in one invocation. A second probe ran 21 predictions on original YUV pairs without writing: first prediction 1.111 seconds; the next 20 took 1.144 seconds, or **0.057 seconds/pair** warm. At 3,596 target rows, the warm-prediction component is about **205 seconds (3.4 minutes)**; allow **5–15 minutes** for full generation including HDF5 reads/writes, sequence/model setup and emulation variance. This is an estimate, not a completed label run.

The only measured training run is P2.3's one train step, one validation step, one epoch: **11.148 seconds** for the entry point, including model construction, compile, initial prediction/loss, checkpoint and final save; its Keras line reported roughly **9 seconds** for the epoch with checkpoint. These are not isolated per-step measurements. A provisional planning allowance is **5–30 seconds/epoch** and **5–30 minutes for 60 epochs**, including periodic best-checkpoint saves and final save. Pure train/validation step latency and sustained 20+10-step epoch latency remain **unmeasured**; a short bounded benchmark should refine the estimate before full training. Professor historical timing is not transferred to this host.

Professor/current default: `BATCH_SIZE=2`, `STEPS=20`, `STEPSv=10`, `EPOCHS=60`, Adam initial `1e-3`, cosine annealing from `lr_max=1e-3` toward `lr_min=5e-4` with `CA_period=60` and no warmup. There are **no active `decay_steps` or `decay_rate` values** in this source; the course overview mentions them generically. The actual custom loss weights are 0.3 path (`0:384`), 0.3 left lane (`385:769`), 0.3 right lane (`771:1155`), and 0.1 full-vector MSE. The best student checkpoint monitors `val_loss`, unlike the professor script's `loss` checkpoint. At 20 train and 10 validation batches per epoch, each epoch samples just 40/2,392 training examples and 20/1,196 validation examples; the infinite corrected stream advances between epochs. Across 60 epochs it requests 1,200 train batches and 600 validation batches versus 1,196 and 598 available per full stream cycle, so only the final 4 train and 2 validation batches revisit the beginning in a simple unprefetched traversal. ZMQ/Keras prefetch and the student server's initial probe can shift the exact boundary. These settings do **not** mean 60 complete passes over the data. They remain unchanged pending actual-run readiness review.

### Reusable preflight and interruption design

`step5_preflight.py`, copied into the isolated image, checks the explicit JSON split; distinct/nonempty sets; each selected HDF5 shape/dtype and nonzero exact batch count; teacher load and summed output width 2383; SHA-256 of five critical professor files including the teacher; read-only data/professor/OpenPilot/root mounts; writable `/derived` and `/output`; free space above raw labels plus 1 GiB; bind availability of 5557/5558; and visible stale student server/trainer processes. The professor archive comparison was also rerun on the host. It passed after the cached image rebuild. A fresh `docker compose run` has its own network/PID namespace, so the port/process result must be repeated **inside the future long-lived run container immediately before launching its servers**; it cannot certify unrelated containers/host ports. The script is non-generating and does not write into the data/output volumes.

Future full-label preparation should use the already tested student `generate_derived_teacher` staging/publish pattern **one sequence at a time**, never invoke professor `oSC_Gen` on `/data`, and write to `/derived/step5`. Keep incomplete work in a hidden staging directory, remove or quarantine it on restart, and publish `outSC.h5` only after shape `(N-1,2383)`, dtype float32, finite-row scan and source/teacher SHA checks pass. Then atomically publish a small completion JSON alongside each label containing sequence, source hash, teacher hash, row count, target width, label hash, and generator version. On resume, skip a sequence only when both marker and HDF5 revalidate; a file without its marker is **incomplete**, not reusable. A Docker restart or host sleep follows the same check. The current P2.2 helper already stages and atomically publishes the HDF5, but it does not yet create/revalidate this completion marker.

For training, preserve `/output/step5/B6BW.hdf5` as the best `val_loss` checkpoint and keep an atomic epoch/metrics manifest. An interrupted run may explicitly restart from that checkpoint through `initialize_model(..., resume_checkpoint=...)`; never silently start from it or overwrite the last known good checkpoint. Weight reload is verified in P2.2/P2.3, but exact optimizer/scheduler/epoch continuation is **not** implemented or validated. Until it is, resuming from best weights is a documented new training segment, not a mathematically identical continuation. The real runner must record that distinction and refuse to claim all intended epochs completed unless its logs prove them. Docker/host restart preserves the named volumes, but processes must be relaunched after preflight.

### Future execution gates and success criteria

The **currently executable** non-generating commands are:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step5_preflight.py
./scripts/openpilot.sh status
./scripts/openpilot.sh validate
```

The real sequence after explicit plan review is: (A) rerun preflight in the long-lived run container; (B) generate three selected label files per sequence with staging/completion markers; (C) independently validate all three label files and hashes; (D/E) start corrected multi-sequence training and validation servers on 5557/5558; (F) start the student real trainer for 20/10 steps and 60 epochs; (G) monitor finite `loss`, `val_loss`, LR, checkpoint, space and server health; (H) fresh-process reload final and best models and assert output `(None,2383)`; (I) preserve logs, metrics and plots; (J) rerun Project 1 status/validate. These are **procedure stages, not yet runnable full-run commands**. `prepare_smoke.py`, `server_corrected.py`, `train_corrected.py` and `smoke_pipeline.py` explicitly enforce one-sequence/five-frame or one-step limits and must not be used for the full run. Minimal future student-owned full-run CLIs and completion-marker validation are still required. Do not relax those smoke gates in place.

Step 5 succeeds only if all selected labels and completion markers validate; recorded training completes the intended steps/epochs; training and validation losses are finite; best and final artifacts exist and reload independently with output width 2383; logs/metrics remain available; professor and original data hashes remain unchanged; and Project 1 still validates. No particular low-loss threshold is established by the professor material. Failure includes missing/nonfinite/misaligned targets, overlap, server termination, partial outputs, nonfinite loss, missing artifacts or altered source. The best checkpoint is selected by `val_loss`; a lower loss is not itself sufficient evidence of successful completion.

**Step 6 handoff only:** future student-owned verification should read `/output/step5/B6.keras` read-only, record its checksum, and mount or explicitly copy it into a separate Step 6 runtime. USA verification uses the course's USA path/data; Taiwan verification uses `dataC` separately. Neither verification is attempted in P2.4.

**P2.4 recommendation: NO-GO for full Step 5 execution now.** Data, split, capacity and compatibility preflight pass, but the real multi-sequence preparation/server/trainer CLIs, completion-marker validation, and exact resume policy are still absent. The next P2.5 action is to implement and fixture-test only those student-owned real-run controls, then perform a bounded sustained-step benchmark and repeat preflight before any full label generation or training. No professor, original data, or Project 1 files were edited.

## 15. P2.5 production Step 5 reproduction (2026-10-05 Taiwan time)

**Outcome:** GO gate passed and the intended 60-epoch, 20-train-step/10-validation-step ModelB6 Step 5 run completed. All generated data remained under `/derived/step5`; all production artifacts remained under `/output/step5`. No Step 6 simulator was run, and no source data, professor code, Project 1 code, Docker volumes, or smoke artifacts were changed or deleted.

### Production interface and correctness gates

Added student-owned `step5_data.py`, `step5.py`, and `step5_tests.py`; `Dockerfile.modelb6` copies them into the isolated image. The existing P2.3 smoke entry points remain gated. `step5.py` exposes `preflight`, `prepare`, `validate-labels`, `server --split train|validation`, `benchmark`, `run --run-id ID`, and `verify --run-id ID`. The `run` command repeats preflight and full-label validation in its own container, launches both servers, probes them, shuts them down, relaunches clean servers, runs training, stops servers, and verifies artifacts. The CLI intentionally has no standalone training subcommand that can bypass these gates. Source paths come only from `step5_split.json`; source, professor, OpenPilot, and student mounts are read-only, with `/derived` and `/output` writable.

`prepare` uses each source `yuv.h5` through an HDF5 external link in a sequence-local hidden staging directory. It calls the unchanged professor `oSC_Gen` with the unchanged `supercombo079.keras` teacher, scans all rows for shape `(N-1,2383)`, float32 and finite values, hashes the staged HDF5, atomically publishes `outSC.h5`, then atomically publishes `outSC.complete.json`. The marker records status, sequence, original path and SHA-256, frame/row counts, target width, dtype, file size/SHA-256, teacher SHA-256, student/professor generator hashes, and UTC completion time. Server startup validates every marker, source hash, label hash, shape, dtype and finite scan once before streaming. Valid completed sequences are reused on restart. A missing/malformed marker, mismatched file, or leftover hidden stage fails closed; `prepare --force` moves only that sequence's derived artifacts into a derived-side quarantine before regenerating. It never touches original data. Training resume requires an explicit prior Step 5 `B6BW.hdf5` path and a new run ID; it starts a **new 60-epoch segment from best weights**, without claiming optimizer or scheduler continuation.

The production server uses `corrected_datagen` with explicit train order `--33,--37` and validation `--32`, ports 5557/5558. Review found that the P2.2 generator retained recurrent state across recordings; `corrections.py` now resets that state at each sequence boundary. The new fixture asserts both the new sequence's frame/teacher alignment and zero initial state. No architecture, 2383-vector definition, custom-loss slice/weight, baseline optimizer, learning-rate schedule, or 2/20/10/60 hyperparameter changed.

All **7 existing correction fixtures and 13 new production fixtures passed** after a one-line stage-cleanup ordering fix found by the first production fixture run. The new tests cover explicit multi-sequence order, split isolation, missing/malformed label completion conditions, wrong hash/row count/width, incomplete stage rejection, frame/teacher/state alignment at the boundary, source-side label avoidance, output shapes, restart reuse and derived-side quarantine. The P2.3 smoke artifacts also reloaded in a fresh process before implementation. No full labels were generated until these tests, the bounded benchmark, and preflight passed.

The bounded benchmark reused **only existing P2.3 smoke labels**, with 15 consecutive train steps and five validation steps in one epoch, no checkpoint or model save. It passed with finite loss **32.1762**, finite val_loss **17.7642**, first compiled train step **7.682 s**, subsequent train-step mean **0.136 s** (range 0.128–0.152), validation-step mean **0.167 s** (range 0.073–0.518), total orchestration **16.185 s**, and maximum resident set **1,776,356 KiB**. No progressive train-step slowdown was evident across 14 subsequent steps. The measurements include Keras callback timing; the whole Step 5 run later measured **289.480 s (4.82 min)**, superseding P2.4's provisional 5–30 minute estimate. `get_data` also runs a professor forward prediction before yielding each batch, so simple pure-gradient timing would understate this workflow.

The rebuilt-image preflight passed with TensorFlow **2.13.1**, three selected and disjoint sequences, valid source shapes/counts, teacher output width 2383, critical professor SHA-256 values, read-only input/root mounts, writable derived/output mounts, more than the required 1,108,018,896 bytes free, free 5557/5558 ports, and no stale visible Step 5 processes. Host filesystem had approximately **190 GiB** free. The image remained the isolated ModelB6 image; TensorFlow/Keras versions were unchanged. The GO decision was made only after these checks and output isolation passed.

### Full teacher labels and server dry run

The exact three selected sequences were generated and then independently revalidated, including deterministic teacher recomputation of rows 0 and 1 with recurrent state. No other sequence was processed. Each HDF5 file had the expected 2,048-byte structure overhead:

| Sequence | Split | Rows | Size bytes | Generation seconds | SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| `--33` | train | 1,198 | 11,421,384 | 76.155 | `dcc67b5d06dcd4ca4dd60bfde25b7f268f3ac7a14f891907c0cea515db201328` |
| `--37` | train | 1,199 | 11,430,916 | 75.148 | `07469e2c97fc345e53a4db67b0780bf6176371c1d35736aa7428df056f08d20b` |
| `--32` | validation | 1,199 | 11,430,916 | 75.701 | `c4a4954d1b282685298da7d19a364941d868a9155e4de3926352f18760cfb896` |
| **Total** | | **3,596** | **34,283,216** | **227.004** | |

The real-data dry run probed **599 training batches through ZeroMQ**, including the actual transition from `--33` to `--37`. The transition's first image pair and target matched `--37` frame/label row 0, and its recurrent state was zero. Three validation batches were probed on 5558. All input/target shapes and values were finite. The probe servers were stopped and fresh production servers started for fitting. Its machine-readable result is `/output/step5/orchestration/p25-baseline-20261005/dry-run.json`.

### Baseline training and artifacts

Run ID **`p25-baseline-20261005`** began fresh. It used batch size 2, Adam, the professor's 1e-3-to-5e-4 cosine schedule, unchanged custom loss and weights 0.3/0.3/0.3/0.1, **60 epochs × 20 train steps** and **60 × 10 validation steps**. The model had **13,039,435 parameters** and output `(None,2383)`. The final run manifest records **60 completed epochs, 1,200 train steps, 600 validation steps**, status `complete`, and **289.480 seconds** training-entry elapsed time. The epoch JSONL has exactly 60 finite records. Best checkpoint selection used minimum `val_loss`.

| Metric | Initial | Final | Minimum (epoch) |
| --- | ---: | ---: | ---: |
| Training loss | 79.2671 | 3.2041 | 0.1690 (45) |
| Validation loss | 42.2973 | 71.7146 | **0.5254 (25)** |

The loss plot is `/output/step5/runs/p25-baseline-20261005/plots/loss.png`; full values and timing are in `run.json`, `metrics/epochs.jsonl`, and `logs/train.log`. Training and validation both initially fell, but validation was highly variable: it reached 254.925 at epoch 18, recovered to its best at epoch 25, and later rose to 71.715 at epoch 60. The median validation loss after epoch 25 was 15.382. Training loss also spiked, so the evidence suggests instability and possible overfitting or sensitivity to the small one-sequence validation stream; it does not establish a behavioral failure or prove model quality. No tuning or retraining was done. There was no stable low-loss plateau across the whole run. The legacy HDF5 checkpoint-format warning occurred but both artifacts loaded.

Fresh-process `step5.py verify` **passed** for both final `B6.keras` and best `B6BW.hdf5`: four expected inputs, output `(None,2383)`, finite inference on a known source sample, and best weights loaded into a newly constructed ModelB6. Artifacts:

| Artifact | Path under `/output/step5/runs/p25-baseline-20261005/` | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Final model | `B6.keras` | 157,259,010 | `7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03` |
| Best checkpoint | `B6BW.hdf5` | 157,495,320 | `97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a` |

### Integrity, Project 1 and Step 6 handoff

The preserved 181-file professor archive still matched `external/aJLL/` with `diff -qr` exit 0. Before/after SHA-256 listings for **all 133 visible files under the read-only dataB6 and dataC trees** were identical. No source-side `outSC.h5` appeared. Derived labels and markers exist only under `/derived/step5/dataB6/`; the models, run manifest, metrics, logs and plot exist only under `/output/step5/`. The pre-existing `/derived/smoke` and `/output/smoke` were not changed. Project 1 `./scripts/openpilot.sh status` showed healthy compute/display; `./scripts/openpilot.sh validate` passed. No replay was run.

**Step 5 reproduction: PASS technically.** The trained final artifact is structurally ready for **later controlled Step 6 verification**, but behavioral quality is unknown and the final model's validation loss is much worse than the best epoch. The exact final handoff artifact is `/output/step5/runs/p25-baseline-20261005/B6.keras` with SHA-256 and size above, TensorFlow/Keras 2.13.1, run ID and losses in `run.json`. Keep the best checkpoint available for comparison; do not silently substitute it for the final model. Future USA verification uses dataB6 `video.hevc`; Taiwan verification uses dataC `fcamera.hevc` separately. No Step 6 command was executed. **Next action:** design the student-owned Step 6 simulator/verification plan around the immutable final artifact and explicitly account for the best-vs-final validation gap before interpreting behavioral results.

## 16. P2.6 source-audit gate (2026-10-05 Taiwan time)

The requested final/best × USA/Taiwan inference matrix **has not started**. Static inspection of the preserved professor source found a material camera/output interpretation conflict before a student Step 6 runner was adopted:

- `simulatorB6.py:5-10` says USA `video.hevc` uses path `+0.1`, left lane `+0.1`, right lane `-0.5`, while Taiwan `fcamera.hevc` uses path `+0`, left `-0.2`, right `-0.7`, with different projection center, height, and starting point. The active `parserB6.py:43-56` applies USA path `+0.1`, left `+1.8+0.1`, **right `-1.8-0.1`**. Thus even the documented USA right-lane adjustment differs by **0.4** from executable code. The active `lanes_image_space.py` uses only the USA projection; the Taiwan video assignment is commented out at `simulatorB6.py:38`. No executable Taiwan calibration branch was found in these Step 6 files.
- The active simulator initializes its two-value traffic input to `[0,0]` (`simulatorB6.py:108`), whereas professor teacher generation and the Step 5 training stream set the first value to `1` (`datagenB6.py:52,91`). This is an inference input shift that could affect model behavior, although the active simulator's choice itself is clear.
- OpenCV opened the USA `--37`, validation `--32`, and Taiwan dataC `61/fcamera.hevc` files and reported each as **1164×874 at 25 fps**; `CAP_PROP_FRAME_COUNT` returned an invalid large negative value, so the full counts still require decoding or a trustworthy probe. No model inference, synthetic fixtures, Step 6 outputs, or Project 1 changes followed this audit.

The camera/offset discrepancy can alter a visual lane comparison and an attempted Taiwan correction would be an unvalidated scientific choice. Per the P2.6 ambiguity gate, implementation and inference stopped here. Resolve the intended USA right-lane offset and the authoritative Taiwan projection/parser configuration before interpreting the four-cell comparison. A future runner should record the simulator's `[0,0]` traffic convention as a limitation relative to Step 5's `[1,0]` training inputs.

## 17. P2.6 controlled Step 6 verification (resumed 2026-10-05)

### Authoritative specification and implementation

The user reviewed the original professor Steps 5–6 presentation and resolved the preceding gate: the **Step 6 slide is authoritative** when its values conflict with the active parser/plotting constants. Student-owned `step6.py` and `step6_tests.py` apply that specification without editing professor files. The 12 raw output slices are asserted against the Step 5 target bounds `(0,385,771,1157,1215,1415,1615,1815,1823,1827,1859,1871,2383)` and saved separately from parsed results. The active professor `parserB6.py` is called, then a student adapter applies only the slide path/lane offsets. The parser's `log1p(exp(x))` softplus overflowed for some **finite** final-model logits (absolute raw maximum 2237.55). The student adapter now evaluates the same softplus mathematically with `log1p(exp(-abs(x)))+max(x,0)+1e-6` and checks **every** parsed field for finiteness. No professor file was changed.

| Slide configuration | USA `video.hevc` / Rav4 | Taiwan `fcamera.hevc` / Prius |
| --- | ---: | ---: |
| StartPt / PATH_DISTANCE | 4 / 192 | 3 / 192 |
| Vanishing point `(x,y)` on 1164×874 | `(592,379)` | `(611,397)` |
| Camera height | 1.4 m | 1.2 m |
| Path / left / right adjustments beyond lane anchor | `+0.1 / +0.1 / -0.5` | `+0 / -0.2 / -0.7` |
| Desire / traffic / initial recurrent state | zero / `[0,0]` / zero | zero / `[0,0]` / zero |

The USA right offset `-0.5` overrides the active parser's `-0.1` solely in student output interpretation. Both videos use the active professor `cameraB3.transform_img` YUV warp from `eon_intrinsics` to OpenPilot `medmodel_intrinsics`; their **overlay projection and parser calibration** differ as the slide specifies. The Step 6 traffic vector `[0,0]` intentionally differs from Step 5 teacher generation/training `[1,0]`, so behavior cannot be attributed solely to model weights. Every video/model cell begins with fresh zero state and feeds its own previous output state forward.

The runner checks exact final/best artifact size and SHA-256 before each cell, loads `B6.keras` directly or constructs `get_model()` plus `B6BW.hdf5` weights, verifies all four input shapes and `(None,2383)` output, checks critical professor hashes and source mount flags, and writes only below `/output/step6`. A failed stage stays there with `failure.json`; completed cells receive immutable per-cell directories, raw `.npy` outputs, parsed JSON, first/middle/last four-panel visuals, SHA-256 artifact inventory, and a completion manifest. `compare` refuses mixed sources/configurations/ranges and makes paired final/best visuals with hashes in `comparison.json`; `report` records the four-cell matrix. Descriptive measures have no ground-truth accuracy field. The preflight passed with Python 3.8.10/TensorFlow 2.13.1, correct model hashes and contracts, unchanged critical professor files, read-only professor/OpenPilot/data/root mounts, writable dedicated output, and more than 512 MiB output space. All **31 new Step 6 fixtures** passed; the earlier 7 correction and 13 Step 5 fixtures also passed (**51 total**).

### Video identity, preprocessing, and smoke

| Domain | Source | SHA-256 | Bytes | Reported OpenCV count | Sequential decoded count | Step 5 role |
| --- | --- | --- | ---: | ---: | ---: | --- |
| USA | `dataB6/UHD--2018-08-02--08-34-47--37/video.hevc` | `98b2420f89426db2eaefd3b2fdbabcf4d2398d272b0874a973887d657875de3c` | 37,534,986 | `-192153584101141` (invalid) | **1,200** | train-seen |
| Taiwan | `tools/replay/dataC/8bfda98c9c9e4291\|2020-05-11--03-00-57/61/fcamera.hevc` | `fc0315d752ed74f1318fd92a174953e687b746ebe3b8ee10a1ff5308e7008600` | 37,603,914 | `-192153584101141` (invalid) | **1,202** | not used in Step 5 |

Both decode as **1164×874, 25 fps**. The first USA transformed `(6,128,256)` tensor matched existing `--37/yuv.h5` row 0 **exactly** (MAE 0; equal fraction 1.0). First Taiwan tensor had finite values, standard deviation 26.74 and the expected shape. USA/Taiwan preprocessed frame MAE at indices 0, 600 and 1199 was **9.54, 14.15 and 16.08**, confirming distinct visual inputs. All four **five-prediction** smoke cells passed decode, four-input inference, output slicing, parser, state feedback, finite selected outputs, four-panel PNGs and manifests. The original professor script still only plots three frames interactively and does not save the claimed output files; this student runner supplies reproducible saved evidence.

The first full USA final run emitted a professor parser `RuntimeWarning: overflow encountered in exp`. That run is retained under `/output/step6/quarantine/usa-final-professor-softplus-overflow/`, not used for the matrix. After the stable-softplus fix, its 1,199 saved raw rows all parsed finitely; fixture 31 exercises a finite logit of 1000. The canonical USA final cell was rerun from frame 0 under the corrected runner. Its raw and visible path/lane/lead artifacts matched the quarantined run, while the corrected parser now also keeps uncertainty outputs finite.

### Full-clip matrix and descriptive comparison

USA final and best both used adjacent frame pairs from zero-based frames **0–1199** (1,199 predictions). Taiwan final and best both used **0–1201** (1,201 predictions). First/middle/last visual frame choices were deterministic: USA **1/600/1199**, Taiwan **1/601/1201**. Runtime below is inference-loop time including preprocessing, parsing and three PNGs; container startup, repeated preflight and sequential counting are outside it. Taiwan cells overlapped in time and shared CPU, so their elapsed values are not pure model-speed comparisons.

The descriptive “near” window is parsed lateral samples **4:40** (zero-based). Temporal change is the mean absolute difference of that window between adjacent predictions. A near-path extreme means any absolute value **>10 m** in that window; a nonpositive near lane width means any left-minus-right value **≤0** there. These diagnostic thresholds were fixed in code and are **not** ground-truth correctness labels.

| Cell | Predictions | Loop seconds | Near-path temporal change, mean m | Near-path >10 m frames | Nonpositive near lane-width frames | Lead-x temporal change, mean m | Max state L2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| USA final | 1,199 | 228.922 | 1.0903 | 239 | 1,006 | 59.9307 | 1045.82 |
| USA best | 1,199 | 242.484 | 0.00460 | 0 | 0 | 0.3483 | 198.41 |
| Taiwan final | 1,201 | 349.866 | 0.9993 | 204 | 941 | 53.5947 | 1007.54 |
| Taiwan best | 1,201 | 334.851 | 0.00460 | 0 | 0 | 0.3477 | 198.41 |

All four raw matrices were finite and shape `(predictions,2383)`; all parsed fields remained finite with the stable adapter. Paired first/middle/last visuals under `/output/step6/{usa,taiwan}/paired_frame_*.png` show strong final-model path/lane zigzags by the middle and end of both clips. The best checkpoint is substantially steadier under these **descriptive** measures, but its smooth overlays do not establish correct lane/path/lead predictions. Its lead-x mean is about **161.19 m** on both unrelated videos, with lead probability mean about **0.99147**; such continuity is not evidence of lead-detection accuracy. The final model's lead-x mean and temporal change are much larger, and its lane widths frequently reverse. The selected USA clip was used in training, so it is not an unseen-USA quality test.

On matching frame indices, the best checkpoint's USA/Taiwan raw outputs differ by mean absolute **3.51×10⁻⁶** (maximum **0.000336**), only **3.55×10⁻⁷** of its USA mean raw magnitude (9.889). The input tensors visibly differ, so this is evidence of **very low image sensitivity under the specified Step 6 inputs**, not evidence of cross-domain driving success. The final model's raw USA/Taiwan mean difference is **9.615** (ratio 0.486 to its mean raw magnitude), consistent with its unstable recurrent trajectories. Different slide camera projections further affect overlay appearance, and the shared Step 6 `[0,0]` traffic input differs from training. Those factors prevent attributing all differences to Taiwan domain shift or overfitting alone.

The low epoch-25 `val_loss` **corresponded to much steadier Step 6 output** than the epoch-60 final artifact on both clips. The experiment supports a late-training **output-stability degradation** hypothesis. It does **not** prove that the best model drives better, that Taiwan is substantially worse than USA, or that the one validation sequence selected behavioral quality correctly. No driving ground truth or closed-loop replay control evaluation was available. **Professor-style Step 6 technical pipeline: PASS** (video → paired YUV → four inputs → 2383 output → parser → path/lane/lead → visualization). **Behavioral quality: INCONCLUSIVE** for both models; final-model consistency is poor.

### Integrity and regression

`step6_integrity.py snapshot`/`verify` compared **173 files** spanning the mounted professor ModelB6 tree, original dataB6/dataC, derived Step 5 labels and all `/output/step5` artifacts: **zero missing, new or changed**. The full 181-file `external/aJLL` professor archive still matched its preserved local copy via `diff -qr` with no differences. Final and best hashes remained `7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03` and `97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a`. No source-side Step 6 outputs, teacher-label edits, retraining, tuning, or Docker-volume deletions occurred. Project 1 `./scripts/openpilot.sh status` showed healthy compute/display and `./scripts/openpilot.sh validate` passed its documented checks. Next experiment: a **read-only, fixed-frame input-sensitivity study** with controlled image and traffic-vector changes, followed by independently annotated path/lane/lead ground truth before any behavioral-quality claim; keep P2.5 weights immutable.

## 18. P2.7 controlled ModelB6 input sensitivity (2026-10-05)

### Input architecture and experiment contract

The preserved `modelB6.py` constructs four inputs: paired image `(1,12,128,256)`, desire `(1,8)`, traffic `(1,2)`, recurrent state `(1,512)`. The image is two adjacent six-plane YUV frames in channel-first order. Its path through the network is:

```text
paired YUV → Permute → EffNet stem/blocks/top → 1024-value flatten ─┬→ meta, desire prediction, pose
                                                            │
desire (8) → bias-free Dense(8) ──────────────────────────────┤
traffic (2) → bias-free Dense(2) ─────────────────────────────┤→ concat → Dense(1024) → recurrent gate → state (512)
previous state (512) → recurrent-state projections ──────────┘                                │
                                                       path, lanes, lead, longitudinal, desire state
                                                                                              │
                                                        next adjacent pair ← output state feedback
```

Desire and traffic join **after** image encoding, at the recurrent branch. The direct meta/desire-prediction/pose heads see the image embedding without desire/traffic/state. The professor Step 6 initial inputs are desire zero, traffic `[0,0]`, state zero. `step6.py` feeds the last 512 raw outputs back as next state. The local OpenPilot `cereal/log.capnp` `ModelData.Desire` enum defines `turnLeft=1` and `laneChangeLeft=3`; P2.7 uses those one-hot indices, without assigning an invented meaning to the eighth channel.

Student-owned `step7_sensitivity.py` and 20 fixtures are copied into **only** the isolated ModelB6 image. They keep both immutable P2.5 model hashes checked, run read-only inference, enforce exactly one changed input by array hashes, reject non-finite outputs and invalid output targets, and write only `/output/p27-sensitivity/`. The manifest stores model/video identities, sample indices, all four baseline/intervention input hashes, changed/unchanged factors, raw full and 12-section MAE/RMS/max, a relative metric, and runtime. Relative denominator is `max(mean(abs(baseline section)), 1.0)`; raw absolute changes are primary. The experiment does not calculate driving accuracy or alter weights. Zero/constant images are deliberately out of distribution.

Five pairs per clip follow `[0, floor((N-2)/4), floor((N-2)/2), floor(3(N-2)/4), N-2]` using P2.6 sequential frame counts, with image pair `(i,i+1)`. USA indices are **0, 299, 599, 898, 1198**; Taiwan **0, 300, 600, 900, 1200**. Each static comparison resets state to zero. Natural next-pair changes, within-domain/cross-domain real swaps, zero/mean images, duplicate-current/reversed temporal pairs, `[1,0]` traffic, two valid one-hot desires, and a state from the preceding eight adjacent pairs were tested for **both** models and domains. A separate 12-pair contiguous window from each quarter index compared recurrent feedback with zero-state reset on exactly the same images. There were **212** single-factor records, runtime **57.822 s** including video decode/model loading and all runs.

### Preprocessing and controlled results

The model-ready USA/Taiwan pair differences at matching sample ordinals were genuine: MAE **9.312, 19.002, 13.952, 15.188, 16.155** pixel levels, RMS **16.076, 24.820, 18.908, 26.194, 22.305**, and maximum absolute differences **175, 184, 185, 165, 158**. The preprocessing near-identity gate did not fire. For a fixed USA quarter input, the USA-middle pair differed by image MAE **2.814** and the Taiwan-quarter pair by **19.002**. Source hashes match section 17. Repeated inference on the identical USA quarter input was **bitwise identical** for both checkpoints (raw output MAE and max zero).

Mean raw full-output MAE across five fixed samples (four where a preceding/next pair is required):

| Intervention | Final USA | Final Taiwan | Best USA | Best Taiwan |
| --- | ---: | ---: | ---: | ---: |
| Real image, other position in same clip | 1.06e-7 | 1.82e-7 | 1.85e-8 | 4.86e-7 |
| Real image, corresponding position other domain | 9.71e-8 | 9.71e-8 | 3.22e-7 | 3.22e-7 |
| Zero image, OOD | 2.66e-7 | 2.50e-7 | 3.38e-7 | 3.08e-7 |
| Constant mean image, OOD | 3.92e-8 | 1.50e-7 | 2.49e-7 | 3.13e-7 |
| Duplicate-current temporal pair | 1.58e-7 | 1.32e-7 | 5.16e-7 | 5.27e-7 |
| Reverse temporal pair | 1.11e-7 | 6.19e-8 | 1.20e-8 | 4.92e-7 |
| Natural next adjacent pair | 1.32e-7 | 7.63e-8 | 2.42e-7 | 3.88e-7 |
| Traffic `[0,0]` → `[1,0]` | 1.69e-5 | 1.69e-5 | 6.39e-7 | 7.33e-7 |
| Desire zero → `turnLeft` one-hot | 2.24e-6 | 2.25e-6 | 7.49e-7 | 7.58e-7 |
| Desire zero → `laneChangeLeft` one-hot | 5.12e-7 | 5.08e-7 | 8.24e-7 | 8.30e-7 |
| Zero → real prior-eight-pair state | **1.868** | **1.868** | **2.046** | **2.046** |

The largest raw single-value image-swap change across these records was at most **4.58e-5**; the full-output mean was tiny even for zero images. Natural next-pair variation was likewise tiny, so the image result is not explained by choosing unusually similar real frames. The traffic change is larger than the final model's image effect, but remains only ~**1.7e-5** absolute full-output MAE in a zero-state one-step test; no large immediate traffic shift was demonstrated. Long recurrent accumulation under `[1,0]` was not tested. The real-state change is about **seven orders of magnitude** larger than the image change and is nearly identical across road domains for each checkpoint.

The section results follow the architecture: on USA, the prior-state intervention changed final/best **path** by mean MAE **0.722/0.690**, **long_x** by **8.411/4.418**, and output **state** by **2.298/4.526**. The direct **meta, desire_pred and pose** sections had *exactly zero* state-intervention difference. Real image swaps changed even the direct pose head by only about **1e-6** and meta by ~**1e-8** or less. Other image-sensitive sections were similarly tiny; full per-section metrics for every record are in `results.json`.

The quarter-window 12-pair feedback-vs-reset comparison (excluding the first identical prediction) gave mean full-output MAE **1.165 final** and **3.033 best** in both domains; path MAE **0.441 final** and **0.777 best**. Maximum recurrent-state L2 in these windows was **70.79 final** and **143.03 best**; mean successive state-output MAE was **0.791 final** and **1.233 best**. These are controlled state effects on identical image sequences, not driving-quality scores.

### Representation probe, interpretation and next gate

An additional read-only probe used the saved models' named image layers, holding other inputs at baseline. At USA quarter versus Taiwan quarter, input MAE was **19.002**; `stem_activation` MAE was **7.697 best / 7.706 final**, `block3b_activation` **1.33e-4 / 1.32e-4**, `top_activation` **3.18e-8 / 2.88e-8**, and final 1024-value `flatten` **1.29e-7 / 1.08e-7**. The image representation therefore becomes nearly invariant **inside the image encoder**, between the earlier block and the top; the first layer clearly receives distinct images. Zero-image perturbation also changes the stem strongly but barely changes the flatten vector. This localizes the observed failure more tightly than P2.6's uncontrolled raw-output comparison. It does not yet identify which weights, input scaling, activation, or training mechanism caused the collapse.

**Decision: Branch C plus E.** Under the tested sample set and Step 6 inputs, **both final and best are near image-invariant**, while real recurrent state has a material effect. The output is **not globally constant**: changing prior state changes many sections strongly. It behaves like a near-constant *image-conditioned* predictor at fixed state. Best is steadier than final in P2.6 and their recurrent dynamics differ; this experiment does not prove that this fully explains the stability gap. The large uncontrolled P2.6 final USA/Taiwan divergence should not be called direct image sensitivity; weak image perturbations may be amplified over a long recurrent rollout, which remains to be isolated. No meaningful direct image response or traffic effect comparable to state was found. The Step 5/Step 6 `[1,0]`/`[0,0]` mismatch remains real, but this one-step test does not make it the primary explanation of the collapsed image response. Behavioral quality, path/lane/lead accuracy, and global image independence remain unverified.

**Next experiment:** keep both weights frozen and audit the image encoder *layer by layer* from `block3b` through `top_activation`, along with actual training input scaling, checkpoint weight statistics, and read-only image-to-output gradients on fixed real pairs. Locate the first loss of scene information and determine whether it comes from numerical saturation, scaling, or learned weights before considering any retraining or model changes.

### Validation and integrity

`step7_sensitivity.py verify` passed all **212** records; **20 P2.7 + 31 P2.6 + 13 P2.5 + 7 P2.2 = 71 fixtures** passed. The P2.7 before/after SHA-256 inventory covered **245 files** across the professor ModelB6 tree, original dataB6/dataC, Step 5 derived and output trees, and **all** P2.6 outputs: zero added, missing, or changed. A separate `diff -qr` confirmed the full 181-file `external/aJLL` archive still matches its preserved local copy. Professor/OpenPilot/data/root mounts were read-only; only dedicated Project 2 derived/output volumes were writable. Project 1 `./scripts/openpilot.sh status` reported healthy compute/display and `validate` passed. Project 1 files were not edited by P2.7. No training, tuning, professor/dataset edits, volume deletion, commit, or push occurred.

## 19. P2.8 frozen-weight encoder audit (2026-10-05)

### Scope, source contracts and outputs

Following P2.7, the user authorized continuing the next diagnostic. Student-owned `step8_encoder_audit.py` traces **91 image-layer outputs** and records all **124 weighted layers** for the final, best, and a seeded fresh architecture reference. It measures image derivatives without an optimizer or weight update. The fresh seed **2801** and supplemental seeds **2802/2803** are architecture controls, **not** the unavailable historical P2.5 initialization. No fresh model is saved or trained. SHA-256 of every in-memory trained weight is unchanged before/after the primary probe; the original model-file identities remain the section 15 values.

Outputs are only `/output/p28-encoder-audit/results.json`, `reference_controls.json`, and `integrity_before.json`. The primary audit took **30.799 s**; two extra seed controls took **8.141 s**. The runtime remains TensorFlow **2.13.1**, with the P2.7 model/source/mount preflight. Comparisons use USA pairs **299/300** and **599/600**, Taiwan **300/301**, and a diagnostic zero tensor. Division by 255 is explicitly an OOD diagnostic intervention, not a change to preprocessing or a proposed correction.

### Training versus inference scale: no mismatch found

Decoded USA pairs **0/1, 299/300, 599/600** exactly match their original `yuv.h5` pairs: **MAE, RMS, max difference and nonzero difference count all zero**. Reading the actual `step5.stream_for_split('train')` also confirms its first image pair exactly matches its source HDF5 pair, uses float32 native YUV values, and sets traffic to `[1,0]`. Its first batch has image range **35–204**, mean **92.335**, standard deviation **25.347**. Neither pipeline divides images by 255. This rules out a train/inference scale discrepancy on the inspected inputs; it does not establish that the professor architecture's overall scale is well conditioned.

### Where image differences decay

Raw activation MAE for the identical controlled USA-quarter/Taiwan-quarter swap:

| Image endpoint | Final | Best | Fresh seed 2801 |
| --- | ---: | ---: | ---: |
| `stem_activation` | 7.706 | 7.697 | 7.153 |
| `block3c_add` | 0.003445 | 0.003471 | 0.006258 |
| `block4d_add` | 1.947e-4 | 1.968e-4 | 3.633e-4 |
| `block5d_add` | 8.584e-6 | 8.523e-6 | 1.388e-5 |
| `block6e_add` | 3.229e-7 | 3.843e-7 | 4.202e-7 |
| `block7b_add` | 1.977e-8 | 2.326e-8 | 1.144e-8 |
| `top_activation` | 2.885e-8 | 3.179e-8 | 4.343e-9 |
| `flatten` | 1.076e-7 | 1.291e-7 | 6.362e-9 |

The attenuation is progressive across stages, not a single disconnected layer. At trained `flatten`, mean activation magnitudes are **2.824 final / 3.026 best**, while the swapped-image signal is about **1e-7**. The late representation is dominated by an image-independent response on these probes. The zero-image comparison shows the same pattern. Supplemental fresh seeds 2802/2803 have `flatten` swap MAE **2.515e-8 / 1.910e-8** and top MAE **1.293e-8 / 7.656e-9**, so this attenuation also exists before training across all three tested seeds.

ELU negative saturation is present in the stem (~30% of trained activations at or below -0.999). It is **zero at measured later block activation endpoints and top_activation**; therefore late ELU negative saturation is not supported as the main explanation of the observed progressive attenuation. The numeric threshold statistic is interpreted as saturation only for ELU activation outputs, not for arbitrary convolution outputs or weights. All collected arrays/weights are finite; kernels are not all zero. Trained biases are nonzero, unlike fresh initialization, but their isolated causal contribution was not tested.

### Initialization mechanism and local derivatives

Inspection of the installed Keras implementation confirms default **GlorotUniform** depthwise initialization. For kernel shape `(k,k,C,1)`, its generic convolution fan calculation gives `fan_in=k²C`, `fan_out=k²`. The resulting initialized kernel standard deviation is `sqrt(2/(k²(C+1)))`. Under the simplifying independent-input variance model, a single depthwise filter's RMS gain is approximately `sqrt(2/(C+1))`. This is a scale calculation, not an exact gain for correlated real images or the entire residual network.

The seed-2802 kernels' measured spatial-filter RMS norms at stage-entry depthwise layers decrease as **0.245, 0.142, 0.117, 0.0843, 0.0614, 0.0529, 0.0402** from blocks 1–7. For example, `block6a_dwconv` has shape `(5,5,720,1)`, and its initialized RMS gain is ~**0.0527** under this calculation. Repeated stage transitions therefore have a concrete mechanism for losing image amplitude at initialization. Residual paths do not bypass every stage transition. Three fresh controls corroborate the net attenuation, but they cannot reconstruct the exact original training trajectory.

Read-only image-gradient RMS at the USA quarter pair, using explicitly defined mean-square scalar probes:

| Scalar objective | Final | Best |
| --- | ---: | ---: |
| Mean square of 1024 image embedding | 2.113e-11 | 1.121e-11 |
| Mean square of raw path section | 1.811e-13 | 1.092e-17 |
| Mean square of raw pose section | 8.429e-11 | 3.902e-11 |
| Mean square of raw recurrent output | 1.443e-14 | 9.208e-19 |

Taiwan gives similarly small local derivatives. These gradients are connected, finite, and tiny for the chosen objectives; they are **not** the Jacobian norm of every output, the actual professor training-loss gradient, or proof that all inputs have zero influence. Dividing both domains' image tensors by 255 did not restore a substantial output difference: full-output cross-domain MAE remained **2.705e-7 final / 5.438e-9 best**. Merely normalizing inference images is not justified by these results.

### Result and next diagnostic

The strengthened explanation is **encoder amplitude attenuation already present at default initialization, followed by a trained late representation dominated by input-independent response**, with a materially responsive recurrent branch established in P2.7. A preprocessing discrepancy and late ELU saturation are not supported by the measured evidence. This is stronger localization than a claim of overfitting alone, but it does not prove that initialization is the sole cause or identify the training intervention that would repair it.

Next: on existing teacher-labelled samples, measure the **actual unchanged training-loss gradients** reaching stem/early/late encoder weights versus recurrent/head weights, under the existing teacher-state input and a separately labelled zero-state diagnostic. Check whether the teacher-state path supplies a shortcut while the image path has negligible supervised gradients. Keep final/best weights and professor architecture fixed; do not retrain or tune until that evidence is established.

### Validation and preservation

Six new numerical/path/gradient fixtures plus all **71 existing Project 2 fixtures** passed (**77 total**). A before/after inventory of **248 protected files** includes all prior P2.5/P2.6 outputs, P2.7 evidence, professor ModelB6 and original datasets; zero added/missing/changed files. The full professor archive still matches its preserved local copy. Project 1 status/validate passed after the isolated image build. No professor, original dataset, Project 1 source, old model/output, or saved weight was changed; no training, volume deletion, commit or push occurred.

## 20. P2.9 supervised gradient attribution audit (2026-10-05)

### Question, exact training path and state provenance

Does the original supervised objective send useful gradient into the image encoder, and does teacher-state availability suppress that signal? The decision is **P2.9-B: strong encoder-gradient attenuation evidence**, with **H1 the strongest shared explanation**. Final-USA additionally shows state-dependent suppression compatible with H3 locally. Best and Taiwan counterfactuals do not support a universal strong-shortcut conclusion. This classification follows the completed measurements, not the prior hypothesis.

The actual source path is `step5.train` → `compiled_model`/`model.fit(professor_train.get_data(...))`. Servers use `step5.stream_for_split` → `corrections.corrected_datagen`; `train_modelB6.get_data` receives four arrays and horizontally stacks the 12 raw target sections. Its extra `predict` and unused loss evaluation do not change the returned sample or any model state in this architecture. The audit calls the **imported original `train_modelB6.custom_loss`** for differentiation, rather than a proxy.

```text
source yuv.h5 frames i,i+1 (native float32 pixels, 12×128×256)
  + desire=zeros(8), traffic=[1,0]
  + teacher target row i-1, slice 1871:2383 (zero at sequence start)
  → ModelB6(image, desire, traffic, state), training=True
  → concatenate 12 raw outputs, width 2383
  → compare with teacher target row i, same 2383-value order
  → 0.3 MSE[0:384] + 0.3 MSE[385:769] + 0.3 MSE[771:1155]
    + 0.1 MSE[0:2383]
  → mean per-sample loss → TensorFlow GradientTape.gradient
  → record gradients; no optimizer/update
```

The three emphasized MSE sections deliberately use the professor's exact 384-value slices, not all values in each path/lane section. The fourth term covers every output, including recurrent state and the direct image heads. No regularization loss is present. The production optimizer is Adam, learning rate 1e-3 with the professor cosine schedule toward 5e-4; P2.9 creates no optimizer. Raw gradients cannot reconstruct Adam updates without the historical moment estimates.

`datagenB6.oSC_Gen` computes teacher row i using image pair `(i,i+1)` and previous teacher state; `corrected_datagen` supplies **row i-1's latent state** to train against row i. The audit verifies this array equality directly for every selected USA sample. Inputs and targets are NumPy arrays in training, so teacher state is already detached from the current graph. Condition C therefore uses another real same-sequence state rather than a meaningless additional detach. The previous teacher state can encode preceding imagery and overlaps current pair's first frame; no inspected path copies the **current** target or a future target into input state. This confirms teacher forcing and causal temporal dependence, not confirmed target leakage.

### Harness, samples and safety

New student files are `step9_gradient_audit.py`, `step9_gradient_tests.py`, and `step9_report.py`; only the isolated ModelB6 Dockerfile receives their COPY entries. The original model, source, loss, preprocessing and checkpoints are unchanged. Final is `/output/step5/runs/p25-baseline-20261005/B6.keras`, SHA-256 `7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03`; best is the same run's `B6BW.hdf5`, SHA-256 `97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a`. The original loss file hash remains `287c036aac2ca08a08e1ce0befb460a33afd7e798ef5d4eaa1d598ab6b77d6d9`.

There are **18 samples × 2 checkpoints × 4 conditions = 144 trials**:

| Stratum | Source/target provenance | Pair start indices |
| --- | --- | --- |
| USA train | dataB6 `--37/yuv.h5`; existing `/derived/step5/dataB6/.../outSC.h5` | 0, 1, 299, 599, 898, 1195 |
| USA validation | dataB6 `--32/yuv.h5`; existing Step 5 teacher labels | 0, 1, 299, 599, 898, 1195 |
| Taiwan diagnostic extension | P2.7 dataC `61/fcamera.hevc`; frozen local `supercombo079.keras` | 0, 1, 300, 600, 900, 1197 |

The actual batch-2 generator truncates the tail: the last usable start is 1195 for 1200 frames, so P2.7's 1198 was not blindly reused. Taiwan's 1202 frames were decoded and checked. No prior Taiwan supervised labels existed. A student audit-only teacher rollout starts at frame zero, uses identical YUV, desire zero and `[1,0]` traffic, and retains only selected inputs/states/targets under `/output/p29-gradient-audit/`. It does not run the professor datagen program or publish an `outSC.h5`. These Taiwan targets are **new diagnostic teacher targets**, not historical training data or human ground truth. The teacher SHA is `14d312f37e9278779bf68b4639142e8d31a569bde8046d5c60a2a3f746c1c590`; direct inference matched `.predict` bitwise on the USA control, and matched the stored USA label within its established tolerance. Teacher weights were hashed before/after the rollout. Sample preparation took **132.696 s**.

Conditions hold target, desire and traffic fixed: **A original**, **B zero state**, **C deterministic same-sequence state rotation**, **D zero image** (OOD). Rotation is by three selected positions; one replacement in each sequence is its valid start-of-sequence zero state. Three original sequence-start samples also have zero state; they remain in per-sample reports but are excluded from paired state-removal aggregates, leaving **15 nonzero histories**.

The model has no Dropout, BatchNorm or other detected stochastic/stateful normalization layer. `training=True` reproduces the training forward computation; its output equals `training=False` on the control. A new tape per trial captures image/state inputs, 23 named activations, fusion slices and every trainable parameter. There are no hooks or accumulated `.grad` buffers. Repeating a sample after all other trials yields exactly the same gradients. Batch-of-two loss/input-gradient parity is checked: each per-sample gradient is twice its contribution to a batch-of-two mean. All **13,039,435** parameters are trainable; all weight hashes remain identical after each role. Main gradient execution took **67.544 s**; the 12 supplemental component probes took **14.911 s**.

### Gradient metrics and main results

Each monitored tensor/group records shape(s), element count, mean absolute gradient, RMS, L2, maximum, exact-zero fraction and fraction below `1e-12`. RMS is used for comparisons across differently sized tensors (image 393216 elements; state 512). Parameter records also contain RMS relative to weight RMS. Input RMS×gradient RMS is stored as a separate scale-aware diagnostic. Ratios with a zero denominator remain null; zero-input state-projection parameter gradients at sequence starts are expected, not a failed tape.

All-sample medians below use 18 individual losses/gradients per checkpoint. They are not P2.5 epoch train/validation metrics. The last row is the median of 15 **paired** ratios, not a ratio of the other medians.

| Measure | Final | Best |
| --- | ---: | ---: |
| Image input gradient RMS | **9.775e-15** | **2.580e-15** |
| State input gradient RMS | **0.1907** | **0.2903** |
| Per-sample image/state RMS ratio | **6.735e-14** | **2.218e-14** |
| Stem activation gradient RMS | 2.591e-14 | 6.776e-15 |
| Middle `block4d_add` gradient RMS | 1.963e-9 | 5.182e-10 |
| Late `top_activation` gradient RMS | 1.686e-6 | 1.240e-6 |
| Image `flatten` gradient RMS | 1.359e-5 | 8.026e-6 |
| Encoder parameter gradient RMS | 3.337e-6 | 3.324e-6 |
| State-projection parameter gradient RMS | 0.01321 | 0.01122 |
| Original supervised loss | 30.7705 | 29.9163 |
| Zero-state supervised loss | 35.4681 | 38.0401 |
| Paired image-gradient amplification after state removal | **7.9617×** | **1.000028×** |

Nonzero-history image/state ratios after multiplying each input-gradient RMS by its input RMS remain **6.354e-12 final / 4.646e-12 best** (medians), so raw input units do not explain the imbalance. Encoder/state **parameter** RMS ratios are **3.532e-4 / 8.280e-4**, substantially larger than the input ratios; a parameter gradient must not be conflated with image sensitivity. Late image biases and nearly constant image representations can still receive gradients. Encoder-kernel RMS medians are **1.394e-6 / 1.582e-6**, versus encoder-bias RMS **4.194e-5 / 4.222e-5**. Stem-convolution parameter RMS is only **7.035e-11 / 3.496e-11**, compared with the last image convolution's **1.566e-5 / 1.732e-5**.

The actual fusion concatenation contains projected desire (0:8), traffic (8:10), then image embedding (10:1034); state enters separate additive/multiplicative gates, not this concat. Fusion-image gradient RMS medians are **3.088e-8 / 8.974e-9**, while the first direct state projection `dense_5` receives **0.06056 / 0.09867**. Other state gates can have tiny or exactly zero gradients, so the state pathway is not uniformly sensitive at every projection.

### Spread, counterfactuals and loss components

| Original condition | Final USA | Final Taiwan | Best USA | Best Taiwan |
| --- | ---: | ---: | ---: | ---: |
| Median image gradient RMS | 2.964e-15 | 3.365e-14 | 9.902e-16 | 1.335e-14 |
| Median state gradient RMS | 0.2180 | 0.1129 | 0.09103 | 0.4234 |
| Median paired zero-state amplification, excluding starts | **52.75×** | **1.1064×** | **1.00018×** | **1.00002×** |
| Median paired zero-state/original loss ratio | 1.2837 | 0.6727 | 1.3032 | 0.8526 |
| State removal increased loss | 10/10 | 0/5 | 6/10 | 0/5 |

Across all 18 samples, image-gradient RMS ranges are **1.01e-15–5.53e-14 final** and **4.09e-16–1.57e-14 best**. Image/state ratios range **2.28e-15–3.30e-13 final**, **2.27e-15–4.04e-13 best**. Thus the severe input imbalance is shared by both checkpoints and domains, while the effect of state removal is not. Final's paired amplification ranges **1.030–148.906×**; best's is **0.995874–1.001451×**. Even amplified final image gradients remain extremely small.

Zero image leaves the original loss effectively unchanged: maximum paired relative loss deviation is about **7.33e-8 final / 6.36e-7 best**. Its local image derivative increases ~3.2× at the zero tensor, which describes a different local derivative, not recovered image-dependent loss. Mismatched real states have median paired loss ratios **1.0856 final / 1.0169 best**, ranges **0.581–2.343 / 0.315–30.602**, and median total image-gradient amplification approximately **1.00002 / 0.99998**. State replacement can worsen or improve individual losses; loss dependence alone is not proof of a universally useful shortcut.

Supplemental component gradients use the same targets and the four exact weighted MSE terms at each stratum's quarter sample, under original and zero state. Their signed gradient sums agree with the imported original total-loss gradient. For USA-train pair 299, final's weighted path image-gradient RMS changes **7.710e-23 → 1.062e-14** upon state removal, while the total is dominated by the all-output term (**1.419e-15 → 1.234e-13**). Best's corresponding all-output contribution is **4.095e-16 → 4.078e-16**, while its path contribution remains much smaller (**1.580e-21 → 6.405e-20**). This reveals checkpoint-dependent recurrent gating/suppression in addition to the shared deep encoder attenuation. It does not establish the historical optimization mechanism or a successful image-based predictor.

### Teacher-state dependency and combined causal evidence

For the 15 nonzero histories, median cosine similarity of previous/current teacher latent state is **0.998603**. Copying previous state to predict current target state has median MSE ratio **0.002794** against a zero-state predictor; copying the entire previous teacher target has median custom-loss ratio **0.000600** against a zero target. The latter is a descriptive temporal baseline: the student receives only the previous 512-value latent, not the whole previous target. These comparisons show strong temporal predictability. They do not demonstrate a current/future target leak or establish that a learned recurrent mapping successfully exploits every sample.

| Observation | P2.7 evidence | P2.8 evidence | P2.9 evidence | Supports | Confidence | Remaining ambiguity |
| --- | --- | --- | --- | --- | --- | --- |
| Preprocessing collapse | Distinct model-ready images | Stored/decoded pairs equal; native scale matches training | Actual training samples and causal Taiwan extension retain same contract | Against preprocessing collapse on tested inputs | High locally | Untested recordings/calibrations |
| Encoder attenuation | Image interventions barely alter output | Progressive attenuation in trained and three fresh models | Embedding gradients ~1e-5 shrink to stem ~1e-14 | H1; P2.9-B shared | High locally | Exact initialization/training contribution |
| Recurrent shortcut | State changes output strongly | State-independent image collapse remains | Final-USA removal boosts image gradient and loss; best gradient barely changes; Taiwan loss improves without state | Conditional H3-compatible effect, not universal H2/C | Moderate, mixed | Local gradients cannot reconstruct optimizer trajectory |
| Teacher forcing | State feedback differs from training | Training pipeline uses teacher latent | Input equals prior target's latent slice, graph detached | Teacher forcing confirmed | High structural | Degree of learned exploitation |
| Target leakage | No direct evidence | No demonstrated future dependency | Current label row i, input latent row i-1; causal overlapping frames | Normal temporal dependence, no confirmed leakage | High for inspected dataflow | Teacher pretraining provenance not audited |
| Checkpoint-specific collapse | Both nearly image-invariant | Both attenuate | Both input ratios ~1e-14; removal response differs substantially | Shared encoder issue plus checkpoint-specific gating | High locally | Development over training time |
| Domain-specific collapse | Both domains affected | Both distinct inputs attenuate | Severe imbalance in USA train/validation and Taiwan; state utility differs by domain | Collapse shared; state effects domain dependent | High locally | Taiwan uses generated teacher targets, no driving ground truth |

**H1 is best supported as the common mechanism.** H2 alone is insufficient; H3 is plausible for final-USA but not strongly established across checkpoints/domains. H4 is not required to explain the observed shared encoder attenuation, although additional mechanisms remain possible. Choosing P2.9-B does not deny local state suppression: it avoids elevating that conditional finding into a universal shortcut cause. No claim of behavioral quality or target leakage is made.

### Validation, artifacts and one next experiment

**12 new tests + 77 prior tests = 89 passed.** Tests include analytical derivatives at original loss boundaries and a synthetic differentiable multi-output graph proving nonzero input/intermediate/parameter gradients. Sanity checks verify finite losses/gradients, trainable parameters, fresh tapes, repeated-gradient equality, batch-2 reduction, no stochastic mode difference, component-sum consistency, no optimizer creation, and identical in-memory/file checkpoint hashes. Before/after inventory covers **251 protected files**, including P2.5–P2.8 evidence, with no changes. The full professor archive matches its preserved copy. Project 1 status/validate pass after the isolated image rebuild. No protected source/checkpoint/output, initialization or architecture was modified; no training, commit or push occurred.

Artifacts under `/output/p29-gradient-audit/`: `samples.json`/`samples.npz`, `records.json`, `summary.json`, `per_sample_gradients.csv`, `counterfactual_gradients.csv`, `checkpoint_comparison.csv`, `layer_gradient_profile.csv`, `component_gradients.json`, `run_metadata.json`, `interpretation.json`, `README.md`, `gradient_depth.png`, and the integrity snapshot. Reports preserve scientific notation, sample identities and median/min/max spread. The plot is derived from saved records and visually checked. `samples.json`'s legacy-named `source_marker_sha256` field contains **label-file SHA-256 values** copied from the verified markers, not marker-file hashes.

**P2.10 completed:** the same audit was applied to three fresh default-initialized controls (seeds 3101, 3102 and 3103), with no updates, using the cached P2.9 samples. Results are documented below.

## 21. P2.10 fresh supervised-gradient controls (2026-10-06)

The control used student-owned `step10_gradient_controls.py` to construct three default-initialized `modelB6.get_model()` instances with seeds **3101, 3102 and 3103**, zero training steps, and the same 18 cached P2.9 samples. It used the imported original `custom_loss`, native training inputs, previous teacher state, zero desire and traffic `[1,0]`. Each fresh model covered all 18 original conditions (**54 trials**); no optimizer update was created.

| Fresh seed | Image input RMS | State input RMS | Image/state ratio | Stem RMS | Middle block4 RMS | Top RMS | Loss |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3101 | 2.528e-14 | 1.478e-3 | 1.836e-11 | 5.847e-14 | 5.505e-9 | 1.480e-4 | 60.3443 |
| 3102 | 2.111e-14 | 1.245e-3 | 1.626e-11 | 6.674e-14 | 4.952e-9 | 1.343e-4 | 60.3723 |
| 3103 | 2.182e-14 | 1.307e-3 | 1.751e-11 | 6.579e-14 | 5.108e-9 | 1.379e-4 | 60.3453 |

Fresh models already have a very small image/state input-gradient ratio (**1.626e-11–1.836e-11**) before training. Their image gradient is about three orders of magnitude larger than P2.9's trained final/best medians (**9.775e-15 / 2.580e-15**), while their state gradient is much lower (**1.245e-3–1.478e-3** versus **0.1907 / 0.2903**). The image encoder still attenuates gradients with depth: fresh stem is about **6e-14**, middle about **5e-9**, and top about **1.3–1.5e-4**. This shows that architecture-level attenuation predates training, while training further strengthens recurrent/state dominance and reduces the absolute image input gradient.

The result refines P2.9-B/H1 rather than replacing it. It does not reconstruct the historical Adam trajectory or prove a unique repair; the fresh controls are not the unavailable historical P2.5 initialization. No behavior-quality claim follows.

P2.10 validation: **4 new tests**, 54 finite records, three distinct seeds, all 13,039,435 parameters trainable per model, zero optimizer creation, unchanged fresh-model weight hashes, and the 248-file protected inventory unchanged. Results are in `/output/p210-gradient-controls/` (`records.json`, `summary.json`, `run_metadata.json`, `integrity_before.json`).

## 22. AI Agent baseline environment (2026-10-06)

The ModelB6 line was pushed before beginning the Agent work. The professor reference `external/aJLL/Agent/agent.py` was inspected without copying its copyrighted source into tracked files. It imports Agno `Agent`, Gemini, YFinanceTools, DuckDuckGoTools, ReasoningTools and Image, and selects Gemini `gemini-2.5-flash`; its active request is a reasoning-based travel prompt. The Agent does not share the OpenPilot Python 3.8 runtime.

Student-owned files now live under `projects/project2/agent/`: an ignored Python 3.11 `.venv`, pinned `requirements.txt`, `baseline_check.py` (offline source/import audit), and `baseline_agent.py` (minimal runtime baseline). Installation resolved Agno **3.1.1**, Google GenAI **2.28.0**, DuckDuckGo Search **8.1.1**, `ddgs` **9.16.0** and YFinance **1.7.0**, with transitive versions recorded in the requirements file. The first offline check exposed Agno's current DuckDuckGo implementation requiring the additional `ddgs` package; adding that isolated pin fixed the import check.

Offline validation passed: all required imports, reference source symbols and Python compilation passed. `GOOGLE_API_KEY` was absent, so the live Gemini request was deliberately skipped. No key was created, stored, logged or committed. The 5-Level framework and original “Do New” feature are not yet claimed complete; they require baseline behavior evidence and a design decision after the assigned material is reviewed.

The original “Do New” feature is now implemented as `projects/project2/agent/evidence_agent.py`. Its `summarize_p2_evidence` tool is read-only, permits evidence roots only under `/output` or temporary test storage, and extracts saved P2.9 checkpoint metrics without loading a model or changing any artifact. `do_new_tests.py` verifies structured output, read-only behavior and rejection of an unapproved root (**2/2 passed**). The live Gemini wrapper remains gated on a runtime `GOOGLE_API_KEY`; no key was available during this run. The local course doc names the 5-Level framework but does not include its definitions, so the repository records that boundary in `FRAMEWORK_REVIEW.md` rather than inventing a review.
