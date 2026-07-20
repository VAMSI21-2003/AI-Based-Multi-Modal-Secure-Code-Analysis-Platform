# SecureCode AI — VS Code Extension

A real VS Code extension that talks to the existing SecureCode AI FastAPI
backend (`backend/main.py`). It adds no new backend code, no bundled model,
and does not retrain anything — every action here is a thin client around
endpoints that already exist and are used by the web dashboard.

## Features

- **Scan File** — right-click in a `.c`/`.cpp` editor, or run the command.
- **Scan Function at Cursor** — heuristically finds the enclosing function
  (brace-matching from the nearest signature line above the cursor, not a
  real parser — see "Known limitations" below) and scans just that snippet.
- **Scan Project** — right-click a folder in the Explorer, or run the
  command with a workspace open. Uploads every `.c/.h/.cpp/.cc/.cxx/.hpp`
  file (capped at 200) to the existing batch-scan endpoint.
- **Inline diagnostics** — every line-level finding from the backend's
  heuristic scanner becomes a real VS Code diagnostic: red squiggle
  (Error) for high/critical severity, yellow squiggle (Warning) for
  low/medium, with the matched CWE id(s) in the message.
- **CodeLens** — a "Scan this function" lens above every detected function
  signature, plus a "Scan File" lens at the top of the file.
- **Quick Fix** — when a SecureCode AI diagnostic is selected, the lightbulb
  offers "Apply suggested secure rewrite", which calls the same rule-based
  rewrite endpoint used by Auto Patch Generator / Code Diff Viewer in the
  web app and replaces the file contents (review before committing — it's
  a best-effort pattern rewrite, not a guarantee of correctness).
- **Open Dashboard / Explanation / Exploit Simulator** — one-click commands
  that open the relevant page of the full web platform in your browser,
  pre-linked to the most recent scan where applicable.
- **Generate Report** — opens the Developer PDF report for the most recent
  scan in this VS Code session.

## Setup

```bash
cd vscode-extension
npm install
npm run compile        # or: npm run watch
```

Then open this `vscode-extension/` folder in VS Code and press **F5** to
launch an Extension Development Host with the extension loaded. Open a
`.c`/`.cpp` file in that new window and try **Scan File** from the
right-click menu or the Command Palette (`Ctrl+Shift+P` → "SecureCode AI").

The backend must be running first:

```bash
cd backend
uvicorn main:app --port 8000
```

And ideally the web dashboard too (for the "Open Dashboard" / "Open
Explanation" links):

```bash
cd frontend
npm run dev
```

Both URLs are configurable in VS Code settings under `securecodeAi.*` if
you're running the backend/frontend on non-default ports or a remote host.

## Known limitations

- **Function-boundary detection is a heuristic, not a real C parser.** It
  finds the nearest line above the cursor that looks like a function
  signature, then brace-matches forward. It can be fooled by braces inside
  string/char literals or comments, and by unusual formatting (e.g. the
  opening `{` on its own line far from the signature is fine; a brace
  hidden inside a macro is not). The web app's own AST-based analysis
  (tree-sitter) does not have this limitation — "Scan Function" here is a
  convenience for quick iteration, not a replacement for the full file scan.
- **This extension was built and TypeScript-compiled (`tsc -p ./` passes
  with zero errors) but has not been interactively exercised inside a real
  VS Code Extension Development Host window** — the sandboxed environment
  this was built in has no VS Code GUI to launch. The command wiring,
  diagnostic/CodeLens/CodeAction provider registration, and all backend
  calls were verified by direct code review and by confirming every backend
  endpoint they call (`/api/scan/code`, `/api/scan/{id}/detail`,
  `/api/scan/batch`, `/api/export/pdf/developer/{id}`) responds correctly
  via curl. Press F5 locally to do the first interactive pass.
- Requires VS Code ^1.85 (for global `fetch` in the extension host, avoiding
  an extra HTTP client dependency).
