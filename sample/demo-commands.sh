# Commands used in the demo, to show on screen. Copy and paste them one at a time.
# Run from sample/ with the venv active and FOUNDRY_PROJECT_ENDPOINT exported.
# BILLABLE = calls models or deploys. Slow ones are run before the talk.
echo "Copy commands from this file one at a time; don't run it as a script." && exit 1

# --- Deploy the app only ---
azd deploy purchasing-advice-demo

# --- Demo 2: run the starting agent (live) ---
azd ai agent invoke purchasing-advice-demo --new-session --new-conversation \
  'Today is 13 October 2026. Can I book a team dinner for six this Thursday? It'\''s about $540, and my manager'\''s approved it.'

azd ai agent invoke purchasing-advice-demo 'Yes, there will be wine.'   # same session

azd ai agent invoke purchasing-advice-demo --new-session --new-conversation \
  'Today is 21 October 2026. I'\''m Marcus Webb in Engineering. Can I buy a video-conferencing system for the boardroom for $6,800? I'\''ve got two supplier quotes.'

# --- Demo 4: evaluate (BILLABLE, ~10 minutes) ---
python evaluation/evaluate.py --dry-run                          # prints the request only
EVAL_DATASET=evaluation/datasets/approvers-holdout.jsonl python evaluation/evaluate.py --wait

# Compare runs question by question
python evaluation/compare_runs.py --list
python evaluation/compare_runs.py --a OLD_RUN_1 OLD_RUN_2 --b NEW_RUN_1 NEW_RUN_2

# --- Demo 5: optimise (BILLABLE, ~1 hour) ---
azd ai agent optimize --config evaluation/optimize.yaml --no-prompt

# --- Demo 6: fact check a candidate (no Azure) ---
python evaluation/check_prompt_facts.py --baseline agent/.agent_configs/baseline \
  --candidate evaluation/candidates/optimiser-0.691 --data agent/data/*.json

# --- CI/CD: manual workflow runs (BILLABLE) ---
gh workflow run agent-main.yml --ref BRANCH -f mode=holdout     # check a PR branch, no release
gh workflow run agent-main.yml --ref main -f mode=release       # promote main, with approvals

# === Preparation, not shown on stage ===

# Open a PR from a saved candidate (branch, folder, title, body)
open_pr() {
  git switch main && git pull --ff-only && git switch -c "$1" || return
  cp "evaluation/candidates/$2/"{instructions.md,metadata.yaml,tools.json} \
    agent/.agent_configs/baseline/ || return
  git add agent/.agent_configs/baseline || return
  git commit -m "$3" && git push -u origin "$1" && gh pr create --title "$3" --body "$4"
}
open_pr demo/reviewed-candidate reviewed "Review the evidence-led purchasing improvement" \
  "Saved manually improved configuration, not an optimiser-generated winner."
open_pr demo/no-grounding regressed "Demo: no tools, same answer to every request" \
  "Deliberately bad negative control. Observe the evaluation failure; do not merge."
git switch main

# Register changed judges (then refresh the affected baselines)
python evaluation/evaluate.py --update-evaluators --register-only

# Create the drift baseline without releasing (BILLABLE)
gh workflow run agent-main.yml --ref main -f mode=baseline-drift

# Rebuild the roster and test sets, or the policy embeddings
python evaluation/generate_approver_data.py
python agent/build_embeddings.py          # --check verifies them without Azure

