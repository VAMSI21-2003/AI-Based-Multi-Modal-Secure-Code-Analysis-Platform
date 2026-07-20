// =============================================================================
// extension.ts -- SecureCode AI VS Code extension entry point.
//
// Talks to the EXISTING FastAPI backend only (backend/main.py + routers/*.py)
// -- no new backend code, no bundled model, no retraining. Function-boundary
// detection for "Scan Function" / CodeLens is a lightweight brace-matching
// heuristic (not a real C parser): good enough to isolate the enclosing
// function body for a quick scan, but it can be fooled by braces inside
// string/char literals or comments. Flagged here rather than silently
// pretending it's a full parser, consistent with the rest of this project's
// approach to static-analysis certainty.
// =============================================================================

import * as vscode from "vscode";
import { scanCode, getScanDetail, scanProjectFolder, frontendUrl, developerPdfUrl, type ScanResult } from "./api";

const C_LANGS = new Set(["c", "cpp"]);

let diagnostics: vscode.DiagnosticCollection;
let output: vscode.OutputChannel;
const lastScanByDoc = new Map<string, ScanResult>(); // document URI string -> last scan result

export function activate(context: vscode.ExtensionContext) {
  diagnostics = vscode.languages.createDiagnosticCollection("securecodeAi");
  output = vscode.window.createOutputChannel("SecureCode AI");
  context.subscriptions.push(diagnostics, output);

  context.subscriptions.push(
    vscode.commands.registerCommand("securecodeAi.scanFile", () => scanActiveFile(context)),
    vscode.commands.registerCommand("securecodeAi.scanFunction", () => scanFunctionAtCursor(context)),
    vscode.commands.registerCommand("securecodeAi.scanProject", (uri?: vscode.Uri) => scanProject(uri)),
    vscode.commands.registerCommand("securecodeAi.openDashboard", () => openWeb("/")),
    vscode.commands.registerCommand("securecodeAi.openExploitSimulator", () => openWeb("/simulator")),
    vscode.commands.registerCommand("securecodeAi.openExplanation", () => openLastScanPage("/explanation")),
    vscode.commands.registerCommand("securecodeAi.generateReport", () => generateReport()),
    vscode.commands.registerCommand("securecodeAi.applySuggestedFix", (docUri: vscode.Uri) => applySuggestedFix(docUri)),
  );

  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(
      [{ language: "c" }, { language: "cpp" }],
      new SecureCodeLensProvider(),
    ),
  );

  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      [{ language: "c" }, { language: "cpp" }],
      new SecureCodeActionProvider(),
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] },
    ),
  );

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      const cfg = vscode.workspace.getConfiguration("securecodeAi");
      if (cfg.get<boolean>("scanOnSave", false) && C_LANGS.has(doc.languageId)) {
        scanDocument(doc, context);
      }
    }),
  );
}

export function deactivate() {}

// ── Core scan flow ───────────────────────────────────────────────────────────

async function scanActiveFile(context: vscode.ExtensionContext) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) { vscode.window.showWarningMessage("SecureCode AI: no active editor."); return; }
  await scanDocument(editor.document, context);
}

async function scanDocument(doc: vscode.TextDocument, _context: vscode.ExtensionContext) {
  if (!C_LANGS.has(doc.languageId)) {
    vscode.window.showWarningMessage("SecureCode AI: only C/C++ files are supported.");
    return;
  }
  const code = doc.getText();
  const filename = doc.fileName.split(/[\\/]/).pop() || "file.c";
  const projectName = vscode.workspace.name || "VS Code Workspace";

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `SecureCode AI: scanning ${filename}...` },
    async () => {
      try {
        const result = await scanCode(code, filename, projectName);
        lastScanByDoc.set(doc.uri.toString(), result);
        const detail = await getScanDetail(result.id);
        applyDiagnostics(doc, detail.line_risks);

        const icon = result.verdict === "VULNERABLE" ? "$(warning)" : "$(check)";
        const choice = await vscode.window.showInformationMessage(
          `${icon} ${result.verdict} — ${result.risk_level} (${result.vuln_probability.toFixed(1)}% probability, ${result.confidence.toFixed(1)}% confidence, ${result.model_used})`,
          "Open Full Analysis", "Open Dashboard",
        );
        if (choice === "Open Full Analysis") openWeb(`/analysis?scan=${result.id}`);
        if (choice === "Open Dashboard") openWeb("/");
      } catch (e) {
        vscode.window.showErrorMessage(`SecureCode AI: ${e instanceof Error ? e.message : String(e)}`);
        output.appendLine(String(e));
      }
    },
  );
}

async function scanFunctionAtCursor(context: vscode.ExtensionContext) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) { vscode.window.showWarningMessage("SecureCode AI: no active editor."); return; }
  if (!C_LANGS.has(editor.document.languageId)) {
    vscode.window.showWarningMessage("SecureCode AI: only C/C++ files are supported.");
    return;
  }
  const range = findEnclosingFunction(editor.document, editor.selection.active.line);
  if (!range) {
    vscode.window.showWarningMessage("SecureCode AI: could not find an enclosing function at the cursor (heuristic brace-matching found no match) — falling back to Scan File.");
    await scanDocument(editor.document, context);
    return;
  }
  const snippet = editor.document.getText(range);
  const filename = `${editor.document.fileName.split(/[\\/]/).pop()}#function-at-line-${range.start.line + 1}`;
  const projectName = vscode.workspace.name || "VS Code Workspace";

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "SecureCode AI: scanning function..." },
    async () => {
      try {
        const result = await scanCode(snippet, filename, projectName);
        lastScanByDoc.set(editor.document.uri.toString(), result);
        const icon = result.verdict === "VULNERABLE" ? "$(warning)" : "$(check)";
        const choice = await vscode.window.showInformationMessage(
          `${icon} Function: ${result.verdict} — ${result.risk_level} (${result.vuln_probability.toFixed(1)}% probability)`,
          "Open Full Analysis",
        );
        if (choice === "Open Full Analysis") openWeb(`/analysis?scan=${result.id}`);
      } catch (e) {
        vscode.window.showErrorMessage(`SecureCode AI: ${e instanceof Error ? e.message : String(e)}`);
      }
    },
  );
}

async function scanProject(uri?: vscode.Uri) {
  const folder = uri ?? vscode.workspace.workspaceFolders?.[0]?.uri;
  if (!folder) { vscode.window.showWarningMessage("SecureCode AI: no folder selected/open."); return; }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `SecureCode AI: scanning project ${folder.fsPath}...` },
    async () => {
      try {
        const pattern = new vscode.RelativePattern(folder, "**/*.{c,h,cpp,cc,cxx,hpp}");
        const uris = await vscode.workspace.findFiles(pattern, "**/node_modules/**", 200);
        if (uris.length === 0) {
          vscode.window.showWarningMessage("SecureCode AI: no .c/.cpp/.h files found in this folder.");
          return;
        }
        const files: { name: string; content: string }[] = [];
        for (const u of uris) {
          const bytes = await vscode.workspace.fs.readFile(u);
          files.push({ name: vscode.workspace.asRelativePath(u, false), content: Buffer.from(bytes).toString("utf8") });
        }
        const projectName = vscode.workspace.name || folder.fsPath.split(/[\\/]/).pop() || "Project";
        const result = await scanProjectFolder(files, projectName);
        const choice = await vscode.window.showInformationMessage(
          `SecureCode AI: scanned ${result.total_files_scanned} file(s) — ${result.vulnerable_count} vulnerable, ${result.safe_count} safe.`,
          "Open Project Dashboard",
        );
        if (choice === "Open Project Dashboard") openWeb(`/project-scanner?batch=${result.batch_id}`);
      } catch (e) {
        vscode.window.showErrorMessage(`SecureCode AI: ${e instanceof Error ? e.message : String(e)}`);
      }
    },
  );
}

async function generateReport() {
  const last = [...lastScanByDoc.values()].pop();
  if (!last) { vscode.window.showWarningMessage("SecureCode AI: no scan yet in this session — run Scan File first."); return; }
  vscode.env.openExternal(vscode.Uri.parse(developerPdfUrl(last.id)));
}

async function applySuggestedFix(docUri: vscode.Uri) {
  const last = lastScanByDoc.get(docUri.toString());
  if (!last) { vscode.window.showWarningMessage("SecureCode AI: run Scan File first so a rewrite can be computed."); return; }
  const detail = await getScanDetail(last.id);
  if (!detail.suggested_rewrite.changed) {
    vscode.window.showInformationMessage("SecureCode AI: no automatic rewrite rule matched this file.");
    return;
  }
  const doc = await vscode.workspace.openTextDocument(docUri);
  const editor = await vscode.window.showTextDocument(doc);
  const fullRange = new vscode.Range(doc.positionAt(0), doc.positionAt(doc.getText().length));
  await editor.edit((builder) => builder.replace(fullRange, detail.suggested_rewrite.rewritten_code));
  vscode.window.showInformationMessage(`SecureCode AI: applied ${detail.suggested_rewrite.changes.length} rule-based fix(es). Review before committing.`);
}

function openWeb(path: string) {
  vscode.env.openExternal(vscode.Uri.parse(`${frontendUrl()}${path}`));
}

function openLastScanPage(path: string) {
  const last = [...lastScanByDoc.values()].pop();
  if (!last) { vscode.window.showWarningMessage("SecureCode AI: no scan yet in this session — run Scan File first."); return; }
  openWeb(`${path}?scan=${last.id}`);
}

// ── Diagnostics ───────────────────────────────────────────────────────────────

function applyDiagnostics(doc: vscode.TextDocument, lineRisks: { line: number; severity: number; reasons: string[]; cwe: string[] }[]) {
  const items: vscode.Diagnostic[] = lineRisks.map((lr) => {
    const lineIdx = Math.max(0, Math.min(doc.lineCount - 1, lr.line - 1));
    const lineText = doc.lineAt(lineIdx).text;
    const range = new vscode.Range(lineIdx, 0, lineIdx, lineText.length);
    const severity = lr.severity >= 3 ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning;
    const cweTxt = lr.cwe.length > 0 ? ` [${lr.cwe.join(", ")}]` : "";
    const diag = new vscode.Diagnostic(range, `SecureCode AI: ${lr.reasons.join("; ")}${cweTxt}`, severity);
    diag.source = "SecureCode AI";
    diag.code = "securecode-ai-finding";
    return diag;
  });
  diagnostics.set(doc.uri, items);
}

// ── CodeLens ──────────────────────────────────────────────────────────────────

const FUNC_SIGNATURE_RE = /^[A-Za-z_][\w\s*]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$/;

class SecureCodeLensProvider implements vscode.CodeLensProvider {
  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const lenses: vscode.CodeLens[] = [];
    if (document.lineCount > 0) {
      lenses.push(new vscode.CodeLens(new vscode.Range(0, 0, 0, 0), {
        title: "$(shield) SecureCode AI: Scan File",
        command: "securecodeAi.scanFile",
      }));
    }
    for (let i = 0; i < document.lineCount; i++) {
      const text = document.lineAt(i).text;
      if (FUNC_SIGNATURE_RE.test(text.trim()) && text.includes("(") && !text.trim().endsWith(";")) {
        lenses.push(new vscode.CodeLens(new vscode.Range(i, 0, i, 0), {
          title: "$(shield) Scan this function",
          command: "securecodeAi.scanFunction",
        }));
      }
    }
    return lenses;
  }
}

// ── Quick Fix ─────────────────────────────────────────────────────────────────

class SecureCodeActionProvider implements vscode.CodeActionProvider {
  provideCodeActions(document: vscode.TextDocument, _range: vscode.Range, ctx: vscode.CodeActionContext): vscode.CodeAction[] {
    const relevant = ctx.diagnostics.filter((d) => d.source === "SecureCode AI");
    if (relevant.length === 0) return [];
    const action = new vscode.CodeAction("SecureCode AI: Apply suggested secure rewrite", vscode.CodeActionKind.QuickFix);
    action.command = { command: "securecodeAi.applySuggestedFix", title: "Apply suggested secure rewrite", arguments: [document.uri] };
    action.diagnostics = relevant;
    return [action];
  }
}

// ── Heuristic function-boundary detection (brace matching, not a real parser) ─

function findEnclosingFunction(doc: vscode.TextDocument, cursorLine: number): vscode.Range | null {
  let startLine = -1;
  for (let i = cursorLine; i >= 0; i--) {
    const text = doc.lineAt(i).text;
    if (FUNC_SIGNATURE_RE.test(text.trim())) { startLine = i; break; }
  }
  if (startLine === -1) return null;

  let depth = 0;
  let seenOpenBrace = false;
  for (let i = startLine; i < doc.lineCount; i++) {
    const text = doc.lineAt(i).text;
    for (const ch of text) {
      if (ch === "{") { depth++; seenOpenBrace = true; }
      else if (ch === "}") { depth--; }
    }
    if (seenOpenBrace && depth <= 0) {
      return new vscode.Range(startLine, 0, i, doc.lineAt(i).text.length);
    }
  }
  return null;
}
