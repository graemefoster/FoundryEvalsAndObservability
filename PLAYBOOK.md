# From prompt to production

**Agent -> evaluation -> traces -> continuous evaluation -> optimisation.**
Open `presentation/deck.html` or `presentation/presentation.pptx` for the deck.
This page covers the stage flow and how to run the sample, not individual run history.

## The demo

In Foundry, use project **Agent Evaluation Demo** and agent
**purchasing-advice-demo**. The project display name is separate from its Azure
resource name; commands obtain resource IDs and endpoints from your azd environment.

The agent uses Microsoft Agent Framework, GPT-5.4-mini with low reasoning, and
three read-only tools shaped like the Microsoft IQ MCP tools: `knowledge_base_retrieve`
(Foundry IQ, policies), `ask` (Work IQ, workplace notices) and `search_ontology`
(Fabric IQ, returns a fixed department budget).
It advises; it cannot approve, buy or contact anyone.
None connects to a real IQ source. The real ones are LLM-backed and have generic tool
descriptions, with domain guidance held in the knowledge base or ontology; ours are
deterministic local stand-ins.
Hosting and Agent Framework own the model/tool loop and tracing.

The question we evaluate is **"does the employee know their next action?"**
Ask for missing decision facts, identify outstanding requirements, or recognise
that the requirements are complete. Policy rules belong in retrieved documents.
Use the decision date in the question, not today's date.

| Location | Purpose |
| --- | --- |
| `sample/agent/` | Agent, baseline configuration, 19 policies and five notices |
| `sample/evaluation/` | Evaluation script, binary judge, optimiser configuration |
| `sample/evaluation/datasets/` | 32 development and 24 separate validation cases |
| `sample/azure.yaml` | Native Foundry deployment and model configuration |
| `sample/infra/monitoring.bicep` | Telemetry connection and evaluator model access |

## On stage (12-15 minutes)

Prepare the portal tabs and a completed evaluation/optimisation before the talk.
Do not wait for deployment or model runs on stage.

### 1. Ask the agent

Open a fresh conversation with the baseline agent:

> Decision date: 2026-10-20. An Orion field-service employee is flying business
> class from Australia to Japan. The itinerary says 11 hours including a
> connection, but doesn't break down flight segments. The $6,400 trip has two
> quotations, Category Manager spending approval and line-manager trip
> authorisation. Travel Desk will book. Can we rely on the regional pilot for
> the cabin?

Use single quotes when pasting into a shell, or `$6,400` becomes `,400` and the agent
invents a cost. From `sample/`:

```bash
azd ai agent invoke purchasing-advice-demo --version 2 --new-session --new-conversation \
  'Decision date: 2026-10-20. An Orion field-service employee is flying business class from Australia to Japan. The itinerary says 11 hours including a connection, but does not break down flight segments. The $6,400 trip has two quotations, Category Manager spending approval and line-manager trip authorisation. Travel Desk will book. Can we rely on the regional pilot for the cabin?'
```

The missing fact is the individual flight-segment duration, not total itinerary
time. Look for the answer to say "No, not yet", cite the single-segment 9-hour rule
and ask for the segment breakdown. The agent also checks the budget, so expect a
budget line. Show the instructions and the three IQ-shaped tools. Live wording varies.

### 2. Evaluate the next action

Open a completed development evaluation. Show a dataset question and its
`ground_truth`, the judge in `evaluation/purchasing-next-action.json`, and the
agent's answer.

Only the question reaches the agent. The judge sees the question, reference and
final answer. Discuss a failed case: an answer can quote the right policy yet
ask for a supplied fact, reopen a completed approval or offer unresolved routes.
Check execution errors separately from quality failures.

### 3. Inspect the trace

Open a rehearsed trace and expand a model call and policy search. Show the query,
returned documents and answer. Retrieving evidence and using it well are
different things; the tracing comes from hosting and Agent Framework.

### 4. Show continuous evaluation setup

In Foundry, open the recurring evaluation setup, select the agent and show live
traffic sampling and evaluator selection. Rehearse the portal navigation.
**Stop before enabling it.** This is a setup walkthrough, not a live service.
Live traffic has no golden references: use a compatible reference-free evaluator,
not this dataset-based judge.

### 5. Optimise, then inspect

Open a completed optimisation and compare baseline and candidates on the
**same 24 validation cases**, not against the 32-case development score.
Inspect fixed and regressed cases as well as the aggregate score.

Read each candidate's full effective instructions and tool descriptions. Look
for policy dates, limits or exceptions copied into configuration: a higher
answer score does not establish maintainability under changing policy.
The judge measures the next action, not whether the prompt contains facts.

Validation influences candidate selection; it is not untouched acceptance
testing. Inspect which development cases the training mini-batches actually used.
**Do not promote a candidate as part of the walkthrough.**

## Run the sample

Run all commands from `sample/`. For a new environment, complete **First-time
setup** below first. For an existing environment:

```bash
ENVIRONMENT="<your-azd-environment>"
azd env select "$ENVIRONMENT"
export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT -e "$ENVIRONMENT")"
azd ai agent show purchasing-advice-demo -e "$ENVIRONMENT"
```

The sample defaults to **agent version 1 and judge version 1**. Use the actual
deployed/registered versions in `evaluation/evaluate.py` and
`evaluation/optimize.yaml`; redeployment does not update those values for you.

For a fresh invocation, reset both the session and conversation:

```bash
# BILLABLE. Use the deployed agent version; single quotes keep $ amounts intact.
azd ai agent invoke purchasing-advice-demo \
  'Decision date: 2026-10-20. I need a mouse for an Orion employee in Singapore. What information do you need?' \
  --version 2 --new-session --new-conversation -e "$ENVIRONMENT"
```

Check that an answer arrives, not just exit code 0. In Foundry Tracing or the
connected Application Insights, inspect correlated `chat` and `execute_tool`
spans, including tool arguments/results. Allow time for ingestion.

For local development, run `.venv/bin/python agent/main.py` with the exported
endpoint and Azure credentials. `.env.example` is documentation, not loaded
automatically. For an authorised app-only update, use
`azd deploy purchasing-advice-demo -e "$ENVIRONMENT"`, not `azd up`.

### Evaluate and optimise

**Python submits evaluation; azd submits optimisation.** Both use the registered
`purchasing-next-action` judge with GPT-5.5. Editing the local rubric does not
update the stored judge: register a new version and align both configurations.

```bash
# Local preview: no credentials, cloud calls or generated files.
uv run --frozen python evaluation/evaluate.py --dry-run

# BILLABLE: 32 questions sent to the deployed agent, then judged.
uv run --frozen python evaluation/evaluate.py

# BILLABLE: one optimisation, capped at two candidates.
azd ai agent optimize --config evaluation/optimize.yaml \
  -e "$ENVIRONMENT" --no-wait --no-prompt

# Read-only progress for the returned job ID.
azd ai agent optimize status JOB_ID -e "$ENVIRONMENT"
```

Use the returned IDs to view answers and scores in Foundry. A `completed` run
can still contain errored or skipped rows; these are not quality judgments.
Keep run IDs, reports and deployment history outside the repository.

Keep the deployed baseline aligned with local source and leave inputs unchanged
during optimisation. The static YAML uses separate development and validation
datasets; its paths resolve from `sample/agent/`, not from the YAML directory.
No preparation script or copied input package is needed.

References go to the evaluation/optimisation service, not the agent. The exact
internal reflector inputs are not established. Inspect full resolved candidate
configuration, not only mutation records. The installed optimisation SDK applies
function descriptions but not parameter descriptions.

The CLI may rewrite baseline `metadata.yaml`. Preserve the run evidence, compare
the referenced tool bytes and restore only an unintended `tools_file` path.
Do not blindly reset local changes or apply the selected candidate.

## First-time setup

<details>
<summary>Provision a new environment, connect telemetry, register the judge and deploy</summary>

You need Python 3.13, `uv`, Azure CLI and azd (1.35.0 was used with the extension
versions below). Your Azure identity needs resource-creation and role-assignment
permissions. Check regional model/hosting availability and quota before provisioning.

`azure.yaml` requests GlobalStandard capacity 400 for GPT-5.4-mini and 100 for
GPT-5.5. Tool-assisted runs need adequate token capacity. These are quota
allocations, not spending caps; hosting, inference and telemetry incur charges.

```bash
az login
azd auth login
azd extension install azure.ai.agents --version 1.0.0-beta.13
azd extension install azure.ai.projects --version 1.0.0-beta.8
uv venv --python 3.13
uv pip install --require-hashes -r agent/requirements.txt -r requirements-dev.txt
```

Use your approved package index and the checked-in dependencies; no upgrade is
needed. Choose a unique environment name and explicitly select the subscription:

```bash
SUBSCRIPTION_ID="<your-subscription-id>"
ENVIRONMENT="agent-evaluation-demo-unique"
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

az rest --method patch \
  --url "https://management.azure.com${PROJECT_ID}?api-version=2025-06-01" \
  --body '{"properties":{"displayName":"Agent Evaluation Demo"}}' \
  --query properties.displayName -o tsv
```

The friendly display name does not change resource IDs or endpoints.
Deploy the companion Bicep for Log Analytics, Application Insights, the project
connection and account-level **Foundry User** access for the evaluator.
Project-only or OpenAI-only access is insufficient for cloud judging.

```bash
EVALUATOR_PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"
az deployment group create --name demo-monitoring \
  --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" \
  --template-file infra/monitoring.bicep \
  --parameters environmentName="$ENVIRONMENT" accountName="$ACCOUNT_NAME" \
    projectName="$PROJECT_NAME" evaluatorPrincipalId="$EVALUATOR_PRINCIPAL_ID" \
  --query properties.provisioningState -o tsv
```

For a service principal, supply its object ID and add
`evaluatorPrincipalType=ServicePrincipal`. Use the same identity for evaluation.
Allow RBAC propagation; `azd ai agent doctor` does not prove judge-model access.
Check that access with this tiny billable request before a full run:

```bash
az rest --method post --resource https://ai.azure.com \
  --url "https://${ACCOUNT_NAME}.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview" \
  --body '{"model":"gpt-5.5","messages":[{"role":"user","content":"Reply OK."}],"max_completion_tokens":32,"reasoning_effort":"low"}' \
  --query 'choices[0].message.content' -o tsv
```

If denied, resolve access before proceeding. Register the rubric once in the new
project, noting the returned version, then deploy the agent:

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

Align the returned versions in the evaluation script and optimiser YAML before
running them. Do not recreate resources or redeploy just to reset a stage demo.

</details>
