# Diagnosis / Unified 3.5 Flash-Lite live receipt reviews — 2026-10-14

The user ran Diagnosis with `GEMINI_MODEL_ID=gemini-3.5-flash-lite`. The supplied
terminal transcript contains completed JSON and return to the shell prompt;
`gemini_executed=true`, report nonempty, and six tool entries have `error=false`.
Thus **live execution / response completion PASS** for this run. This does not
establish that 503 is globally resolved or all report claims passed review.

Tools reported: gradient, fresh gradient, sensitivity, training, encoder and domain
comparison. Exact transmitted tool payloads/arguments are not included in this
receipt; the review independently reads existing checksum-verified local exports.
No provider request, retraining or experiment was initiated by this review.

## Content review: PARTIALLY SUPPORTED — corrections required

| Report statement | Canonical evidence / correction |
|---|---|
| Overall image gradient ~1.39e-14 and state-parameter gradient ~0.020 | These match **mismatched_state** aggregate medians (1.39566e-14 / 0.0204674). The final/original overall medians are 9.77476e-15 / 0.0132107. Name role, domain, intervention, metric and median explicitly. |
| Encoder decreases from ~73.5 to final addition ~0.017 | ~0.017 is intermediate `block3b_add` baseline RMS. Final trained flatten baseline RMS is ~5.00381; the cross-domain **difference RMS** there is ~3.70732e-7 (stem difference ~19.0898). Activation magnitude and input-dependent difference are distinct; the report conflates endpoint and signal. |
| Final path max absolute deviation >20 m | The source is `path_near_abs_max_m`: predicted near-path coordinate magnitude, not error/deviation from ground truth. USA 20.4660 / Taiwan 21.7146; best 1.55516 / 1.45516. |
| Hundreds of nonpositive frames associated with path degradation | Counts are `lane_width_near_nonpositive_frames`: USA 1006 / Taiwan 941. They describe nonpositive lane width, not path-negative frames. |

Training facts (60 epochs, final losses 3.20409 / 71.71458, best validation 0.52541
at epoch 25) match. The report correctly retains uncertainty about overfitting,
universal shortcuts, initializer-only causality and driving/closed-loop quality.
Fresh-control top/stem orders ~9.3–9.4 agree, but this is positive log10(top/stem)
for backward-gradient attenuation toward the stem; it is not forward feature RMS.

Overall status: **execution PASS; report factual acceptance pending corrections**.
At the Diagnosis review, Unified had no new successful receipt; see the later
Unified review below. Existing 3.8 default is unchanged;
this successful execution used a command-scoped 3.5 override. There is no basis
to mark all extra v2 live acceptance complete or edit the delivered v5 report.

The local ignored evidence folder `artifacts/live-reviews/diagnosis-35lite-20261014/`
contains original transcript, parsed JSON, receipt hash, canonical source hashes
and review facts. Source definitions: `v2_evidence.py` and its approved exports.

## Subsequent Taiwan/best Unified receipt

The user supplied completed Unified JSON using the same command-scoped 3.5 model
and image `step6/taiwan/best/frame_00001.png`, followed by the shell prompt.
Image SHA `2a46e36a96b78ed0ff6edd9e9f256240cca06fd1f0b405ecc95d4122bf849a5d`
matches the approved local PNG; dimensions are 1200×900. Execution/response
completion PASS. This transcript had no tool-name/result trace; the SDK warning
about function_call non-text parts is not a provider error, nor proof of completed
numerical tool execution. Installed SDK text access warns when non-text parts
exist; installed Agno separately parses function_call parts.

Visual review of the actual PNG:

- Night road, overpass, traffic, signs and store lighting: supported qualitatively.
- Green path has spatial jaggedness: supported; this still cannot establish temporal
  oscillation. Red/blue lines also have visible irregularities, especially top-down.
- Correct lane-boundary alignment and smoothness: overstated from this still;
  source overlays, projection and ground truth do not establish accurate tracking.
- Red-car-to-model-lead correspondence: unsupported. Vehicles are visible but the
  figure has no explicit lead marker/link to validate a model-lead association.
- Both numerical comparison fields say Not evaluated: no substantive integration
  demonstrated. Full Unified acceptance remains pending, despite completed JSON.

A minimal student-code improvement now emits tool names/error flags (without
arguments) and makes the default Unified question request verification/domain
tools, sourced metrics and explicit separation of clip aggregates vs this frame.
Lead instructions explicitly disallow matching a visible vehicle to model lead
without associated evidence. This improves observability/instructions; it does
not retroactively repair the submitted report or guarantee a correct next answer.
Two new mocked tests verify trace privacy and default/custom prompt behavior.
Current offline Agent suite: **49/49 PASS**, no failures/skips. No API request,
model/dependency change, training or delivered-report change was made.

## Subsequent Diagnosis retry: original reference correct, generated prose still rejected

The next user attachment contains **Diagnosis only**. It completed on 3.5 with
`tools=[]`. Every shared field in the returned `verified_reference` matches the
current authenticated local readers; this is deterministic preflight, not a
model-selected tool trace. The earlier intervention/encoder endpoint/path metric
identity issues are improved in the detailed evidence section.

The generated concise table nevertheless copies USA final count **1006** into
Taiwan final; authenticated Taiwan count is **941** (the same report states 941
correctly in its earlier section). Further prose overstates overfitting and
encoder saturation, calls two-clip instability generalized collapse, and proposes
deployment/early-stopping implementation outside the current read-only scope.
Execution completed, but content is **REJECTED / corrections required**. No new
Unified receipt is present in this attachment.

Software response: explicit claim-catalogue classifications, mechanism limits and
allowed next action are included in authenticated context. The exact Step6 fact
table is rendered in code as `verified_evidence_table`; the default model question
no longer requests a duplicate transcription. Scoped numeric Markdown table rows
are checked against their domain/checkpoint/metric/source; this actual receipt
is rejected for 1006 vs 941. Rounded continuous values allow relative tolerance
1e-5; counts must match exactly. Unparsed prose is never counted as validated.
The content-validation status remains HUMAN_CONTENT_REVIEW_REQUIRED, not PASS.
These checks do not constitute a general causal/semantic verifier and cannot
promise that every future model sentence is correct.

Five new regression tests and all prior tests pass: **64/64**, zero failures/skips.
The real submitted receipt was also tested offline against the guard; the generated
canonical table checks 12 scoped numeric rows correctly. Receipt and checks are
preserved locally under `artifacts/live-reviews/diagnosis-retry-20261014-02/`.
No new API call, model/dependency/default change, training, deployment, commit or
push. New live content acceptance remains pending; no repeated API call is needed
to establish that this submitted draft contains the identified errors.

## Subsequent Unified retry: numerical comparison demonstrated, interpretation qualified

The user supplied completed Taiwan/best Unified JSON on 3.5. Image identity,
SHA, dimensions and the **entire** numerical_reference equal local authenticated
readers. The report cites the correct domain/checkpoint/source with
`path_near_abs_max_m=1.4551631212234497`, `path_near_mean_m=0.02472166662830858`,
nonpositive lane-width count 0 and 1201 frames. Its non-comparable per-frame error
statement is appropriate; visible vehicle/model-lead correspondence remains unknown.
Thus execution and sourced clip-summary comparison are PASS in that bounded scope.
`tools=[]`: the model used preflight context; model-selected tool execution is not
shown by this receipt and is not inferred from the local reference readers.

The final statement that spatial jitter is "averaged out over the 1201-frame clip"
is unsupported. `step6.py::summarize` takes near-path positions `[:,4:40]` across
frames, reporting coordinate mean/max and separate temporal change; it does not
measure removal of full-path spatial wiggles by averaging. A small mean does not
establish spatial smoothness, accuracy or a causal temporal averaging mechanism.
Lane smoothness/alignment remains a limited qualitative impression; the actual
plot includes irregularities in the top-down curves.

Bounded replacement: "The clip's near-path coordinate summaries are limited in
magnitude while this still shows spatial jaggedness along the predicted path.
These describe different properties; they do not establish that temporal averaging
removes spatial jitter or that predictions match ground truth."

Overall content remains PARTIALLY SUPPORTED / correction required, rather than an
unqualified full live acceptance. No new Diagnosis receipt was included here.
Original receipt/result/review are locally preserved under
`artifacts/live-reviews/unified-retry-20261014-02/`. This is a review-only update:
no API call, source/prompt change, new test run, training, commit or push. The
last executed offline suite remains 64/64 for its recorded implementation.

## Latest Diagnosis retry: bounded content review PASS

The latest user attachment contains completed Diagnosis on 3.5. The entire
`verified_reference` exactly matches current authenticated local readers, and
`verified_evidence_table` exactly matches the code-generated table. USA final
nonpositive lane-width frames are 1006, Taiwan final 941. All seven explicitly
stated claim-catalogue classifications match canonical values. The current
narrative preserves uncertainty about overfitting, initialization, saturation,
training-only causation, generalized collapse and driving quality. It restricts
next action to existing-evidence review, with no deployment/training recommendation.

**Execution PASS and content review PASS for this bounded submitted summary.**
This is not a driving-quality finding, complete independent research validation,
or proof of model-selected tool use. `tools=[]` remains an explicit distinction:
this response summarizes deterministic preflight context rather than demonstrating
agent-selected tools.

`content_validation.checked_step6_table_rows=0` is expected because the model no
longer duplicates the table in prose. The separately returned verified table is
an exact match; offline checker processes its 12 numeric rows. The program keeps
HUMAN_CONTENT_REVIEW_REQUIRED as a conservative runtime label; this separate
receipt review records the performed content check without pretending the runtime
is a universal semantic verifier.

Original transcript, parsed response and review are preserved locally under
`artifacts/live-reviews/diagnosis-retry-20261014-03/` (transcript SHA-256
`4cc7b5f1ad929dc6c797f6bb568600f1474c8ee5f61ea52a4bf6a1b90a910193`).
No new Unified receipt is included; its prior numeric-reference comparison PASS
and spatial-averaging qualification remain unchanged. No API/source/prompt change,
new test run, training, commit or push. Last executed offline suite remains 64/64.

## Post-review software optimizations (no new live receipt)

Progress/budgets/retries, concise output with full local records, meaningful
optional tool verification and a targeted averaging-claim guard were added after
these receipts. Current offline suite 87/87, P3 regression 50/50; no API request.
See RUNNING.md and audit §41. Historical user receipts are not rewritten as tests
of the new worker/retry mode; those real live behaviors still require a user run.

## Optimized preload CLI: both real user runs complete

The user ran optimized Diagnosis and Taiwan/best Unified at 22:26 on 2026-10-14
(Asia/Taipei), on gemini-3.5-flash-lite. Real local run directories are:

- `artifacts/live-runs/20261014-222611-diagnosis-676c58ed`: COMPLETED, 5.355 seconds,
  one attempt; all 10 manifest-listed files match their SHA-256 values.
- `artifacts/live-runs/20261014-222629-unified-8cc86599`: COMPLETED, 6.667 seconds,
  one attempt; all 10 manifest-listed files match their SHA-256 values.

Recorded fact/source context matches local readers. Worker stage logs retain all
steps even when rapid changes are not individually shown by console polling.
Progress, local record creation and concise rendering are verified on this success
path. No live transient retry, timeout/cancellation or verify-mode behavior is
inferred from these two success runs; those retain their offline test evidence.
Both use preload mode and tools are empty, accurately labeled NOT_DEMONSTRATED.

Diagnosis classifications/causal limits are acceptable within the bounded summary
scope. Prefer primary P27 sensitivity citation for image-invariance; allowed
next-action restrictions are task policy rather than a finding measured by P27.
Unified fixes the prior averaging-mechanism overclaim and preserves lead/accuracy
limits. Its remaining erroneous qualifier `aggregation=median` is attached to Step6
count fields. Counts 0 and the supplied numerical facts are correct, but the
aggregation label is not: nonfinite/extreme/nonpositive frame metrics are counts,
path_near_mean_m is an arithmetic mean. The corrected numerical comparison should
identify these as clip-level counts with no median qualifier.

Review-only corrections are separate from immutable original run records.
Additionally, software now supplies metric_reductions in Unified context, limits
the gradient median rule explicitly to gradient audits, and rejects the observed
positive aggregation=median qualifier in Step6 comparison. Two added tests pass;
current Agent suite **89/89**, no failures/skips. The new guard rejects this actual
submitted median-label error offline. No new API request; fresh run content with
these extra definitions is not yet live-tested. Original run files were not edited.
The user transcript and review are saved under
`artifacts/live-reviews/optimized-preload-20261014-01/`.

## 22:55 required-tools receipts and protocol revision

Original immutable run IDs: `20261014-225523-diagnosis-079d9899` and
`20261014-225544-unified-d3d736b7`. Both run.json statuses FAILED.
All 8 manifest entries per run verified; earlier two preload runs each retain
10 matching entries and COMPLETED. Diagnosis draft contains successful
get_training_evidence and check_diagnostic_claim only; gradient/encoder missing.
Unified draft tools=[]; content exists but cannot satisfy verify. No provider
503 was reported in either run. Preloaded evidence + instructions did not enforce
complete tool use. Structured output and tool use are now separated; this is a
protocol correction, not proof that schema constraints alone caused the omission.

Revised verify uses one required tool per model request with ANY and
stop_after_tool_call; verifies actual results and the overfitting argument before
continuing. Collected outputs feed the final report; the final typed request has
no tools. Application selects the checks. No autonomous-selection claim.
96 offline tests pass, including missing results, wrong claim arguments, provider
status, constructor configuration and both final-report integrations. No API call
was made by this revision; revised live acceptance remains NOT VERIFIED.
PPTX v6 updates slides 2/33/36/37/38 without changing model results.

## 23:06–23:07：新版必要工具流程 live 完成（audit §44）

- Diagnosis `20261014-230632-diagnosis-5ae5d652`：COMPLETED，單次 attempt
  29.301 s；training／gradient／encoder／overfitting 四個必要工具均有成功回傳。
- Unified `20261014-230705-unified-598a0b14`：COMPLETED，單次 attempt
  6.857 s；verification／compare_domains 兩個必要工具均有成功回傳。
- 兩份 manifest 各12項全數匹配；六個實際工具回傳逐一解析後與 canonical
  readers 相等；保存的 Python source hashes 與目前版本完全一致。
- 選擇工具的是程式，模型發出 function calls；不能升級為自主工具選擇或
  跨樣本可靠度的驗證。96項離線測試為先前同來源版本的結果，本輪無須重跑。

內容審閱：數值與七項 claim 分類吻合，但 Diagnosis 段落把 fresh-gradient
9.30–9.40 orders 誤引到 P2.8 reference_controls；正確來源為
`/output/p210-gradient-controls/summary.json`。Near image-invariance 的主要
依據應是 P2.7 image interventions，不能僅靠極小 loss gradients 證明。
Unified 的「moving vehicles」改為「visible vehicles」；單張不能確認移動，
也不確認前車 lane／model-lead 關聯。數值對照與 clip-versus-frame 限制可保留。

助理依 canonical sources 審閱，結論為 ACCEPT_WITH_DOCUMENTED_REVIEW_CORRECTIONS；
這不是使用者已人工簽核、也不是所有自然語言自動驗證通過。原始 run 目錄與
模型逐字輸出完全保留；審閱稿另存 `artifacts/live-reviews/required-tools-success-20261014-01/`
的 `diagnosis-reviewed.md`／`unified-reviewed.md`，清楚標示非原始逐字輸出。
本輪只更新審閱紀錄／文件與v7簡報，未改執行程式，未呼叫 Gemini、訓練或 commit/push。
目前不需為相同樣本再重複執行這兩個指令。新的影像、domain 或模型才是額外覆蓋，
並不屬本次兩項必要工具成功路徑的缺口。

## 2026-10-15 教授審閱版狀態用語

使用者最新指示保留 Diagnosis／Unified「LIVE EXECUTION CONFIRMED／
CONTENT REVIEW PENDING」。先前助理審閱與另存的修正稿保留為候選修正，
不升級為使用者已完成最終內容驗收。此狀態在精修v7的2/33/36/37/38頁明示。
本輪簡報精修沒有重跑Agent或修改原始live結果。


## 2026-10-16：依使用者要求完成指定實測的內容核對

重新驗證23:06／23:07兩次成功run的24項manifest、來源Python hashes、
6項實際工具payload及reference contexts，全部吻合目前canonical readers。
本次亦對照原始PNG與逐項解讀；補正P210來源、P27主要依據，並收斂
Unified的移動／同車道／lead／車道對齊措辭。數字核對與內容修正已完成，
原始逐字輸出不變，修正稿另存。此狀態取代上節「等待最終內容驗收」用語，
不代表使用者已簽核或跨樣本可靠度。完整核對見
`reports/evidence/project2/Agent-Content-Review-20261016.md`；簡報v8同步更新五頁。
未新增API呼叫、實驗、訓練或runtime程式修改。
