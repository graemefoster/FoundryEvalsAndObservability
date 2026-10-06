# Five demos, one purchasing agent

**12-15 minutes. No live coding, deployments or waiting for an optimiser.**
Before the session, follow [PRESENTER-NOTES.md](PRESENTER-NOTES.md) to open the tabs,
check access and prepare fallbacks. Keep this page as your live run sheet.
The comparison below is the earlier development-only run. A separate native
holdout-validation run has now completed: baseline 8/12, selected candidate 1 9/12,
candidate 2 8/12. See the presenter notes; do not mix the two runs' scores.

## 1. Initial agent - ask a question (2 minutes)

**Open:** Foundry, `grfpublicfoundry / proj-default`, agent `purchasing-advice-demo:1`.
In a fresh conversation, ask:

> Decision date: 2026-10-05. Can I order desks from DeskCo? I don't have the total
> price yet and have not committed to anything. What should I do next?

**Show:** the answer, then briefly the original instructions and two search tools.
Do not walk through the Python. Live wording may differ from the recorded answer.

**Say:** "A small hosted agent, searching fictional policies and workplace notices.
It can advise, not approve or buy. Getting the policy facts right is only the start:
is it clear what this employee should do next?"

**Bridge:** "Let's make that preference measurable."

## 2. Initial evaluation - define success (3 minutes)

**Open:** the prepared [initial evaluation](PRESENTER-NOTES.md#tabs-to-open).
Show its **9/16 passes**, one failed missing-facts case, and the judge's reason.
In the IDE, show one development dataset row beside the next-action evaluator.

**Say:** "These are synthetic questions and reference answers, but real agent calls.
Only the question goes to the agent. The judge receives three things: the question,
the golden reference's expected facts and next action, and the actual agent answer.
Our evaluator instructions define success; it returns a pass/fail score and a reason.
Here, success means asking for the missing amount before listing approval routes."

**Land this:** "The golden reference is our answer key, not a hidden agent input.
This judge does not inspect the candidate system prompt or the retrieved documents,
so a pass doesn't prove where the answer's knowledge came from."

Point out the four case groups: missing facts, remaining requirements, exceptions,
and ready to proceed. "An agent that always asks another question should not win."

**Bridge:** "The score tells us where to look. The trace helps explain what happened."

## 3. Traces - inspect the evidence (2 minutes)

**Open:** the matching trace you rehearsed. Expand one model call and one search.
Show its search terms, returned document and final answer; stop there.

**Say:** "The evidence was available. Retrieving the right policy and using it well
are different things. Foundry hosting and Agent Framework provide the tracing;
we haven't built our own telemetry framework."

**Bridge:** "A test dataset is one view. How would we watch real usage?"

## 4. Continuous evaluation - show where to enable it (2 minutes)

**Open:** **Build > Evaluations > Recurring Configs > Create**.
Select this agent, **Continuous evaluation**, and **Live traffic**. Show the evaluator
selection and sampling/run limit. Follow the [portal steps](PRESENTER-NOTES.md#continuous-evaluation-portal-walkthrough).

**Say:** "This samples real interactions. Unlike our test dataset, live questions
don't arrive with reference answers, so we need an evaluator that can work without
them. Scheduled benchmark runs are a separate option."

**Default: stop before creating/enabling.** No continuous evaluation is configured
in the recorded project check; this beat demonstrates setup, not existing results.
Enable only if deliberately rehearsed and budgeted by the presenter.

**Bridge:** "Monitoring finds opportunities. The optimiser tries changes against
the objective we've defined."

## 5. Optimiser - improve, then question the improvement (4 minutes)

**Open:** the completed optimiser run and its baseline/candidate comparison.
Show the recorded desk answers, then the selected system prompt.

| Configuration in this search | Passes | Prompt words |
| --- | ---: | ---: |
| Fresh baseline | 10/16 | 233 |
| Candidate 1 | 15/16 | 992 |
| Selected candidate 2 | 16/16 | 1,551 |

**Say:** "The optimiser generated a fresh baseline: 10/16, not the earlier 9/16.
The selected answer asks for the amount without listing both routes.
But the prompt now includes policy facts and examples. Our judge scores the
answer, not whether the system prompt contains facts."

Show **`golden-development.jsonl` (16 cases)** and **`golden-holdout.jsonl` (12 cases)**.
"Keep both: golden development data guides optimisation; the holdout is passed
separately as the optimiser's validation set, not mixed into training. In our new
run, the selected candidate scored 9/12 on that holdout and still embedded policy
facts. Different questions can use the same rules, so this does not test whether
the agent follows changed evidence. The validation scores also help compare
candidates; they are not an untouched final acceptance test."

**Close:** "16/16 is a development result, not a production guarantee.
That earlier candidate hasn't been evaluated on the holdout or deployed.
The separate validation run selected a different candidate at 9/12."
