# From prompt to production

**Agent -> traces -> evaluation -> continuous evaluation -> optimisation.**
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
Evaluations and optimisations can take tens of minutes or longer. Pre-run both
well before the session and confirm they have finished; show their saved results
on stage rather than waiting for live runs. Do not wait for deployment on stage.

### 1. Ask the agent

Invoke the deployed agent from `sample/`. Remote invocation is the default;
omit `--version` to use the default deployed version and start a fresh session.
Use single quotes so the shell preserves `$540`:

```bash
azd ai agent invoke purchasing-advice-demo --new-session --new-conversation \
  'Decision date: 2026-10-20. We want to book a business dinner for six people in total: three employees and three supplier representatives. None are public officials. The complete bill is $540, including tax and service. We have a quotation and line-manager spending approval. Can we book?'
```

The missing fact is whether alcohol is included. A good answer asks that question
before describing alternative approval routes. The baseline may instead give
"if alcohol, then ... otherwise ..." advice: that is the clarification failure
to discuss, not merely verbosity. Show the policy lookup and budget check in
the trace, then the instructions and three IQ-shaped tools. Live wording varies.
Evaluation and optimisation omit agent and evaluator versions to use the latest.
Keep the deployed agent and registered evaluators unchanged during a comparison.

### 2. Inspect the trace

Open a rehearsed trace and expand a model call and policy search. Show the query,
returned documents and answer. Retrieving evidence and using it well are
different things; the tracing comes from hosting and Agent Framework.

### 3. Evaluate the next action

Open a completed development evaluation. Show a dataset question and its
`ground_truth`, the agent's answer and both evaluator definitions in `evaluation/`:
`purchasing-next-action.json` (custom prompt) and `purchasing-demo-rubric.json`
(native `type: rubric`).

Only the question reaches the agent. The binary judge sees the question, reference
and final answer. The native rubric sees the question and final answer, producing
weighted dimension scores and reasons. Discuss a failed case: an answer can quote the right policy yet
ask for a supplied fact, reopen a completed approval or offer unresolved routes.
Check execution errors separately from quality failures. Neither text-only
evaluator proves that the agent retrieved its evidence.

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

**Baseline means the original agent configuration, not the development dataset.**
Development examples help explore changes; the original agent and offered
candidates are compared on the same validation questions.

**Offered candidates are not the whole search history.** Open the optimisation's
evaluation and look for `minibatch_*` runs. Compare their questions, draft agent
versions and scores: small development batches can reveal before/after trials,
including drafts not offered as candidates. A later draft may refine an earlier
candidate. Improving a mini-batch does not guarantee better validation results;
do not compare scores from different batches as if they used the same questions.

Read each candidate's full effective instructions and tool descriptions. Look
for policy dates, limits or exceptions copied into configuration: a higher
answer score does not establish maintainability under changing policy.
The judge measures the next action, not whether the prompt contains facts.

Validation influences candidate selection; it is not untouched acceptance
testing. Inspect which development cases the training mini-batches actually used.
**Do not promote a candidate as part of the walkthrough.**

Ask **"what are we optimising for?"** This job optimises the native rubric's weighted
quality score, not the binary reference-correctness pass rate. Its clarification-first
dimension caps conditional branching at 3/5 and rewards direct clarification at
5/5. Other dimensions can still lift the overall score; its existing pass threshold
is 0.5, not a guarantee that every dimension is strong. Use the binary judge in the
initial evaluation to show the stricter, all-or-nothing view. Scores from earlier
binary-only optimisation jobs are not directly comparable to rubric scores.

## Run the sample

Run all commands from `sample/`. For a new environment, complete **First-time
setup** below first. For an existing environment:

```bash
ENVIRONMENT="<your-azd-environment>"
azd env select "$ENVIRONMENT"
export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT -e "$ENVIRONMENT")"
azd ai agent show purchasing-advice-demo -e "$ENVIRONMENT"
```

Both workflows use the latest agent and evaluator versions without hard-coded
version numbers.

For a fresh invocation, reset both the session and conversation:

```bash
# BILLABLE. Single quotes keep $ amounts intact.
azd ai agent invoke purchasing-advice-demo \
  'Decision date: 2026-10-20. I need a mouse for an Orion employee in Singapore. What information do you need?' \
  --new-session --new-conversation -e "$ENVIRONMENT"
```

Check that an answer arrives, not just exit code 0. In Foundry Tracing or the
connected Application Insights, inspect correlated `chat` and `execute_tool`
spans, including tool arguments/results. Allow time for ingestion.

For local development, run `.venv/bin/python agent/main.py` with the exported
endpoint and Azure credentials. `.env.example` is documentation, not loaded
automatically. For an authorised app-only update, use
`azd deploy purchasing-advice-demo -e "$ENVIRONMENT"`, not `azd up`.

### Evaluate and optimise

**Python submits evaluation; azd submits optimisation.** Evaluation uses both
evaluators with GPT-5.5: binary `purchasing-next-action` for
reference correctness and native `purchasing-demo-rubric` for weighted quality.
Optimisation uses only `purchasing-demo-rubric`, keeping its objective explicit.
Editing either local definition does not update its registered version.
`evaluate.py` makes two explicit `ensure_evaluator` calls before submission:
reuse the latest registered version, or register its JSON definition if the
evaluator is absent. It does not publish local edits over an existing evaluator;
register an edited definition as a new version before using it. Register missing
evaluators without scoring before a standalone optimisation if needed:

```bash
# Local preview: no credentials, cloud calls or generated files.
uv run --frozen python evaluation/evaluate.py --dry-run

# Register missing evaluators only; no agent calls or scoring.
uv run --frozen python evaluation/evaluate.py --register-only

# BILLABLE: 32 questions sent to the agent, then scored by both evaluators.
uv run --frozen python evaluation/evaluate.py

# BILLABLE: one optimisation, capped at three candidates.
azd ai agent optimize --config evaluation/optimize.yaml \
  -e "$ENVIRONMENT" --no-wait --no-prompt

# Read-only progress for the returned job ID.
azd ai agent optimize status JOB_ID -e "$ENVIRONMENT"
```

Use the returned IDs to view answers and scores in Foundry. A `completed` run
can still contain errored or skipped rows; these are not quality judgments.
Keep run IDs, reports and deployment history outside the repository.

Use App Insights over the job's full time range to inspect draft versions,
effective instructions, model calls and tool activity. Correlate evaluation
rows' trace IDs with spans rather than counting every span as another trial.
`az monitor app-insights query` defaults to the last hour; supply the job's
`--start-time` and `--end-time` for older runs. Telemetry exposes agent-side
experiments, but not the service's private reflection prompt or exact inputs.

Keep the deployed baseline aligned with local source and leave inputs unchanged
during optimisation. The static YAML uses separate development and validation
datasets; its paths resolve from `sample/agent/`, not from the YAML directory.
No preparation script or copied input package is needed.

References go to the evaluation/optimisation service, not the agent. The binary
judge receives them; the native rubric has no ground_truth input. The exact
internal reflector inputs are not established. Inspect full resolved candidate
configuration, not only mutation records. The installed optimisation SDK applies
function descriptions but not parameter descriptions.

The CLI may rewrite baseline `metadata.yaml`. Preserve the run evidence, compare
the referenced tool bytes and restore only an unintended `tools_file` path.
Do not blindly reset local changes or apply the selected candidate.

### CI/CD

PRs and pushes to `main` run `.github/workflows/local-checks.yml`: Ruff and an
offline evaluation-request check. No Azure credentials or model calls are needed.

Run **Deploy and evaluate demo agent** manually from `main` in GitHub Actions
for the cloud stage. It runs the same checks, signs in with OIDC, deploys only
`purchasing-advice-demo` to existing infrastructure, then evaluates all 32
development cases with both judges. It does not provision infrastructure,
optimise, enable continuous evaluation or promote a candidate.

Create a GitHub environment named `demo`, restrict deployment branches to `main`
and configure a required reviewer if available. Configure an Azure OIDC identity
with subject `repo:<owner>/<repository>:environment:demo`; no client secret is
needed. For code deployment, grant that identity **Contributor** and
**Foundry User** on the project, plus account-level **Foundry User** for judging.
The companion Bicep's `evaluatorPrincipalId` can grant the inference role with
`evaluatorPrincipalType=ServicePrincipal`; it does not grant deployment access.

Set these GitHub environment variables from your selected azd environment:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | OIDC application's client ID |
| `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Target tenant and subscription |
| `AZURE_ENV_NAME`, `AZURE_LOCATION` | Existing azd environment name and location |
| `AZURE_AI_PROJECT_ID`, `FOUNDRY_PROJECT_ENDPOINT` | Existing project's resource ID and endpoint |

The evaluation command uses `--wait --report evaluation-summary.json`. It waits
up to 60 minutes and fails on execution errors, missing scores or incomplete
results. Quality failures are reported, not a release threshold: a green job
does not mean every answer passed. GitHub publishes mean scores and pass counts
in the job summary and a seven-day artifact, without raw prompts, answers or
traces. A local timeout does not cancel the cloud evaluation; follow its run ID.
Do not deploy to the same agent elsewhere while the workflow is running.

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
It also grants the project's managed identity **Foundry User** on its own project
and **Monitoring Reader** on Application Insights for trace access.
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

If denied, resolve access before proceeding, then deploy the agent:

```bash
azd deploy purchasing-advice-demo -e "$ENVIRONMENT" --no-prompt
azd ai agent show purchasing-advice-demo -e "$ENVIRONMENT"
azd ai agent doctor -e "$ENVIRONMENT"
```

Evaluation and optimisation use the latest deployed agent.
Evaluator registration is handled by `evaluate.py` as described above.
Do not recreate resources or redeploy just to reset a stage demo.

</details>
