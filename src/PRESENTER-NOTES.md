# Presenter preparation and background

Use [DEMO-PLAYBOOK.md](DEMO-PLAYBOOK.md) during the talk. This is the backstage
reference, not another script to read to the audience.

## Completed native holdout experiment

Job `opt_5070777a25c74fe18d75964db4e7d514` succeeded on October 6, 2026.
The service actually evaluated the separate `validation_dataset`, not merely
accepted the field. All question/reference pairs and 66 actual GPT-5.5 judgments
were checked against the source datasets; there were no errors or skipped judgments.

| Configuration | Holdout passes | Prompt words |
| --- | ---: | ---: |
| Original baseline | 8/12 | 233 |
| Candidate 1, selected | 9/12 | 849 |
| Candidate 2 | 8/12 | 614 |

The ten recorded three-item training mini-batches contain development questions
only, collectively covering all 16 development cases. Two mini-batches repeat a
question within their three items. Each full baseline/candidate report contains
exactly the 12 holdout questions with their original references.

**Important distinction:** the reported candidate ranking uses holdout scores.
This is the optimiser's validation set, not an untouched final release benchmark.
We cannot establish the reflector's exact internal inputs from these reports.

Both candidates changed only the system prompt. The selected prompt still embeds
thresholds, notice facts and development examples. It fixes two baseline failures
but regresses one previously passing case, for a net gain of one. Its remaining
failures concern a premature security-review alternative, a spending route chosen
before the programme is known, and an extra documentation blocker on a ready case.
The last is the judge's interpretation of our strict next-action criterion.
No candidate was applied or deployed.

Raw review: `evidence/holdout-optimisation-review.json`. Native evaluation:
`eval_c3058ed596df48f2acd6558106530574`. Full report files:
baseline `evidence/evalrun_cde8abe35d404fa2b489a958ba562782.json`,
selected `evidence/evalrun_f24fb8e9d9af4a4594abd377124e316b.json`,
candidate 2 `evidence/evalrun_69075be27c1e4a8f962d30a8d25e0ad8.json`.

The recorded comparison later in these notes remains the earlier development-only
run. The old 16/16 candidate was not the starting point for this new search and
has not been scored on this holdout; do not describe the result as 16/16 becoming 9/12.

## Before the session

- Sign in to Foundry (new). Select `grfpublicfoundry / proj-default`, then
  `purchasing-advice-demo:1`. Do not switch to an older agent or apply a candidate.
- Open the tabs below. Set browser zoom and collapse sidebars before presenting.
- Rehearse the desk question in a fresh conversation. Confirm you can open its
  trace and see a model call plus tool input/output. Save a screenshot of that
  exact answer and trace as a fallback; this cleanup does not generate new traffic.
- Check the continuous-evaluation wizard is available for this hosted agent.
  Default to showing configuration without saving. Do not discover permissions
  or preview availability live on stage.
- Open the completed evaluation and optimisation results. Never wait for a
  new batch evaluation or search while presenting.

**Recorded readiness, October 6, 2026:** initial evaluation and optimisation have
completed; the original agent remains deployed. The project check found **zero
evaluation rules and zero schedules**. Continuous evaluation has no recorded
results. Current trace visibility and portal controls still require presenter
rehearsal. The new native validation results are recorded above; no candidate
deployment or separate final acceptance evaluation has been performed.

The source documents are fictional, not live Foundry IQ or Work IQ integrations.
The question's October 5 decision date is intentional, even if you present later.

## Tabs to open

| Tab | Open before the audience arrives |
| --- | --- |
| Agent | Foundry > Build > Agents > `purchasing-advice-demo`, version 1; fresh conversation |
| Initial evaluation | [Recorded initial baseline: 9/16](https://ai.azure.com/nextgen/r/2GWNiIh2Q0SncAVts-jFyA,publicfoundry,,grfpublicfoundry,proj-default/build/evaluations/eval_3288bcdbfeac4db082f0653f0794bcaf/run/evalrun_1d56633f39d84093af1d20d640b8fae2) |
| Trace | The matching agent interaction opened during rehearsal; do not substitute an older agent's trace |
| Continuous evaluation | Foundry > Build > Evaluations > Recurring Configs |
| Optimiser | Completed job `opt_eff605f084da4f63a2cd5598a53508f1`; locate during rehearsal, using the report links below if needed |
| IDE | Original `agent/.agent_configs/baseline/instructions.md`, `agent/datasets/next-action/golden-development.jsonl`, `evaluators/purchasing-next-action.json`, and `agent/datasets/next-action/golden-holdout.jsonl` |

The report links above/below are the service-returned URLs in the saved raw runs,
not guessed portal routes. Authentication, access and the portal layout must
still be checked. If a link no longer resolves, find the evaluation/run by ID.

## Continuous evaluation portal walkthrough

Follow Microsoft's [Agent Monitoring Dashboard guide](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard)
with the **Foundry portal** tab selected. These are documented navigation steps,
not a claim that this project's wizard has been visually rehearsed.

1. Open the project in Foundry (new). Go to **Build > Evaluations > Recurring
   Configs**, then **Create**.
2. Select only `purchasing-advice-demo` and the evaluation turn level.
3. Choose **Continuous evaluation**, then **Live traffic**. Contrast this with
   **Scheduled evaluation**, which runs at fixed times.
4. Choose a supported evaluator that does not require a reference answer.
   For this demo, look for a reference-free quality evaluator such as coherence;
   inspect the available evaluator's required inputs before selecting it.
   Do **not** attach `purchasing-next-action` unchanged: it requires `ground_truth`,
   which ordinary live interactions do not supply.
5. Show the sampling options and maximum trace/run limit offered for this type.
   Prefer a small deliberate budget for rehearsal. Select the judge deployment
   if requested and review the scope and settings.
6. **Default demo ends here: cancel without saving.** Say: "This is where we would
   enable ongoing assessment. We haven't enabled it in this project."

**If the presenter chooses to enable it:** first confirm the permissions and
model-call budget, then complete the wizard and check the resulting configuration
is enabled. Generate a small amount of fresh traffic, allow ingestion/evaluation
time, and inspect **Recurring Configs** and the agent's **Monitor** tab. Show actual
completed evaluations, not just an enabled switch. Do this before the talk.
Afterwards, disable only the configuration created for the rehearsal and confirm
it is disabled; don't leave ongoing judge calls running by accident.

**Prerequisites:** connected Application Insights and access to it/its Log
Analytics workspace, supported evaluator inputs, and permission to create
evaluation configurations. Microsoft's guide also requires the project's managed
identity to have **Foundry User** (previously **Azure AI User**) for continuous
evaluation rules. Check the [evaluation permissions guide](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluation-permissions)
and ask the resource owner to resolve missing access before rehearsal.
This repo cleanup does not grant roles or change telemetry configuration.

**Empty chart does not mean a broken agent.** Check enabled status, time range,
new traffic, ingestion delay and the run limit. If the wizard is unavailable,
use the official guide's screenshots and explicitly call it a configuration
walkthrough. Do not fall back to classic-agent instructions or write a new SDK
integration during the talk.

**Keep the distinction clear:** live-traffic quality signals are not the same
metric as our reference-based business next-action test. Neither a scheduled
benchmark nor the repository's offline CI is automatically live-traffic evaluation.

## Recorded optimiser comparison

These three reports belong to one completed native search:

| Configuration | Report | Passes | Missing-fact passes | Prompt words |
| --- | --- | ---: | ---: | ---: |
| Fresh baseline | [Open report](https://ai.azure.com/nextgen/r/2GWNiIh2Q0SncAVts-jFyA,publicfoundry,,grfpublicfoundry,proj-default/build/evaluations/eval_3e7ed85e2a214631ae40eb879e8deee2/run/evalrun_033f67798a5b4e4cb5dfef70b997dbfa) | 10/16 | 1/4 | 233 |
| Candidate 1 | [Open report](https://ai.azure.com/nextgen/r/2GWNiIh2Q0SncAVts-jFyA,publicfoundry,,grfpublicfoundry,proj-default/build/evaluations/eval_3e7ed85e2a214631ae40eb879e8deee2/run/evalrun_baca4266ed074119818e9e02b17f2606) | 15/16 | 3/4 | 992 |
| Selected candidate 2 | [Open report](https://ai.azure.com/nextgen/r/2GWNiIh2Q0SncAVts-jFyA,publicfoundry,,grfpublicfoundry,proj-default/build/evaluations/eval_3e7ed85e2a214631ae40eb879e8deee2/run/evalrun_ecf22b29931a487a9e569fb89d04fb8e) | 16/16 | 4/4 | 1,551 |

The earlier standalone baseline scored **9/16**. The optimiser generated fresh
answers and scored **10/16**; these are different runs, not conflicting reports.

Both candidates changed only the system prompt. The selected prompt embeds
thresholds, notice facts and development examples. Its native average-token metric
rose from **3,576.625 to 6,529.8125**: do not call this a cost reduction.

**Saved files:** `evidence/opt_eff605f084da4f63a2cd5598a53508f1.json` contains
`result.candidates[].mutations.system_prompt`. Open the selected prompt before
presenting rather than navigating a large JSON file live.
Each report above is also saved as `evidence/<run-id>.json`.
`evidence/next-action-optimisation-review.json` records the comparison and caveats.
These files are local/ignored; copy the required evidence deliberately when
handing the demo to another presenter.

### Desk answer fallback

Same question as the run sheet. These are **recorded answers from the optimiser's
baseline and selected candidate**, not output from the current live conversation.
The candidate is not deployed. Use these excerpts if portal results are unavailable.

**Baseline, verbatim excerpt:**

> What to do next:
> 1. **Get the total price** for the desks from DeskCo.
> 2. If it’s **$5,000 or less**, obtain **one quote** and route for **Line Manager approval**.
> 3. If it’s **over $5,000**, obtain **two quotes** and route for **Category Manager approval**.
> 4. **Do not place the order or commit spend** until the required approval is in place [policy:purchasing].

**Selected candidate, full recorded answer:**

> I don’t have enough facts yet to identify the purchasing route.
>
> What I need next:
> - **The total proposed commitment amount** for the DeskCo desk order.
>
> Why this matters:
> - The total amount determines the required **quotation count** and **spending approver**.
>
> You should **not order or commit spend yet**.

The baseline lists real policy routes, not invented facts. The failure is our
chosen interaction requirement: resolve the missing amount before enumerating
unresolved alternatives. Don't force a live response to match this recording.

## The golden-data conversation

| Asset | Role | Current evidence |
| --- | --- | --- |
| `golden-development.jsonl`: 16 cases | Initial evaluation and training mini-batches | Earlier development-only run: selected candidate passed 16 |
| `golden-holdout.jsonl`: 12 cases | Native validation and candidate comparison, not training mini-batches | New run: baseline 8/12; selected candidate 9/12 |

The development set covers four groups equally: missing facts, remaining
requirements, exceptions and ready to proceed. The holdout set has three cases
per group. It is separate, not larger. The earlier recorded search omitted it;
the new experiment supplied it as `validation_dataset`, with its full evaluations
confirmed against that file. Recorded training mini-batches contain no holdout cases.

**Say:** "Golden refers to the reference-answer cases; holdout describes how we
reserve some of those cases for independent acceptance. Golden development data
can guide the search. Golden holdout data stays out of training and is supplied
through the optimiser's separate validation input."
Our fictional references still need domain-owner review before any production use.
If holdout failures guide the next prompt, that set is becoming development data.

**Does more data prevent fact-stuffing?** No guarantee. An embedded threshold may
work on many unseen questions while policy stays unchanged. Inspect the prompt
and test changed evidence as well as new situations. An isolated $3,000-threshold
experiment was prepared but never evaluated; its helper/data are archived under
`evidence/archive-before-focused-demo/`, not part of the live demo.

**Does this judge see the system prompt?** No. Its template reads `query`,
`ground_truth` and the final `response`. It cannot directly penalise facts embedded
in a candidate prompt. The optimiser has configuration and evaluation evidence;
its exact internal reflector payload is not established here.

**Can we forbid embedded facts in optimiser instructions?** We did not verify a
dedicated reflector-guidance setting in the interface used for this run. The
agent's starting system prompt is not a verified enforced rewrite constraint.

**Is the selected candidate perfect?** No. A passed answer says "before" a clearance
expiry that the notice includes, and the generated prompt contains a nonexistent
`[policy:training]` citation example. Inspected answers used the real
`policy:training-suitability` ID. Scores don't replace review.

## Optional new runs (backstage only)

Nothing here is required to show the recorded demo. Model runs are billable;
preparation registers a judge but does not start optimisation.
Run from `src/` with the existing environment and credentials:

```bash
export FOUNDRY_PROJECT_ENDPOINT='https://grfpublicfoundry.services.ai.azure.com/api/projects/proj-default'

# Preview the requests locally, then deliberately submit a fresh baseline.
uv run --frozen python evaluate.py --dry-run
uv run --frozen python evaluate.py

# Read the submitted run using its printed IDs.
uv run --frozen python evaluate.py --show EVAL_ID RUN_ID

# Freeze separate training/validation inputs and pin the judge; prints the search command.
uv run --frozen python evaluate.py --prepare-optimizer
```

Use the printed, uniquely prepared configuration for a deliberately approved
search, not the raw YAML template. Verify its generated evaluation uses the
single next-action judge and GPT-5.5, including the global evaluation model.
Optimiser terminal success is `succeeded`; evaluation-run completion is `completed`.
An optimisation may perform internal work beyond the published candidate reports.

The CLI previously rewrote local baseline `metadata.yaml` to point into frozen
evidence. After any new search, inspect it: the original baseline's `tools_file`
should remain `tools.json`. Preserve the run inputs and compare tool contents
before correcting an unexpected path; don't blindly reset candidate changes.

`--release --agent-version VERSION` evaluates `golden-holdout.jsonl` against a
deliberately deployed version; it is not a hidden candidate-application command.
Do not apply/deploy a candidate just to show a saved answer.
The local GitHub workflow checks code offline; no automated cloud release gate
is implemented.
