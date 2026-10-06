# Demo evidence

Generated evidence is ignored by Git by default. Do not check in credentials,
tenant data or real employee prompts. Review synthetic outputs before deliberately
adding selected evidence with `git add -f`.

Save each real run with:

- Source commit and dirty-tree diff, baseline/candidate configuration and source fixtures.
- Exact command, supplied decision date, model deployment and agent version.
- Trace ID, operation/run/candidate IDs, per-case results and dataset/rubric versions.
- Duration, total input/output tokens, tool calls, and dated prices if estimating cost.
- A clear label: live run, prepared real run, or offline test double.

No answer, score, optimisation win or deployment success is pre-populated here.
Test-double outputs must never be shown as model-quality evidence.
