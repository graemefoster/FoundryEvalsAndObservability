# proposed/workflows

Move these four files into `.github/workflows/` (Claude can't write there from the device bridge).
Then delete `deploy-and-evaluate.yml`, `local-checks.yml` and the earlier `agent-gate.yml`, which these replace.

| File | Trigger | Runs | Blocks? |
| --- | --- | --- | --- |
| `agent-pr.yml` | Pull request | Lint + dry run + prompt fact check, then the development set (demo-storyline) vs baseline | Yes |
| `agent-main.yml` | Merge to main | Holdout vs baseline | No (warns) |
| `agent-release.yml` | Manual, or a `v*` tag | Drift set, must-pass, scores only; then approval via the `production` environment | Yes |
| `_agent-eval.yml` | Called by the three above | Deploy, evaluate, compare or save baseline | - |

First run: trigger each workflow manually with **write_baseline** ticked, download the
`baseline-<dataset>` artifact, and commit it as `sample/evaluation/baselines/<dataset>.json`.
