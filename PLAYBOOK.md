# From prompt to production

**Deck + sample agent + one playbook.** Open `presentation/deck.html` for the
browser deck, or `presentation/presentation.pptx` for PowerPoint.
`presentation/assets/` supplies the browser deck's backgrounds.

| Location | Purpose |
| --- | --- |
| `presentation/` | Both deck formats and required images |
| `sample/agent/` | Only the code, configuration and policy data that get hosted |
| `sample/evaluation/` | Python evaluation helper, judge, golden datasets and optimiser YAML |
| `sample/azure.yaml` | Deployment configuration for the sample |
| `PLAYBOOK.md` | Stage flow, recorded results and backstage commands |

## The demo in one minute

A lean Python Agent Framework agent searches fictional purchasing policies
and workplace notices. Foundry hosting and Agent Framework own the protocol,
model/tool loop and tracing; there are no custom spans or orchestration.
The agent advises. It cannot approve, buy or contact anyone.

The question is not just "is this policy information correct?" It is
**"does the employee know their next action?"** Ask for missing decision facts,
identify outstanding requirements, or recognise that the stated requirements
are complete. Do not make the employee select between unresolved routes.

The active baseline is `purchasing-advice-demo:3`, GPT-5.4-mini with low
reasoning. The judge and optimiser generator use GPT-5.5. There are 19 policies,
five notices, 32 development cases and 24 separate validation cases. All 56
questions supply their own decision date.
Neither search tool is real Foundry IQ or Work IQ.

The local source now uses that supplied date and asks when a needed date is
missing; it no longer injects a fallback date. This simplification has not been
deployed or scored. Recorded version-3 results below belong to the earlier
deployed source, which supplied an October 5, 2026 fallback overridden by each
question's explicit date. Deploy deliberately before evaluating the new source
or preparing optimisation inputs for it.

## Five beats on stage (12-15 minutes)

Prepare portal tabs and recorded results before the talk. Do not wait for a
deployment, evaluation or optimisation on stage.

### 1. Ask the agent (2 minutes)

Open Foundry project `grfpublicfoundry / proj-default`, agent
`purchasing-advice-demo:3`, in a fresh conversation. Ask:

> Decision date: 2026-10-20. An Orion field-service employee is flying business
> class from Australia to Japan. The itinerary says 11 hours including a
> connection, but doesn't break down flight segments. The $6,400 trip has two
> quotations, Category Manager spending approval and line-manager trip
> authorisation. Travel Desk will book. Can we rely on the regional pilot for
> the cabin?

Show the answer, original instructions and two tools, not a Python walkthrough.
The missing decision fact is the individual flight-segment duration, not total
itinerary time. Live wording varies; this case passed in the recorded baseline.

**Say:** "Retrieving the policy is only the start. We want the next best action,
not a menu of decisions left for the employee."

### 2. Evaluate the behaviour (3 minutes)

Open the recorded version-3 development evaluation: **16/32 passes**.
Show a question and `ground_truth` in
`sample/evaluation/datasets/golden-development.jsonl`, beside
`sample/evaluation/purchasing-next-action.json`.

**Say:** "Only the question reaches the agent. The judge sees the question,
golden reference and actual answer. One binary rubric scores the immediate next
action. It does not score whether the system prompt contains policy facts."

For a failure, use `clarify_event_allocation`: the answer requested itemisation
but also raised the conditional excess-funding route before the allocation was
known. The rubric rejects that unresolved branching. Other baseline failures
include repeated completed approvals and omissions of mandatory requirements;
do not claim every answer was factually correct.

### 3. Inspect the trace (2 minutes)

Open a matching, rehearsed trace. Expand one model call and policy search.
Show the query, returned source and answer.

**Say:** "The evidence was available. Retrieving it and using it well are
different things. This tracing comes from hosting and Agent Framework."

### 4. Show continuous evaluation setup (2 minutes)

In Foundry, open **Build > Evaluations > Recurring Configs > Create**,
select the agent, **Continuous evaluation** and **Live traffic**. Show evaluator
selection and sampling limits. Portal labels may change; rehearse the navigation.

**Stop before enabling it.** Continuous evaluation is not configured for this
demo. Live traffic has no golden references, so use a compatible reference-free
evaluator, not this dataset-based judge. Scheduled benchmark runs are separate.

### 5. Optimise, then inspect the improvement (4 minutes)

Open the completed final optimiser run and compare on its **same 24 validation
cases**, not the separate 32-case development baseline:

| Configuration | Validation passes | System words | Tool/parameter-description words |
| --- | ---: | ---: | ---: |
| Baseline | 16/24 | 233 | 102 |
| Candidate 1 | 16/24 | 1,099 | 102 |
| Candidate 2, selected | 17/24 | 1,099 | 463 |

The selected candidate fixed two cases and regressed one. Clarification stayed
at **1/6**. It retained candidate 1's fact-filled prompt and expanded tool
descriptions. Show embedded PrintForge hold dates, retention periods and travel
pilot rules. No candidate was promoted.

**Say:** "There is a modest measured gain, but policy knowledge has been copied
into configuration. Our judge scores the answer, not where that knowledge lives."

The supplied cases cover all 19 policies, including scoped holds, regional
eligibility, cost allocation, deadlines and amendments. However, the recorded
training mini-batches exercised only **six distinct development questions**.
All 24 validation questions were used in each full comparison. Validation helps
select candidates; it is not untouched final acceptance testing. This finite,
fixed corpus does not establish whether a candidate follows changed policy.

**Close:** "Optimisation is an experiment, not a production guarantee. Inspect
the effective configuration as well as the score."

## Recorded results and portal tabs

In the project portal, open **Evaluations** or the agent's **Optimisation** tab
and use these IDs. They refer to completed runs from October 6, 2026:

| Item | ID |
| --- | --- |
| Development evaluation | `eval_9b0e48435c864bf6b1b33d54e91c3920` |
| Development run, 16/32 | `evalrun_861c3122b8f04fc58126bae11441897f` |
| Final optimiser | `opt_de776d8b3fea47b386f6ed68f193fe6c` |
| Optimiser evaluation | `eval_3a18d5c82d3244ffb18f352501ca24c1` |
| Validation baseline, 16/24 | `evalrun_07d97f9e610d4046a88996c99a905cad` |
| Candidate 1, 16/24 | `evalrun_47b1be66c8a84ef9ac8cb25f1a165dbc` |
| Selected candidate 2, 17/24 | `evalrun_834d839328a5493ab753bb8f1e5507d9` |

The final seven optimiser reports contained 84 completed judgments and no
errors/skips. All full-report query/reference pairs were checked against frozen
inputs; 600 retrieved source records matched the packaged corpus. Actual draft
configurations were resolved to establish prompt inheritance.

For historical context only: the earlier 13-policy version-2 experiment used
46/24 cases, scoring 32/46 development and 16/24 -> 20/24 validation. Its selected
candidate also embedded facts. Do not mix those scores with the current cases.
Detailed history and raw evidence have been archived outside this repository.

## Backstage: run the sample

From `sample/`, use Python 3.13, `uv`, Azure sign-in and the existing `azd`
environment. Keep `agent/requirements.txt`, `requirements-dev.txt` and `uv.lock`
for reproducibility. Install and check locally:

```bash
uv venv
uv pip install --require-hashes -r agent/requirements.txt -r requirements-dev.txt
.venv/bin/ruff check agent evaluation
.venv/bin/ruff format --check agent evaluation
```

For this workstation's package mirror, set
`UV_DEFAULT_INDEX=https://packagefeedproxy.microsoft.io/pypi/simple/` if needed.
Other environments can use their approved package index.

The existing environment is `ai-genius-hosted`. Obtain the project endpoint
without copying credentials into files:

```bash
export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT -e ai-genius-hosted)"
```

`sample/.env.example` is documentation, not automatically loaded configuration.
For a local agent server, export the endpoint, authenticate with `az login`,
then run `.venv/bin/python agent/main.py`.

Deploy only when intentionally changing the agent:

```bash
azd deploy purchasing-advice-demo -e ai-genius-hosted --no-prompt
azd ai agent show purchasing-advice-demo -e ai-genius-hosted
```

Use the actual returned version in later evaluation commands. Do not run
`azd up`, provision/delete shared resources, or apply a candidate as a demo reset.

## Backstage: evaluate and optimise

**Evaluation stays in Python; optimisation runs through `azd`.** The Python
script submits the 32 development questions using the already registered judge.
Foundry invokes the hosted agent and scores it.

Run these commands from `sample/`. Agent version 3, judge version 8, judge model
and dataset path are constants at the top of `evaluation/evaluate.py`.
Change the agent version only when its deployed corpus matches the dataset.

```bash
# Local request preview: no credentials or model calls.
uv run --frozen python evaluation/evaluate.py --dry-run

# BILLABLE: a new 32-case development evaluation. Not needed to view old results.
uv run --frozen python evaluation/evaluate.py
```

The script prints the evaluation/run IDs and report link. View progress, answers
and scores in Foundry Evaluations; use the recorded IDs above for the stage demo.
`--dry-run` prints the request without credentials, cloud calls or local files.

`evaluation/optimize.yaml` directly references the local baseline, 32 development
cases, 24 validation cases and registered judge version 8. No preparation or input
copying is needed. Keep these inputs unchanged during a run.
Before another authorised optimisation, align the deployed agent version with
the local baseline and update `agent.version` in the YAML.
Judge version 8 was checked against the local rubric on October 7, 2026.
If the rubric changes, register the revised judge and update its version in both
the script and YAML. Editing the local JSON alone does not change the stored
judge. A different Foundry project needs its own registered judge version.

```bash
# BILLABLE: one search, capped at two candidates.
azd ai agent optimize --config evaluation/optimize.yaml \
  -e ai-genius-hosted --no-wait --no-prompt

# Read-only status; never starts another search.
azd ai agent optimize status JOB_ID -e ai-genius-hosted
```

The optimiser uses the separate 24-case validation dataset. Development and
validation share the same judge. References are sent to the
evaluation/optimisation service, not to the agent under evaluation. Exact internal
optimiser reflector inputs are not established.

The CLI may rewrite baseline `metadata.yaml` when submitting optimisation.
Inspect the diff afterwards: preserve the run's configuration, verify the
referenced tools match, and restore only `tools_file: tools.json` if necessary.
Do not blindly reset changes or promote the selected candidate.

The script does not copy inputs, hash source files or download results.
The recorded portal runs remain the demo reference; a fresh checkout does not
contain archived local evidence.
CI checks Python lint and formatting, not model quality or continuous
evaluation. The previous unit tests are archived outside the demo repository.

### CLI evaluation is an alternative, not this demo's dependency

The Microsoft Learn evaluation walkthrough uses `azd ai agent eval`.
A separate `azure.ai.evaluations` extension exposes `azd ai eval`, which can
also target a hosted agent. Their configuration formats are different.
On October 7, the separate extension successfully created an evaluation
definition with this judge's exact question/reference/final-answer mappings,
version 8 and threshold 1. No model run was started, so end-to-end parity was
not verified. We retain the proven Python workflow by choice; do not present
either CLI route as incapable of golden-data evaluation.

The temporary definition `eval_0554662f8078486a9f4183d088c2d3c8` remains in
Foundry with no run started by this investigation. Its local experimental
configuration was removed. The optional extension remains installed on the
workstation but is not required by this sample.
