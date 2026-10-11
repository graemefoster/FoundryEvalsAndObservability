# Overfitting demo (the dinner storyline)

The exhibit for "how the optimiser cheats, and how you catch it". It isn't part of the CI pipeline.

| File | Role |
| --- | --- |
| `demo-storyline.jsonl` | 8 near-identical team-dinner questions. This is the training set that made memorising the cheapest win. |
| `golden-holdout.jsonl` | 24 varied policy questions, used as validation. This is what caught the memorising. |
| `optimize.yaml` | Reproduces the run: `azd ai agent optimize --config evaluation/overfitting-demo/optimize.yaml` (from `sample/`). |

What happened on 11 Oct 2026: on its 3 training questions the candidate went from 0/3 to 2/3; on the holdout it fell from 16/24 (67%) to 11/21 (52%). The optimiser kept the baseline. The candidate's prompt also failed `check_prompt_facts.py` on 14 copied facts (names, amounts, dates).

The pipeline's datasets are in `../datasets/`: `approvers-development` (development), `approvers-holdout` (holdout) and `approvers-drift` (release).
