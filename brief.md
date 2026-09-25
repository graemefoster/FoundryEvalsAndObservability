# AI Genius S6 E2 — Presentation Brief

**Working title:** From Prompt to Production  
**Speaker:** Graeme Foster  
**Series:** Microsoft AI Genius, Season 6, Episode 2  
**Status:** Approved HTML deck and editable PowerPoint export; demos remain to be built  
**Brief updated:** 24 September 2026

## Purpose

Create a 60-minute, demo-led AI Genius session showing how Microsoft Foundry helps teams build agents that remain useful, measurable, cost-conscious, and continuously improvable.

The presentation is a skeleton supporting live demonstrations. Slides should introduce one concept at a time, remain visually sparse, and avoid teaching implementation details that are better shown in the demos.

Microsoft Foundry must be the hero. The fictional scenario provides continuity, but must not hide the underlying services or engineering workflow.

## Primary Audience

- Mixed external event audience, with a significant number of graduates.
- Primarily developers, AI engineers, and solution architects.
- Skewed toward beginners, with some intermediate practitioners.
- Assume familiarity with:
  - Basic Python
  - Git and GitHub
  - LLM and prompting basics
  - Azure basics
  - CI/CD basics
- Do not assume expert knowledge of Microsoft Foundry, Microsoft IQ, evaluations, tracing, or agent optimisation.

## Desired Audience Outcome

Attendees should understand:

1. Why agents need good organisational context.
2. Why one successful answer is not enough to establish consistent task performance.
3. How evaluations make agent quality measurable.
4. How quality, latency, tokens, tool calls, and model cost influence production decisions.
5. How Agent Optimizer can improve instructions, tool descriptions, and model choice.
6. How evaluation evidence can flow into a GitHub-based delivery process.
7. Why Microsoft Foundry provides a strong end-to-end environment for this work.

## Core Message

Use this three-part mental model throughout:

> **Start with a working agent. Measure consistency, speed and cost. Improve with evidence.**

Closing version:

> One working agent. Consistent answers. Measured trade-offs. Repeatable release checks.

## Session Format

- **Total duration:** 60 minutes
- **Closing and Q&A:** 10 minutes
- **Content and demos:** 50 minutes, including two minutes for the delivery lifecycle and one minute for further exploration
- **Delivery:** Live remote
- **Balance:** Approximately 30% slides and 70% demonstrations
- **Demo style:** Live questions and trace inspection; prepared evaluation, optimisation and pipeline runs. No live coding. Saved evidence is available at every stage.
- **Demo slide treatment:** Minimal bumper only — demo number, short title and one sentence describing what the audience is about to see. All teaching detail stays in speaker notes and the live demonstration.
- **Number of labelled demos:** Six
- **Slide target:** 18 slides
- **Tone:** Practical, engineering-led, accessible, fast-paced, and friendly but mostly straight
- **Slide density:** Sparse; one concept plus a few supporting labels

## Session Copy to Satisfy

The published copy promises that attendees will learn:

- How to compare and select models with Microsoft Foundry.
- How to add organisational context to agents.
- How to build continuous evaluation pipelines.
- How to profile quality, speed, and token cost.
- How to use Agent Optimizer.
- How to manage an agent in a CI/CD pipeline.

Technologies called out:

- Microsoft Foundry
- Microsoft Foundry extension/Toolkit for Visual Studio Code
- Microsoft Foundry evaluations
- Agent Optimizer
- GitHub Actions

The deck and demos must visibly address each promise, even when the treatment is intentionally brief.

## Narrative Strategy

Use one coherent agent and one purchasing scenario throughout.

The story should lead the audience through Microsoft Foundry rather than becoming the main attraction. Each demo should answer one obvious question and expose a different Foundry capability.

The central question is:

> The agent works. How consistently does it work, and what does each successful answer cost?

The engineering story is:

1. Introduce the purchasing agent and the question that connects the demonstrations.
2. Choose a starting model or routing configuration.
3. Connect institutional and workplace context and save a working baseline run.
4. Inspect its calls, evidence, prompts, responses and timings.
5. Evaluate consistency across purchase types, dates and incomplete requests.
6. Use the results to choose an optimisation objective and freeze the baseline, dataset and criteria.
7. Run Agent Optimizer and inspect the actual candidate results and configuration differences.
8. Select a candidate based on answer consistency, response time and estimated cost, or retain the baseline.
9. Carry the selected configuration through release tests and approval.
10. Introduce a separate, deliberate regression to demonstrate the release checks, then show ongoing evaluation.

Each demo corresponds to a saved stage with a playbook. Findings come from measured runs, not a scripted tool omission. The missing-IQ-call scenario is no longer a dependency of this presentation.

## Fictional Scenario

Use a fictional online learning provider named **Nova Learning**.

The user is an employee or learning-and-development stakeholder asking:

> **Can I spend $6,250 on 25 Nova Learning licences for our new graduate employees?**

The fictional organisation name still needs to be chosen. Do not use Contoso unless it becomes useful during implementation.

### Stable Policy in Foundry IQ

> Purchases above $5,000 require two quotes and Category Manager approval.

### Current Exception Through Work IQ

Use these fixed fictional facts consistently across slides, source documents, prompts, tests, and demos:

- **Decision date:** 3 November 2026.
- **Exception email date:** 1 November 2026.
- **Author:** People Director.
- **Authority:** The People Director authorises the exception under the purchasing policy; the Head of Learning remains the purchase approver.
- **Scope:** Nova Learning licences for the new graduate programme.
- **Supplier status:** Nova Learning is pre-approved for this programme.
- **Exception route:** One supplier quotation and Head of Learning approval replace the normal two-quotation and Category Manager route.
- **Expiry:** Approval must be obtained by 30 November 2026.
- **Business impact:** Following the standard route adds unnecessary administration and can delay graduate training.

Use this visible disclosure when the simulated connection is shown:

> **Synthetic example:** The exception email is fictional and served through a sample Work IQ adapter.

### Required Good Answer

The correct response should include:

- A direct answer.
- The applicable policy threshold.
- The current exception.
- The correct approval route.
- The exception expiry date.
- Citations to the policy and current email.
- A recommended next action.

### Simple Evaluation Cases

Keep the dataset deliberately small and understandable:

1. Graduate learning licences before the exception expires.
2. A purchase below the normal threshold.
3. A different purchase category, such as hardware.
4. The same learning-licence purchase after the exception expires.
5. Inaccessible context or missing request details.

Add paraphrases and repeat representative cases to assess variation. Use the case's supplied decision date, not the machine clock, so saved and live runs remain comparable.

## Working Baseline and Optimisation Goals

The baseline agent has access to both Foundry IQ and the Work IQ tool interface, with reasonable instructions and tool descriptions. Establish that it can answer the opening question; do not deliberately weaken it to produce a failure.

Primary experiment: **answer consistency across the purchasing dataset**. Measure correct approval routes, applicable dates, citations and actionable next steps.

Secondary experiments:

- Clearer, more concise responses.
- Comparable task quality at lower estimated cost.
- Lower response time or fewer unnecessary calls where measured.

Choose the experiment from baseline evidence. If the initial quality scores are already strong, investigate quality-preserving efficiency rather than constructing a miss. A candidate is retained only when its measured trade-off supports the decision.

Preserve actual reports, traces, configurations and source versions. The deliberately regressed configuration used in the CI/CD demonstration is separate from this baseline and is labelled as a test of the release checks.

## Technical Demonstration Plan

### Agent

- Microsoft Foundry hosted/code agent.
- Python implementation.
- Keep the code intentionally small and readable.
- Show project structure and selected files rather than writing code live.

Likely files:

- `agent.py`
- `instructions.md`
- Tool configuration or adapters
- Evaluation dataset/configuration
- Tests
- GitHub Actions workflow

### Context Connections

- **Foundry IQ:** Real connection for institutional knowledge such as policies and authoritative documents.
- **Fabric IQ:** The IQ layer for governed business entities and live business state. Use “spend so far” and remaining budget as the scenario example, but do not demo it.
- **Work IQ:** Workplace context across people, collaboration and workflows. Initially represented by a sample/mock adapter using the synthetic manager email.
- **Web IQ:** Not required for this session.

The live narration must briefly disclose that the initial Work IQ implementation is a sample adapter. This disclosure belongs in speaker notes and should be spoken during the relevant demo without distracting from the story.

### Sample Repository

The attendee-ready sample repository should use mocks by default so graduates can run it without enterprise tenant configuration.

Use one shared implementation with runnable configuration checkpoints, rather than a copy of the application per stage. Planned structure:

```text
agent/                       Shared implementation and adapters
stages/
  01-model-choice/
  02-grounding/
  03-observe/
  04-evaluate/
  05-optimise/
  06-automate/
datasets/                    Versioned cases and rubric definitions
evidence/                    Saved traces, reports and configuration diffs
.github/workflows/           Release checks and scheduled evaluation
```

These folders are the demo build plan; they have not yet been implemented.

Each stage playbook must include the starting configuration, prerequisites, exact commands and portal steps, what to inspect, saved outputs and a reset procedure. Record run IDs, source versions and environment requirements. Prepared evidence must be identified as such.

| Stage | Checkpoint |
| --- | --- |
| 01 — Model Choice | Starting model or routing configuration and comparison evidence |
| 02 — Grounding | Working baseline, source fixtures, question, answer and run ID |
| 03 — Observe | Same agent as stage 02; trace, call sequence and timings |
| 04 — Evaluate | Frozen baseline, dataset, rubric and per-case report |
| 05 — Optimise | Actual generated candidates, operation IDs, reports, configuration diff and selected configuration |
| 06 — Automate | Release suite, workflow results and separately labelled regression checkpoint |

Observe and Evaluate add evidence without requiring code changes. Stages must be independently resumable from their recorded inputs.

The Optimise playbook records the executed workflow, for example:

```bash
azd ai agent optimize --config eval.yaml
azd ai agent optimize status OPERATION_ID --watch
azd ai agent optimize apply --candidate CANDIDATE_ID
```

Keep the real baseline and candidate configurations. Applying a candidate prepares local configuration; release checks and approval precede deployment. Record actual command arguments and outputs during implementation, including how to restore the baseline.

Include mock adapters for local use, a documented path to real services, and the GitHub Actions workflow. The sample repository URL remains to be supplied.

## Model Selection

Introduce the agent and purchasing question after the agenda. Then introduce model choice with three model examples prioritising quality, speed and cost, and compare options in Foundry. Revisit the starting choice later using the task and its business-specific definition of a good answer.

Teach three concise lessons:

1. The biggest model is not automatically the best production choice.
2. Public benchmarks and leaderboards help narrow the field.
3. The team's task-specific evaluation makes the final decision.

Use the Microsoft Foundry portal model comparison in Demo 1. Establish task-specific baseline performance in Demo 4, then compare Optimizer candidates in Demo 5 using quality, end-to-end time, input/output tokens, tool calls and estimated cost.

Use Foundry Toolkit in Visual Studio Code for the developer workflow, agent project, evaluation, and related development experiences.

Do not invent model scores or costs in the draft deck. Use concepts and placeholders until the demonstration produces measured values.

## Evaluation Strategy

Explain, but do not deeply teach:

- Built-in Groundedness and Customer Satisfaction evaluators.
- The Rubric evaluator with custom business criteria.
- Batch evaluation datasets.
- Baseline-versus-candidate comparison.
- The ability to bring evaluation output into CI/CD.

Documentation checked 24 September 2026:

- Groundedness checks whether a response is supported by the supplied context: https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators
- Customer Satisfaction (preview) predicts satisfaction from conversation messages across helpfulness, completeness, clarity, tone, resolution and adaptability: https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators
- Rubric (preview) uses an LLM judge to score custom, weighted criteria appropriate to the task: https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rubric-evaluators

For the demo, map the retrieved context into Groundedness and conversation messages into Customer Satisfaction. Check tool-input support when wiring the agent evaluation; the documentation lists limitations for some retrieval tools. Keep response time, tokens, tool calls and estimated cost as companion comparison metrics, not as a third evaluator tile.

### Business Rubric

The rubric should check:

- Policy use.
- Current exception use.
- Correct approval route.
- Expiry awareness.
- Citations.
- Actionable next step.

The teaching point is:

> Built-in evaluators assess general qualities; the rubric measures the requirements of our purchasing task across cases.

Do not require a particular disagreement between evaluator scores. Show per-case explanations and measured variation. Keep optimisation cases, optional validation cases and final release cases separately versioned. Record quality requirements before selecting a candidate.

Avoid unexplained composite scores and illustrative numbers in the deck. Use real results after the demo is built.

## Observability

Use Foundry tracing to inspect LLM calls, tool calls, captured prompts and responses, and timings.

The trace demonstration should remain focused:

1. Open the saved baseline interaction.
2. Follow the LLM and tool calls, including both IQ sources when used.
3. Inspect captured prompts, evidence, responses and timings.
4. Save the request and expected outcome as a repeatable evaluation case.

Core message:

> A trace explains how an answer was produced and where the agent spent its time.

## Agent Optimizer

Use a prepared optimisation run rather than starting an optimisation live.

The optimiser should be shown exploring:

- System instructions.
- Tool descriptions.
- Model choice.

Use the baseline results to choose the objective, with answer consistency as the primary experiment. Inspect per-case results and the actual changes to instructions, tool descriptions and model choice.

Compare rubric performance and built-in evaluator scores alongside speed, token use and estimated cost. Keep the quality requirement fixed when considering a cheaper configuration. Candidate changes and improvements must come from the recorded run, not prewritten expectations.

Revisit the opening question and a changed date or purchase type. Apply a candidate when its results support the trade-off; otherwise retain the baseline. Explain the optional validation dataset in the demo and run separate release tests in Automate.

## CI/CD

Allocate two minutes for the concept and five minutes for the demonstration.

Show a completed GitHub Actions run rather than running the full workflow live.

Show the selected configuration entering release checks. Use cases outside optimisation and candidate selection, with quality requirements and operational limits recorded in advance.

For the gate demonstration, introduce a separately labelled, deliberate configuration regression. Retain its exact diff and actual failed-check evidence. It is a test of the release workflow, not the baseline used for the Optimizer experiment. Follow with approvals, deployment, rollback and scheduled checks.

Suggested explanation:

> Preserve the quality requirement as the agent changes.

End-to-end loop:

> Trace → dataset → evaluation → comparison → optimisation → deployment.

## Approved Slide Structure

The deck uses one consistent rhythm: a concise concept slide followed immediately by its live demonstration. Concept headings match the agenda. Each has three compact visual blocks, revealed manually in no more than three steps, introducing what to look for. Demo bumpers contain only the demo number, a short title and an invitation to investigate. The concept slides and their speaker notes set up the questions; the demonstrations reveal the findings.

### 1. From Prompt to Production

Open with a working agent, then pose the question of consistency, speed and cost. Introduce the six-stage progression without promising particular results.

### 2. Agenda

Title: **What we'll cover.** Use a simple numbered agenda in reading order, not a loop or process diagram:

- **Model Choice:** model comparison and Model Router.
- **Grounding:** Foundry IQ, Fabric IQ and Work IQ.
- **Observe:** Foundry tracing.
- **Evaluate:** quality, latency, tokens and cost.
- **Optimise:** Agent Optimizer.
- **Automate:** continuous evaluation and GitHub Actions.

### 3. Meet the Agent

A quick introduction to the purchasing advice agent: it helps employees understand what they can buy and which approvals they need.

A learning coordinator asks:

> Can I spend $6,250 on 25 Nova Learning licences for our new graduate employees?

Use the agent illustration beside the question. Allow one minute; keep the policy, exception and answer for the demonstrations. Explain that later cases vary dates, purchase types and available information.

### 4. Model Choice

- **Model 1 — optimised for quality:** complex reasoning and multi-step tasks. Trade-off: higher cost ($$$) and slower responses.
- **Model 2 — optimised for speed:** responsive chat and quick interactions. Trade-off: less capable on complex tasks.
- **Model 3 — optimised for cost:** high-volume, repeatable tasks. Trade-off: less suited to nuanced requests.

Use three distinct SVG model characters with manual reveals. Keep the slide literal and introduce Model Router in the portal demonstration.

### 5. Demo 1 — Foundry Model Comparison

Compare fixed models and Model Router, then save a starting configuration in stage 01. Treat the choice as a hypothesis that will be tested later.

### 6. Grounding

- **Foundry IQ:** institutional knowledge; policies, procedures and reference documents.
- **Fabric IQ:** governed business entities and state; conceptual spend-so-far context, not used in the demo.
- **Work IQ:** workplace context; recent decisions, conversations and approvals.

Connect the source types to the purchasing question. Keep the policy threshold and exact exception for the demonstration.

### 7. Demo 2 — Run the Starting Agent

Ask the purchasing question and inspect the answer, then open the source documents, instructions and available tools. Save the working baseline and run ID in stage 02. A correct answer is a useful starting point; the demonstration does not depend on a missing source call.

### 8. Observe

- **Calls:** which LLMs and tools ran, and in what order?
- **Inputs & outputs:** what prompts, responses and evidence passed between steps?
- **Timing:** where did the agent spend its time?

### 9. Demo 3 — Inspect the Trace

Follow the saved run's calls, evidence, prompts, responses and timings. Save the trace and timing evidence in stage 03 without changing the agent. Use the request and expected outcome as a repeatable case.

### 10. Evaluate

- **Groundedness — built-in:** is the answer supported by the supplied context?
- **Customer Satisfaction — built-in, preview:** how satisfied would the user be with the conversation?
- **Rubric — custom criteria, preview:** does the answer meet task-specific requirements such as approval route, expiry and next action?

Introduce the rubric and representative cases for a valid exception, expired exception, out-of-scope purchase and unavailable evidence. Reveal scores and pass/fail outcomes in the demonstration.

### 11. Demo 4 — Evaluate Across Cases

Inspect the baseline across valid and expired exceptions, different purchase types and missing information. Review Groundedness, Customer Satisfaction and Rubric scores alongside operational metrics; repeat representative cases to assess variation. Freeze the configuration, dataset, criteria and report in stage 04. Choose the optimisation objective from these results.

### 12. Optimise

- **Baseline:** freeze the working configuration, cases and scores; measure answer consistency.
- **Candidates:** use Agent Optimizer to test changes to instructions, tool descriptions and model choice.
- **Compare:** compare scores and configuration changes; ask whether quality improves or holds at lower cost.

Explain the comparison method here; reveal candidate changes and results in the demonstration.

### 13. Demo 5 — Agent Optimizer

Show the playbook command and its completed run. Compare actual candidate results and configuration changes with the frozen baseline. Explain the optional `validation_dataset` within Agent Optimizer: it supplies separate evaluation cases; if omitted, the optimisation dataset is used for evaluation. Record the operation ID, reports and diffs in stage 05. Apply a candidate when supported by the evidence, or retain the baseline, then proceed to release testing.

Documentation checked 24 September 2026:

- https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/optimize-agent-targets
- https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-optimizer-costs

### 14. Automate

- **Trigger:** agent changes, source updates and scheduled checks.
- **Evaluate:** run the broader release test suite, including cases kept outside optimisation and candidate selection; check operational limits and retain reports. Continue sampled evaluation after deployment.
- **Release:** review, gate, deploy and retain a rollback path.

Distinguish pre-release regression testing from post-release continuous evaluation. Introduce the triggers, checks and release criteria without showing a particular run's outcome.

### 15. Demo 6 — Release Check

Follow the selected configuration through GitHub Actions, inspect its release report, then reveal the gate result. Introduce the separately labelled deliberate regression and inspect its checks. Save reports, run IDs and the resettable regression configuration in stage 06. Show approval, deployment, rollback and scheduled checks.

### 16. From Test Cases to Production

After the release-check demo, synthesise the lifecycle in three connected panels. Keep the existing Automate introduction unchanged.

- **Build / pre-launch:** Simulation feeds a reviewed, versioned golden dataset with agreed expected outcomes and a rubric.
- **On every change / CI/CD:** Pull request → build and unit/tool-contract tests → agent evaluation against the golden dataset → quality, latency and cost gates → versioned deployment and smoke checks. Failed gates stop promotion.
- **In production:** Evaluate sampled agent traces, monitor quality and operational metrics, and alert.

Keep a single **Optimise** box below production, with "Compare candidates" underneath. Connect production down to Optimise, then route the return arrow left and up into the bottom of the CI/CD panel, clear of the golden-dataset connector. No separate findings, case-review or duplicate pull-request boxes. The return represents a new change entering the pipeline: a candidate must go through the same tests and release gates, never directly into production. Retain the baseline if no candidate justifies a change.

Reviewed findings inform deliberately curated, versioned datasets; generated responses are not automatically ground truth. Keep final release cases outside optimisation and candidate selection. Pin artifacts, dataset, rubric, judge configuration and source versions for reproducibility.

Keep the diagram sparse: no separate purchasing-cases box, CI/CD subheading, approval step or recovery box. The five CI/CD steps show headlines only; supporting descriptions stay in speaker notes. This is the intended engineering lifecycle, not a claim that every capability was demonstrated. Gates and alerts require explicit workflow/application implementation. Simulation and trace-to-dataset generation are preview capabilities.

Allow two minutes, taken from Q&A. Documentation checked 24 September 2026:

- https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluation-dataset-synthetic
- https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluation-datasets
- https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/traces-to-dataset
- https://learn.microsoft.com/en-us/azure/foundry/concepts/observability
- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

### 17. Worth Exploring Next

Use the agenda's 3×2 grid for six short signposts:

- **Human Annotation:** Bring domain experts into evaluation.
- **Synthetic Test Data:** Expand the cases you test.
- **AI Red Teaming:** Test adversarial behaviour.
- **Guardrails:** Protect inputs and tool responses.
- **Identity & Permissions:** Limit what the agent can access.
- **Human Approvals:** Keep people in control of actions.

Allow one minute, with no additional demonstration. Human annotation remains outside the main Evaluate segment. Distinguish assessing an answer from authorising an action. Feedback must be explicitly curated into criteria and datasets; do not imply annotations automatically train the judge or feed Agent Optimizer. Human approvals would extend the current advice-only agent into a purchasing workflow.

Speaker notes connect these topics to purchasing expertise, policy-derived test cases, adversarial requests, malicious content in retrieved emails, enterprise access boundaries and approval before submission.

Documentation checked 24 September 2026:

- Human Evaluation (preview): https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/human-evaluation
- Synthetic Test Data (preview): https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluation-dataset-synthetic
- AI Red Teaming: https://learn.microsoft.com/en-us/azure/foundry/concepts/ai-red-teaming-agent
- Prompt Shields: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-prompt-shields
- Agent Identity: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity
- Human Approval for long-running hosted agents (preview): https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/add-human-in-the-loop

Verify feature availability and support for the chosen agent type before any future implementation.

### 18. Build → Measure → Improve → Repeat / Q&A

Close with:

> One working agent. Consistent answers. Measured trade-offs. Repeatable release checks.

Allow 10 minutes for the close and questions after 50 minutes of content and demonstrations.

## Speaker Notes

Every slide should eventually contain:

- Suggested timing.
- Plain-English definitions.
- Key message to repeat.
- Exact transition into the next demo or concept.
- Demo click path where relevant.
- Brief source/documentation references.
- Spoken disclosure for the Work IQ mock adapter.

The HTML prototype currently includes:

- Timing.
- Definitions.
- Talk track.
- Key message.
- Transition.
- Source note.
- Demo checkpoint guidance for each of the six stages.

## Visual Direction

Use the **FY27 Microsoft AI Genius dark template** as the visual source of truth.

Required visual characteristics:

- True black canvas.
- Microsoft AI Genius wordmark.
- Colourful isometric cube motif framing the slide edges.
- Large white headings.
- Generous empty space.
- Sparse content.
- Dedicated visual state for demo slides.
- Dedicated Q&A treatment.
- Thank-you treatment available for the final PowerPoint if required.

Do not include the template's **Classified as Microsoft Confidential** label.

The HTML prototype uses extracted template artwork to approximate the intended look and feel. It is an iteration tool, not the final marketing asset.

The marketing team can use the editable PowerPoint export for final template/master integration and production polish.

## HTML Prototype

Current file:

- `deck.html`

Template background assets:

- `assets/ai-genius-title.jpg`
- `assets/ai-genius-content-minimal.jpg`
- `assets/ai-genius-content-framed.jpg`

Prototype functionality:

- Arrow-key navigation.
- Clickable slide overview.
- Presenter-notes panel.
- Elapsed timer.
- Slide progress.
- Fullscreen mode.
- Print/PDF layout.
- Designed demo wireframes/placeholders.
- `?slide=N` query parameter for direct slide rendering.
- `#slide-N` URL fragments for shareable slide links and restoring the current slide after refresh. Navigation updates the fragment without adding a browser-history entry for every slide; a valid fragment takes precedence over `?slide=N`.

The HTML remains the narrative source of truth. Keep it easy to change and regenerate the PowerPoint export when the approved content changes.

## PowerPoint Export

- **File:** `AI_Genius_S6_E2_From_Prompt_to_Production.pptx`
- **Content:** All 18 approved slides, speaker notes, timings and documentation references.
- **Editable elements:** Native PowerPoint text, cards and process-diagram shapes. Model/agent illustrations are SVG artwork with PNG fallbacks.
- **Reveals:** Three click-to-reveal groups on each of the six concept slides.
- **Template treatment:** Uses the official exported AI Genius artwork in reusable PowerPoint layouts. The supplied template is rights-protected, so its original slide-master structure is not inherited.
- **Typography:** Arial for portable rendering; final brand-font substitution can be applied during marketing polish.

The user approved this artwork-based, editable export approach. Original template and reference files are unchanged.

## Terminology and Language

- Use UK/Australian English for general copy.
- Preserve official product spelling and branding, including **Agent Optimizer**.
- Explain these terms in plain English before relying on them:
  - Grounding/context
  - Foundry IQ
  - Work IQ
  - Evaluation/evaluator
  - Rubric
  - Trace/observability
  - Agent Optimizer

## Delivery Milestones

Dates agreed from the planning conversation:

- **Draft slides usable:** 24 September 2026
- **Demo implementation target:** Approximately 6 October 2026
- **Run-through target:** Approximately 22 October 2026
- **Live delivery target:** Approximately 3 November 2026

## Existing Source Files

- `copy.txt` — published session copy and learning promises.
- `AI_Genius_S6_E2_Hosted_Agent_Optimizer_Rebuilt 1.pptx` — original binary PowerPoint saved with a `.pptx` extension.
- `converted.pdf` — readable export of the original 16-slide concept deck.
- `NEW_FY27 Microsoft AI Genius_PPTtemplate_Dark.pdf` — official visual template reference.
- `deck.html` — current interactive narrative prototype.

## Decisions Intentionally Deferred

- Final fictional organisation name.
- Actual models used in the comparison.
- Real measured evaluation, latency, token, and cost results.
- Final Work IQ connection.
- Final screenshots and live-demo fallback assets.
- Sample repository URL and QR code.
- Final PowerPoint conversion/rebuild.
- Whether the marketing version adds separate feedback, series-page, certified-badge, or thank-you slides.

## Immediate Next Steps

1. Review and iterate the 18-slide narrative in `deck.html`.
2. Finalise the fictional policy, email exception, and expected answer.
3. Build one shared Python hosted-agent sample with six resumable stage checkpoints and playbooks.
4. Connect real Foundry IQ.
5. Implement the mock Work IQ adapter behind a replaceable interface.
6. Create the five case families and business rubric, with paraphrases, repeated runs and separate release cases.
7. Establish a working baseline and preserve its configuration, source versions, trace and per-case evaluation.
8. Choose an objective from baseline evidence and preserve a completed Agent Optimizer run, actual candidate diffs and the selection decision.
9. Add a GitHub Actions release workflow with prepared results and a separately labelled, resettable regression checkpoint.
10. Replace HTML demo wireframes with screenshots or confirmed click paths.
11. Hand the editable PowerPoint, approved narrative and assets to marketing for final template integration and polish.
