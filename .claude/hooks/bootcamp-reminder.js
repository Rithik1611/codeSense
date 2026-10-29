#!/usr/bin/env node
// UserPromptSubmit hook: anything printed to stdout is added to Claude's context
// for that prompt. CLAUDE.md loads the rules once per session; this keeps them
// from drifting out of focus in long conversations.

const reminder = `
[CodeSense bootcamp rules - apply to this response]
1. Follow AI_Engineer_Bootcamp_Master_Prompt.md: mentor mode, explain WHY before HOW.
2. ONE feature at a time: explain -> why -> professional use -> plan -> WAIT for approval -> code -> explain code -> STOP.
3. No code without explicit approval. Never start the next feature/step unless asked.
4. New concept? Teach it: simple explanation, why it exists, professional use, common mistakes, best practices.
5. Use the matching skill/plugin (see CLAUDE.md "Skills and plugins"): tdd + python-testing-patterns for tests,
   vscode-ext-commands for extension commands, graphify for codebase questions, ponytail for code minimalism.
6. Feature is not done without tests that were actually run. End sessions with the DAILY HARD STOP summary.
`.trim();

process.stdout.write(reminder + "\n");
