---
description: Probe a change before proposing — grilling over a 6-layer question tree (Experimental)
---

Probe a change before `/opsx-propose`: depth-first grilling over a 6-layer question tree, producing `openspec/changes/<name>/probe-report.md`.

Follow the openspec-probe skill. This is a free-text interview: ask exactly ONE question per message and wait for the reply — never use option-card / multiple-choice tools (e.g. AskUserQuestion) to collect answers.

Start by reading context:
```bash
openspec status --json
openspec instructions --json
```

**Input**: A change name (kebab-case) after `/opsx-probe`, OR a description to derive one from.
