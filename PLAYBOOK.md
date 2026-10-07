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
| `sample/infra/monitoring.bicep` | New-project telemetry and evaluator model access |
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

The fresh-project baseline is `purchasing-advice-demo:1`, GPT-5.4-mini with low
reasoning. The judge and optimiser generator use GPT-5.5. There are 19 policies,
five notices, 32 development cases and 24 separate validation cases. All 56
questions supply their own decision date.
Neither search tool is real Foundry IQ or Work IQ.

The source uses that supplied date and asks when a needed date is missing; it
no longer injects a fallback date. It was deployed to a new project on
October 7, 2026. The stage walkthrough and version-3 scores below remain the
historical October 6 experiment in the old project, whose source supplied an
October 5 fallback overridden by each question's explicit date. Agent and
judge version numbers are project-local; do not mix the two projects' results.

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

### Fresh-environment rehearsal: October 7, 2026

This is a separate deployment of the current source, not a rerun of version 3.
It started from a clean checkout without `.azure` state or a virtual environment.

| Item | Value |
| --- | --- |
| Environment / project | `ai-genius-fresh-20261007` |
| Subscription | `d8658d88-8876-4344-a770-056db3e8c5c8` |
| Region / resource group | `australiaeast` / `rg-ai-genius-fresh-20261007` |
| Foundry account | `cog-rt2g7wn5rar2g` |
| Agent / judge | `purchasing-advice-demo:1` / `purchasing-next-action:1` |
| Application Insights | `appi-ai-genius-fresh-20261007` |
| Correlated model/tool trace | `771cb0447dadebd9177960dbbc333a4d` |
| Development evaluation | `eval_3687d5b6698e4a33a0c5611778cef8d0` |
| Development run, 22/32 | `evalrun_40d69611834d4067ab6e44a3711ed798` |
| Optimisation job | `opt_e46d90742edf45eeae626d51575a00c0` |
| Optimiser evaluation | `eval_51287789cd8d401e868b2741cfd4ebe1` |
| Validation baseline, 17/24 | `evalrun_263397c9f99c49db963460b4ad558cf4` |
| Selected candidate 1, 18/24 | `evalrun_30a08567beca468c894b11d97a22446e` |
| Candidate 2, 18/24 | `evalrun_908d4c0de879496798ed034fea6c1773` |

The agent answered using its tools, and persisted native traces contain model
calls plus both search tools' arguments and results. Monitoring and evaluator
access are now reproducible through `sample/infra/monitoring.bicep`.

Two initial 32-case runs generated answers but errored during judging. They are
**not 0/32 quality scores**. Project-only access was insufficient; adding
OpenAI-only access was also insufficient. After assigning account-level Foundry
User, a one-case cloud evaluation produced a valid judgment with no execution
errors. The full replacement scored **22/32**, with **zero errors or skips**.
The two-candidate optimisation completed successfully:

| Configuration | Validation passes | System words | Stored tool/parameter-description words |
| --- | ---: | ---: | ---: |
| Baseline | 17/24 | 243 | 102 |
| Candidate 1, selected | 18/24 | 912 | 102 |
| Candidate 2 | 18/24 | 912 | 597 |

Both candidates improved one baseline failure without regressing a baseline
pass, but fixed different cases. The selected candidate fixed
`exception_release_accessibility_region`; candidate 2 fixed
`clarify_release_funding_support_split`. This is not a 22/32-to-18/24 comparison:
development and validation are different datasets.

**Fact stuffing remains.** Both candidates share the same expanded system
instructions, including dated PrintForge hold rules, specific consulting
deletion dates and the Orion travel-clearance window. Candidate 2 also embeds
policy detail in tool/parameter descriptions. Counts above come from the full
resolved configurations referenced by the evaluated drafts, not mutation
records alone. Stored parameter descriptions should not be assumed to reach
the runtime: the installed optimisation SDK applies function descriptions,
but not parameter descriptions.

All seven optimiser reports contained 84 judgments with no errors or skips.
The four training mini-batches used six distinct development questions; every
full comparison used all 24 exact validation question/reference pairs.
Validation influenced selection; changed-policy robustness remains untested.
No candidate was applied or promoted: version 1 remains live. The CLI left the
local baseline unchanged in this run.

The new environment is selected in this workstation's original checkout; old
environments were retained. Resources remain running and can incur charges.

## Backstage: run the sample

### Start in a new subscription environment

Run the following Bash commands from `sample/`. You need Python 3.13, `uv`,
Azure CLI and `azd`; the rehearsal used azd 1.35.0 and the extension versions
below. Your Azure identity needs resource-creation and role-assignment
permissions in the chosen subscription. Model availability, hosted-agent
availability and quota must cover the chosen region.

`azure.yaml` requests GlobalStandard capacity 400 for GPT-5.4-mini and 100 for
GPT-5.5. In the rehearsal, capacity 10 for the agent repeatedly throttled
tool-assisted requests; 400 supplied 400,000 TPM / 400 RPM. These are quota
allocations, not a spending cap. Hosting, inference and telemetry can incur
charges; do not delete somebody else's deployments to make room.

```bash
az login
azd auth login
azd extension install azure.ai.agents --version 1.0.0-beta.13
azd extension install azure.ai.projects --version 1.0.0-beta.8
uv venv --python 3.13
uv pip install --require-hashes -r agent/requirements.txt -r requirements-dev.txt
.venv/bin/ruff check agent evaluation
.venv/bin/ruff format --check agent evaluation
```

Keep the checked-in manifests and lock file; no dependency upgrade is needed.
For this workstation's package mirror, set
`UV_DEFAULT_INDEX=https://packagefeedproxy.microsoft.io/pypi/simple/` if needed.
Other environments can use their approved package index.

Choose a unique environment name (short lowercase letters, digits and hyphens)
and explicitly select the subscription; Azure CLI and azd defaults can differ.
The native Foundry provider creates the account, project and model deployments.

```bash
SUBSCRIPTION_ID="<your-subscription-id>"
ENVIRONMENT="ai-genius-your-unique-name"
LOCATION="australiaeast"
az account set --subscription "$SUBSCRIPTION_ID"
azd env new "$ENVIRONMENT" --subscription "$SUBSCRIPTION_ID" --location "$LOCATION"
azd provision -e "$ENVIRONMENT" --preview --no-prompt
azd provision -e "$ENVIRONMENT" --no-prompt

RESOURCE_GROUP="$(azd env get-value AZURE_RESOURCE_GROUP -e "$ENVIRONMENT")"
PROJECT_ID="$(azd env get-value AZURE_AI_PROJECT_ID -e "$ENVIRONMENT")"
ACCOUNT_ID="${PROJECT_ID%/projects/*}"
ACCOUNT_NAME="${ACCOUNT_ID##*/}"
PROJECT_NAME="${PROJECT_ID##*/}"
export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT -e "$ENVIRONMENT")"
```

### Connect monitoring and grant judge access

Native provisioning did not create the monitoring connection in our rehearsal.
This companion Bicep creates Log Analytics, Application Insights and the project
connection. It also grants the signed-in evaluator **Foundry User** (formerly
Azure AI User) on this account. Project access and subscription Owner alone
did not allow judge inference. **Cognitive Services OpenAI User is insufficient:**
it permits direct OpenAI inference but not the Foundry `/models` route.

```bash
EVALUATOR_PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"
az deployment group create --name demo-monitoring \
  --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" \
  --template-file infra/monitoring.bicep \
  --parameters environmentName="$ENVIRONMENT" accountName="$ACCOUNT_NAME" \
    projectName="$PROJECT_NAME" evaluatorPrincipalId="$EVALUATOR_PRINCIPAL_ID" \
  --query properties.provisioningState -o tsv
```

For service-principal authentication, supply that principal's object ID instead
and add `evaluatorPrincipalType=ServicePrincipal`. Use the same identity for
Python evaluation; avoid an unrelated credential selected from your shell.
The template does not print connection strings. Allow time for RBAC propagation;
a passing `azd ai agent doctor` does not prove judge-model access.
Before spending on a full evaluation, this tiny billable request checks the
Foundry model route with the intended signed-in identity. Expect an answer,
not a 401/403. If denied, resolve access or allow propagation before proceeding.

```bash
az rest --method post --resource https://ai.azure.com \
  --url "https://${ACCOUNT_NAME}.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview" \
  --body '{"model":"gpt-5.5","messages":[{"role":"user","content":"Reply OK."}],"max_completion_tokens":32,"reasoning_effort":"low"}' \
  --query 'choices[0].message.content' -o tsv
```

### Register the judge and deploy the agent

Register the checked-in rubric once in this new project. This stores the judge's
definition, not an evaluation run. Record the returned version; registering again
can create another version.

```bash
.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

rubric = json.loads(Path("evaluation/purchasing-next-action.json").read_text())
name = rubric.pop("name")
with DefaultAzureCredential() as credential, AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
) as project:
    judge = project.beta.evaluators.create_version(name, evaluator_version=rubric)
    print(f"Judge: {name}:{judge.version}")
PY

azd deploy purchasing-advice-demo -e "$ENVIRONMENT" --no-prompt
azd ai agent show purchasing-advice-demo -e "$ENVIRONMENT"
azd ai agent doctor -e "$ENVIRONMENT"
```

Use the actual returned agent and judge versions in `evaluation/evaluate.py`
and `evaluation/optimize.yaml`. Both default to 1 for a new project. Redeploying
creates new agent versions; it does not update these constants automatically.

Invoke a fresh session **and conversation** so previous questions do not leak
into the demo:

```bash
azd ai agent invoke purchasing-advice-demo \
  "Decision date: 2026-10-20. I need a mouse for an Orion employee in Singapore. What information do you need?" \
  --version 1 --new-session --new-conversation -e "$ENVIRONMENT"
```

Check that an answer actually arrives, not just exit code 0. In Foundry Tracing
or the connected Application Insights, find that request's operation ID and
expand `chat` and `execute_tool` spans. Allow a few minutes for ingestion.
Hosting and Agent Framework supply model messages, tool arguments/results and
correlation; no custom spans or instrumentation package is required.

`sample/.env.example` is documentation, not automatically loaded configuration.
For a local server, retain the exported project endpoint and run
`.venv/bin/python agent/main.py`.
For later app-only updates, use `azd deploy purchasing-advice-demo`, not
`azd up`. Provisioning or candidate promotion is not a demo reset.

## Backstage: evaluate and optimise

**Evaluation stays in Python; optimisation runs through `azd`.** The Python
script submits the 32 development questions using the already registered judge.
Foundry invokes the hosted agent and scores it.

Run these commands from `sample/`. Agent version 1, judge version 1, judge model
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
A run marked `completed` can still contain execution errors. Check passed,
failed, errored and skipped counts; only passed/failed rows are quality judgments.

`evaluation/optimize.yaml` directly references the local baseline, 32 development
cases, 24 validation cases and registered judge version 1. No preparation or input
copying is needed. Keep these inputs unchanged during a run.
The installed CLI resolves dataset paths from the agent service's
`project: ./agent`, not the YAML directory; the `../evaluation/datasets/...`
paths are intentional.
Before another authorised optimisation, align the deployed agent version with
the local baseline and update `agent.version` in the YAML.
Judge version 1 in the fresh project was checked against the local rubric on
October 7, 2026 (the old project used version 8).
If the rubric changes, register the revised judge and update its version in both
the script and YAML. Editing the local JSON alone does not change the stored
judge. A different Foundry project needs its own registered judge version.

```bash
# BILLABLE: one search, capped at two candidates.
azd ai agent optimize --config evaluation/optimize.yaml \
  -e "$ENVIRONMENT" --no-wait --no-prompt

# Read-only status; never starts another search.
azd ai agent optimize status JOB_ID -e "$ENVIRONMENT"
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
