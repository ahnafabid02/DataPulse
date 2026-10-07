# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `ahnafabid02/DataPulse`.
Use the authenticated `gh` CLI. The `origin` remote identifies this repository;
use `--repo ahnafabid02/DataPulse` when operating outside the checkout.

## Conventions

- Create an issue: `gh issue create --title "..." --body-file <file>`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --json number,title,body,labels`, with filters.
- Comment: `gh issue comment <number> --body-file <file>`.
- Apply/remove labels: `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- Close: `gh issue close <number>` after recording the reason in a comment.
- Write multiline issue/comment bodies to a file; preserve actual newlines.
- Link child issues with GitHub sub-issues when supported by the installed CLI/API.
  Otherwise, put `Part of #<parent>` in the child and a task list in the parent.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub issues and PRs share numbers. Resolve an ambiguous number with
`gh pr view <number>` and fall back to `gh issue view <number>`.

## Skill operations

"Publish to the issue tracker" means create a GitHub issue.
"Fetch the relevant ticket" means read the referenced GitHub issue.

## Wayfinding

- Map: one issue labelled `wayfinder:map`, with Notes, Decisions-so-far, and Fog.
- Child: link to the map, label `wayfinder:<type>` (research/prototype/grilling/task).
- Blocking: prefer native GitHub issue dependencies. If unavailable, record
  `Blocked by: #<number>` in the child. Unblocked means every blocker is closed.
- Frontier: open children without open blockers or an assignee, in map order.
- Claim: assign the selected child to the driving developer before work.
- Resolve: comment with the answer, close the child, and add a linked summary to
  the map's Decisions-so-far.
