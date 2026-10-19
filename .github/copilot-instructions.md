# Repository context and working agreements

## Start here

Read `PLAYBOOK.md` before changing this repository. It is the single source for
the presentation flow, reusable setup and commands. Keep run history, scores,
cloud resource IDs and machine-specific handoffs outside the repository.
These instructions guide coding assistants; the hosted agent's instructions
are in `sample/agent/.agent_configs/baseline/instructions.md`.

This is a presentation and deliberately small demonstration, not a production
agent framework. The story is **agent -> evaluation -> traces -> continuous
evaluation -> optimisation**. Keep the audience focused on those concepts.
The user's priority is simplicity: avoid scaffolding, abstractions, helper
layers and documentation that obscure the sample.

## Layout

- `presentation/deck.html` is the source of truth; `presentation/presentation.pptx`
  is derived. All images in `presentation/assets/` are referenced by HTML.
- `sample/agent/`: the deployable Python agent, baseline configuration and
  fictional policy/notice documents.
- `sample/evaluation/`: `evaluate.py`, `compare_to_baseline.py`, `optimize.yaml`,
  two judge definitions, committed baselines and the development, holdout and
  drift JSONL datasets.
- `.github/workflows/`: PR gate (development set) and promotion (holdout, then
  drift, then release), sharing `_agent-eval.yml`.
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
- Three read-only tools over local JSON stand in for the IQ tools:
  `knowledge_base_retrieve` (Foundry IQ; hybrid keyword plus embedding search over
  policies), `ask` (Work IQ; roles, leave, delegations) and `search_ontology`
  (Fabric IQ; budget). **No real Foundry, Work or Fabric IQ is connected.**
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

- The binary `purchasing-next-action` judge is shared by evaluation and
  optimisation; `purchasing-demo-rubric` adds feedback dimensions. Do not
  silently change a rubric to improve a score.
- Only the question goes to the agent. The judge receives the question,
  `ground_truth` and final answer. The optimiser service receives references;
  its exact internal reflector inputs have not been established.
- `evaluate.py` registers the judges (`--register-only`), submits an evaluation
  (`EVAL_DATASET` selects the set; `--dry-run` prints the request) and writes the
  report that `compare_to_baseline.py` gates. Optimisation uses the static baseline,
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

## Demo conventions

- Use the Foundry project display name **Agent Evaluation Demo** and agent name
  `purchasing-advice-demo`. Get actual resource IDs from the selected azd environment.
- Agent and judge versions default to 1 for a fresh project. Check actual returned
  versions and align the script/YAML; do not infer live state from documentation.
- The agent uses GPT-5.4-mini with low reasoning; judge/generator use GPT-5.5.
- The corpus contains 22 policies and five notices; datasets contain 34 development,
  22 holdout and 8 drift cases. All questions supply an explicit decision date.
- Gates compare with baselines committed by a person; a pipeline never writes
  its own bar. Never give the drift set to the optimiser.
- The companion Bicep provides monitoring and account-level Foundry User access.
  Project-only or OpenAI-only access is insufficient for cloud judging.
- Continuous evaluation is a setup walkthrough. Do not enable it or promote a
  candidate as part of routine demo preparation.

## Change and execution discipline

Explain the reason and obtain confirmation before substantive code, configuration
or cloud changes. Preserve unrelated user edits. Do not commit or push unless
asked. Keep source comments and documentation concise.

Do not run billable evaluations/searches, deploy, promote candidates, provision,
delete resources or change RBAC/networking without explicit approval. Discover
project/environment details from local azd state. An authorised app-only
deployment uses `azd deploy purchasing-advice-demo`, not `azd up`.

Use Python 3.13 and the existing locked dependencies (`requirements*.txt`,
exported from `uv.lock`). Pull requests run offline checks, then a billable
development-set evaluation; pushes to main touching `sample/**` start the
billable promotion workflow. Offline checks, from `sample/`:

```bash
.venv/bin/ruff check agent evaluation
.venv/bin/ruff format --check agent evaluation
.venv/bin/python evaluation/evaluate.py --dry-run
```

The dry run prints the request without writing files or making cloud calls. Check actual input
mapping, dataset separation and file paths when editing the evaluation helper.
Do not recreate a test framework as part of routine cleanup.

Use the package index approved for the current environment.
Do not casually upgrade agent dependencies or azd extensions during a demo task.
Never check in credentials, environment secrets or unreviewed raw telemetry.
