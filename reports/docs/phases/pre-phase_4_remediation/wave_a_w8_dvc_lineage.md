# Wave A · W-A8 Evidence Report — DVC Lineage Design & Clean-Clone Reproducibility

*ACRAS · 2026-10-23 · Wave A (design + reproducibility evidence; no pipeline or remote change).*
*Source: [`execution_plan.md`](execution_plan.md) §2 W-A8 · authority: `remediation_plan.md` §4 R-08 / R-14 / D-09.*

## 1. Result summary

| Item | Result |
| --- | --- |
| Live `dvc.yaml` | Unchanged: `validate` → `stub_train` only (**no** training/promotion lineage) |
| Proposed graph | `validate` → `train` → `evaluate_gate` (draft in [`dvc.proposed.yaml`](dvc.proposed.yaml)) |
| Real `dvc dag` on draft | Valid; `validate` gates both `train` and `evaluate_gate` |
| `train` deps include raw + params + gate signal | **Yes** |
| Failing promotion gate | `PromotionGateError`, CLI exit 1, **bundle not written** |
| Dataset integrity | SHA-256 + MD5 + size match ADR-011 exactly |
| `dvc data status` | `No changes.` |
| Clean-clone `dvc pull` | **Blocked**: local remote `C:\Users\sebas\Desktop\acras_dvc_remote` is absent |
| `dvc.lock` | Absent → the pipeline has never been reproduced end-to-end |

## 2. Current-state findings

### R-08 — no training/promotion lineage in DVC

- Live `dvc.yaml` has two stages: `validate` (GX contract → `outputs/gate_signal.txt`) and `stub_train` (no-op gate proof). Neither declares `params.yaml`, a model, metrics, or a promotion output.
- `dvc status` reports **every** stage dependency as `modified` and logs `Lockfile for 'dvc.yaml' not found`; no `dvc.lock` exists. The graph has never been materialized.
- Training/export code exists and works standalone (`feature.split` → `training.train` → `training.promote`), and INV-3/INV-7 are enforced inside those modules — but the DVC graph does not encode that workflow. This is a governance/reproducibility gap, not evidence that validation is bypassed.

### R-14 — clean-clone retrieval is not currently supported

- `.dvc/config` resolves the remote to `C:\Users\sebas\Desktop\acras_dvc_remote` (sibling of the repo; the `../../` is relative to `.dvc/`). **That directory does not exist** in this environment.
- `dvc status -c` reports `new: data\raw\data.csv` → the remote has no copy of the tracked dataset.
- Consequence: a fresh clone (empty `.dvc/cache`) cannot `dvc pull` the dataset, so `dvc repro` cannot run.
- The dataset itself is intact locally and matches the ADR-011 pin:

| Check | Observed | ADR-011 / `.dvc` |
| --- | --- | --- |
| SHA-256 | `67BF2E7C75490F7AD3F76BBCE57D49CDC25967CDAB607527B94F944863FA14D8` | same |
| MD5 | `DA9CDA1B8F7CB99D03FBB65B86C15B0F` | `da9cda1b8f7cb99d03fbb65b86c15b0f` |
| Size | `11,456,101` bytes | `11,456,101` |
| `dvc data status` | `No changes.` | — |

- `mlruns/` is git-ignored, so MLflow run history is local-only; the durable promotion artifact is the `joblib` bundle.

## 3. Proposed topology (draft, not installed)

Full draft: [`dvc.proposed.yaml`](dvc.proposed.yaml). The three-stage shorthand is realized as:

| Stage | Command (summary) | Key deps | Outputs |
| --- | --- | --- | --- |
| `validate` | `validate_gate data/raw/data.csv --gate-signal outputs/gate_signal.txt` | raw CSV, validate/contract code, committed GX suite | `outputs/gate_signal.txt` |
| `train` | `feature.split … && training.train …` | raw CSV, `params.yaml`, **gate signal**, split/train/schema code | `data/processed/*.parquet`, `artifacts/preprocessor.joblib`, `reports/model_leaderboard.csv` (metric, `cache: false`) |
| `evaluate_gate` | `training.promote --output-bundle artifacts/promoted_model_bundle.joblib` | `params.yaml`, **gate signal**, processed parquet, transformer, promote/gate/train code | `artifacts/promoted_model_bundle.joblib` |

Design decisions recorded:

1. **`train` chains the two existing CLIs** (`feature.split` then `training.train`) because they are separate entrypoints today. A thin orchestration module is the cleaner Phase-4 alternative.
2. **The gate signal is a direct `evaluate_gate` dependency**, so promotion is gated on INV-7 both transitively (via `train`) and directly. Real `dvc dag` shows the `validate → evaluate_gate` edge.
3. **`reports/model_leaderboard.csv` is declared as a git-tracked metric** (`cache: false`). `data/processed/*` and `artifacts/*` are git-ignored and become normal DVC outs.
4. **Lineage caveat:** `run_stage_5_promotion` re-trains the winning configuration inside `promote` rather than consuming a model artifact from `train`. Given fixed seeds this is deterministic, but the promoted object is a re-fit, not the exact `train` object. Preferred Phase-4 variant: persist the winner from `train` as a candidate bundle and have `evaluate_gate` gate/export that object (small refactor, post-approval).

## 4. Dry-run graph check (falsification)

Run against a throwaway `dvc init --no-scm` copy of the draft (the live repo was not modified):

```text
$ dvc stage list
validate       Outputs outputs/gate_signal.txt
train          Outputs data/processed/X_train.parquet, data/processed/X_test.parquet, ...
evaluate_gate  Outputs artifacts/promoted_model_bundle.joblib

$ dvc dag
        +----------+
        | validate |
        +----------+
         **        **
       **            *
      *               **
+-------+               *
| train |             **
+-------+            *
         **        **
           **    **
             *  *
      +---------------+
      | evaluate_gate |
      +---------------+
```

Structural checks (all pass):

- Stage order is `["validate", "train", "evaluate_gate"]`.
- `train.deps ⊇ {data/raw/data.csv, params.yaml, outputs/gate_signal.txt}`.
- `evaluate_gate.deps ⊇ {params.yaml, outputs/gate_signal.txt, data/processed/*.parquet, artifacts/preprocessor.joblib}`.
- `evaluate_gate.cmd` invokes `src.pipelines.training.promote`; its out is `artifacts/promoted_model_bundle.joblib`.
- `train.cmd` invokes both `src.pipelines.feature.split` and `src.pipelines.training.train`.

Gate-failure behavior (direct call with failing probabilities; `y_test` n=1,364, base rate 3.2258%):

```text
Model promotion rejected: PROMOTION BLOCKED: FAILED BOTH calibration
(Brier=0.032258 > 0.03) and discrimination (AUC=0.500000 < 0.85).
promotion_gate_error_raised = true
bundle_written = false
```

The gate is evaluated **before** `joblib.dump` in `promote_and_export_model`, so a failing candidate cannot write the promoted artifact; the CLI maps the exception to exit code 1. DVC therefore marks `evaluate_gate` failed and does not record the bundle as an out.

## 5. Clean-clone reproducibility walkthrough

### Supported path (when the local remote is provisioned)

```powershell
git clone https://github.com/SebastianGarrido2790/ACRAS.git
Set-Location ACRAS
uv sync
# Remote must exist at C:\Users\sebas\Desktop\acras_dvc_remote (sibling of the repo)
uv run dvc pull
uv run dvc data status          # expect: No changes.
uv run dvc repro                # once the proposed graph is approved/installed
uv run dvc status               # expect: up to date (after dvc.lock is committed)
```

### Fallback if the remote is unavailable (documented exception, not a silent change)

Re-acquire the pinned Kaggle snapshot (ADR-011) and verify before use:

```powershell
# Expected: 6,819 rows × 96 columns; 11,456,101 bytes
(Get-FileHash data/raw/data.csv -Algorithm SHA256).Hash  # 67BF2E7C...863FA14D8
uv run dvc add data/raw/data.csv                          # regenerates da9cda1b...
uv run dvc data status                                    # expect: No changes.
```

### Windows PowerShell quickstart (README gap)

README uses `cp .env.example .env` (Unix). The supported Windows equivalent is:

```powershell
Copy-Item .env.example .env
$env:GEMINI_API_KEY = "..."   # never commit .env
$env:GROQ_API_KEY   = "..."
```

`.env.example` exists and matches the referenced filename; `cp` is the only Unix-only step.

## 6. Phase 1 corrective note

The Phase 1 DVC pipeline is a **Phase 0 gate proof**, not a reproducible Tier 1 pipeline. It has no `params.yaml` dependency, no model/metrics/promotion outputs, no `dvc.lock`, and no reachable remote copy of the dataset. The training and promotion commands are real and enforce INV-3/INV-7, but they run outside the DVC graph. Corrective action (pending approval): install the proposed three-stage graph, commit the generated `dvc.lock`, and keep the accepted local remote unchanged. MLflow remains the tracking record; the `joblib` bundle is the durable promotion artifact.

## 7. Decisions / open items

1. **Approve or reject installing** `dvc.proposed.yaml` as the live `dvc.yaml` (D-09 scope decision). The draft is not installed.
2. **Remote:** provision `C:\Users\sebas\Desktop\acras_dvc_remote` **or** accept the documented re-acquire-and-verify exception. Do not switch to a cloud remote without separate approval (D-09/D-11).
3. **README:** add `dvc pull` to the clean-clone steps and a PowerShell `Copy-Item` quickstart (change-managed edit; not applied here).
4. **Hygiene:** add `outputs/` to `.gitignore` (the gate signal is a DVC out, currently unignored).
5. **Lineage refinement (Phase 4):** persist the `train` winner as a candidate bundle so `evaluate_gate` gates that exact object instead of re-training.
