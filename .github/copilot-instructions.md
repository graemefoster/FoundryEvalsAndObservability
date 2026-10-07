# Repository context and working agreements

## Start here

Read `PLAYBOOK.md` before changing this repository. It is the single source for
the presentation flow, recorded experiment results, service IDs and commands.
These instructions guide coding assistants; the hosted agent's instructions
are in `sample/agent/.agent_configs/baseline/instructions.md`.

This is a presentation and deliberately small demonstration, not a production
agent framework. The story is **agent -> evaluation -> traces -> continuous
evaluation -> optimisation**. Keep the audience focused on those concepts.
The user's priority is simplicity: avoid scaffolding, abstractions, helper
layers and documentation that obscure the sample.

## Layout

- `presentation/deck.html` and `presentation/presentation.pptx`: presentation
  formats. All seven images in `presentation/assets/` are referenced by HTML.
- `sample/agent/`: the deployable Python agent, baseline configuration and
  fictional policy/notice documents.
- `sample/evaluation/`: `evaluate.py`, `optimize.yaml`, the binary evaluator
  definition and separate development/validation JSONL datasets.
- `sample/azure.yaml`, dependency manifests and lock files: runnable sample
  configuration. Run backstage commands from `sample/`.
- `sample/infra/monitoring.bicep`: companion deployment for Application Insights,
  its project connection and account-level Foundry User access for the evaluator.
- `PLAYBOOK.md`: the only presenter/operator guide. Update it rather than
  introducing another README, presenter-notes file or historical run sheet.

Do not restore the removed `src/`, test suite, historical datasets, slide-review
screenshots or template/conversion files unless requested. Generated
`sample/evidence/` remains ignored; the demo script does not generate evidence files.

## Agent design

- Native Microsoft Agent Framework with `FoundryChatClient` and
  `ResponsesHostServer`. Hosting and Agent Framework own tracing and the
  model/tool loop. Do not reintroduce custom spans or orchestration.
- Two read-only tools search local JSON via SQLite FTS5, returning up to three
  whole documents per call. They simulate policy/workplace knowledge:
  **neither real Foundry IQ nor Work IQ is connected**.
- The agent advises on purchasing; it cannot approve, buy or contact approvers.
- Keep mutable policy facts in retrieved documents, not system instructions or
  tool descriptions. Preserve native optimiser configuration loading.
- Use the decision date supplied in the question. Ask if it is needed and
  missing. Do not inject today's date or restore a fixed sample/reference date.
  Policy effective dates come from retrieved documents.

## Evaluation and optimisation

The objective is **next best action**, not always next best question:
ask for missing decision facts, identify outstanding requirements, or recognise
readiness. Do not list alternative routes before resolving missing facts or
reopen approvals already supplied as complete.

- One binary `purchasing-next-action` judge is shared by evaluation and
  optimisation. Do not silently change its rubric to improve a score.
- Only the question goes to the agent. The judge receives the question,
  `ground_truth` and final answer. The optimiser service receives references;
  its exact internal reflector inputs have not been established.
- Python submits the static development evaluation using an existing judge
  version; `--dry-run` prints the request. No registration or report download.
  Optimisation uses the static baseline,
  separate datasets and registered judge version in `evaluation/optimize.yaml`.
  Dataset paths resolve from the service's `sample/agent/` directory, not the YAML.
- **`azd ai agent optimize` submits optimisation jobs.** Python is not a
  replacement optimisation engine. Submit `evaluation/optimize.yaml` directly;
  no Python preparation or copied input package is needed.
- Preserve separate development and native `validation_dataset` inputs.
  Validation influences candidate selection; it is not untouched acceptance.
- Inspect effective system instructions **and tool/parameter descriptions**.
  A mutation record alone may omit inherited candidate configuration.
- The CLI can rewrite baseline `metadata.yaml` to reference frozen tools.
  Preserve evidence, compare tool bytes, then restore only the unintended path.
  The local baseline normally uses `tools_file: tools.json`.

CLI evaluation is possible. The user deliberately chose to retain the proven
Python workflow. `azd ai agent eval` and the separate `azd ai eval` extension
have different configurations; do not conflate them or claim golden-data
evaluation is unsupported. Do not restart that migration without a request.

## Recorded state at October 7, 2026

Treat this as a dated handoff, not a substitute for checking live state:

- Fresh-project baseline: `purchasing-advice-demo:1` in
  `ai-genius-fresh-20261007`, GPT-5.4-mini, low reasoning. Registered judge
  version 1; judge/generator GPT-5.5. No candidate promoted.
- Current corpus: 19 policies and five notices; 32 development and 24 validation
  cases. All 56 questions have explicit decision dates.
- Historical October 6 version-3 experiment: development baseline 16/32; same-set validation baseline
  16/24, candidate 1 16/24, selected candidate 2 17/24. Policy facts remained
  embedded. Only six distinct development cases appeared in recorded training
  mini-batches; all 24 validation cases appeared in each full comparison.
- The source without the October 5 fallback date is deployed in the fresh
  project. Do not label historical version-3 scores as results for this source.
- Native provisioning omitted monitoring and gave the caller only project-level
  Foundry User access. The companion Bicep supplies monitoring and account-level
  Foundry User; OpenAI-only access did not suffice for cloud judging.
- Two initial full evaluations errored during judging; these are not quality
  scores. The one-case RBAC verification subsequently produced a valid judgment.
  The full replacement scored 22/32 with zero errors/skips. Fresh optimisation:
  validation baseline 17/24, selected candidate 1 18/24, candidate 2 18/24.
  All 84 optimiser judgments completed without errors/skips. Both candidates
  embedded policy facts; their effective system prompts grew from 243 to 912 words.
  Six distinct development questions appeared in the training mini-batches.
  No candidate was applied or promoted; baseline version 1 remains live.
- Continuous evaluation is a setup walkthrough, not an enabled live service.
- An optional CLI investigation created an evaluation definition, but no model
  run. Details are in the playbook. The fresh-environment rehearsal is complete;
  no further evaluation, optimisation, deployment or promotion is authorised.

Cleanup archives, including the modified brief, prior tests and full raw evidence,
were saved outside the repository under:
`~/.copilot/session-state/4bd6dbe2-282c-419c-aa03-8bf15d01dfd9/files/repo-cleanup-2026-10-07/`.
They are local recovery material, not a dependency available in a fresh clone.

## Change and execution discipline

Explain the reason and obtain confirmation before substantive code, configuration
or cloud changes. Preserve unrelated user edits. Do not commit or push unless
asked. Keep source comments and documentation concise.

Do not run billable evaluations/searches, deploy, promote candidates, provision,
delete resources or change RBAC/networking without explicit approval. Existing
project/environment details are in the playbook. An authorised app-only
deployment uses `azd deploy purchasing-advice-demo`, not `azd up`.

Use Python 3.13 and the existing locked dependencies. CI performs Ruff lint and
format checks, not unit tests or model evaluation. From `sample/`:

```bash
.venv/bin/ruff check agent evaluation
.venv/bin/ruff format --check agent evaluation
uv run --frozen python evaluation/evaluate.py --dry-run
```

The dry run prints the request without writing files or making cloud calls. Check actual input
mapping, dataset separation and file paths when editing the evaluation helper.
Do not recreate a test framework as part of routine cleanup.

For this workstation's uv package operations, use
`UV_DEFAULT_INDEX=https://packagefeedproxy.microsoft.io/pypi/simple/`.
Do not casually upgrade agent dependencies or azd extensions during a demo task.
Never check in credentials, environment secrets or unreviewed raw telemetry.
