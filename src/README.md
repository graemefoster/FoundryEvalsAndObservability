# Five demos, one small Foundry hosted agent

**Start with [DEMO-PLAYBOOK.md](DEMO-PLAYBOOK.md).**
[PRESENTER-NOTES.md](PRESENTER-NOTES.md) has preparation, portal steps, recorded
results, fallbacks and the reasoning behind the demo.

The flow is **agent -> evaluation -> traces -> continuous evaluation -> optimiser**.
Use the portal and prepared results on stage, not live Python or deployments.
Continuous evaluation is an enablement walkthrough; it has not been configured.

## What's here

| Location | Purpose |
| --- | --- |
| `agent/main.py` | Native Agent Framework agent and Foundry `ResponsesHostServer` |
| `agent/tools.py` | Two read-only searches over eight fictional policy/notice documents |
| `agent/configuration.py` | Load baseline or native optimiser configuration |
| `agent/.agent_configs/baseline/` | Original instructions, model and tool descriptions |
| `agent/datasets/next-action/` | `golden-development.jsonl` (16 cases), `golden-holdout.jsonl` (12 cases) |
| `evaluators/purchasing-next-action.json` | One binary judge: the correct immediate next action |
| `evaluate.py` | Backstage native evaluation submission and optimiser preparation |
| `optimize-next-action.yaml` | Two-candidate native optimiser template |
| `tests/` | Offline runtime, dataset and evaluation contract checks |

The deployed baseline is `purchasing-advice-demo:1`, GPT-5.4-mini with low reasoning.
The judge and optimiser generator use GPT-5.5. Agent Framework owns the model/tool
loop; hosting supplies the protocol and platform telemetry. No custom spans or
orchestration. The agent cannot approve or place purchases.

The scenario date is fixed at **October 5, 2026**, not the wall clock.
Only questions reach the agent; reference answers are for evaluation.
No candidate is deployed. The new native-validation run completed: baseline 8/12,
selected candidate 1 9/12, candidate 2 8/12 on the holdout. Training mini-batches
used development cases; full candidate comparisons used holdout cases. See the
presenter notes for the distinction from the earlier 16/16 development-only result.

## Backstage commands

Run from `src/` with Python 3.13, `uv`, Azure sign-in and the existing `azd`
environment. `.env.example` documents the endpoint variable; it is not auto-loaded.
These are operator tools, not steps to type during the talk.

```bash
# Local preview: no credentials or model calls.
uv run --frozen python evaluate.py --dry-run

# Billable: Foundry calls the deployed agent on the 16 development questions.
uv run --frozen python evaluate.py

# Read an existing run; does not submit another.
uv run --frozen python evaluate.py --show EVAL_ID RUN_ID
```

`--prepare-optimizer` registers the judge and freezes separate development and
holdout inputs. The latter is passed as native `validation_dataset`, not added to
training. Preparation does not submit a search. `--release` selects
`golden-holdout.jsonl` for a standalone evaluation and should not be used for
tuning. See [preparation commands](PRESENTER-NOTES.md#optional-new-runs-backstage-only).

The existing source-code hosting definition in `azure.yaml` reuses the Foundry
project. Deploy only when intentionally changing the agent:

```bash
azd deploy purchasing-advice-demo -e ai-genius-hosted --no-prompt
```

Do not provision/delete shared resources or apply a candidate as a demo reset.
The GitHub workflow runs offline checks, not continuous evaluation.

Older evaluator modes, datasets, stage guides and the unrun changed-policy staging
experiment were removed from the active demo. A byte-preserved local copy is under
`evidence/archive-before-focused-demo/`. Evidence is ignored by Git: a new checkout
needs its own runs or a deliberate copy of the recorded evidence. Slides, assets
and the existing presentation brief are unchanged.
