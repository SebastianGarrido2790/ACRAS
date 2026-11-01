# A-02 / DVC Remote Provision Note (A-02 / D-09 / R-14)

Status: DVC graph installed (`dvc.yaml` updated to proposed topology; `reports/docs/phases/pre-phase_4_remediation/dvc.proposed.yaml` preserved as reference); remote `../../acras_dvc_remote` configured in `.dvc/config` but directory absent.

Exception (approved A-02, `wave_a_return.md` §7.2 / `remediation_plan.md` §4 R-09):
- Clean-clone reproducibility requires re-acquire via `dvc pull` against `../acras_dvc_remote`; if remote is unavailable, the exception path is documented here.
- ADR-011 checksum verification (`reports/docs/grounding/adr_011.md` or equivalent) must be performed when the dataset is re-acquired; `dvc.yaml` `validate` stage produces `outputs/gate_signal.txt` only on full pass.
- Fallback: if `dvc pull` fails and remote cannot be restored, the dataset (`data/raw/data.csv`) must be verified against ADR-011 expected dimensions/checksum before any `train` stage runs; `validate` exits non-zero on checksum mismatch.

Actions taken (A-02 applied):
- `dvc.yaml` updated to proposed `validate -> train -> evaluate_gate` topology.
- `.dvc/config` remote `local_storage` preserved (approved design, no cloud remote change).
- No remote directory created; exception path documented above.

Pending (owner separate approval for remote change):
- Create/provision `C:\Users\sebas\Desktop\acras_dvc_remote` (repo sibling) to resolve clean-clone `dvc pull`; does not require new decision if within A-02 approved scope.
- If remote cannot be restored, run full re-acquire + ADR-011 checksum verification as exception.
