import Editor from "@monaco-editor/react";
import { useState } from "react";
import { Sun, Moon } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  height?: string | number;
  readOnly?: boolean;
  highlightLines?: { line: number; color: string }[];
}

export default function CodeEditor({ value, onChange, height = 380, readOnly = false, highlightLines }: Props) {
  const [theme, setTheme] = useState<"vs-dark" | "light">("vs-dark");

  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <div className="flex items-center justify-between px-3 py-1.5 bg-(--surface-3) border-b border-(--border-hairline)">
        <div className="flex items-center gap-1.5 text-xs text-(--text-muted)">
          <span className="w-2.5 h-2.5 rounded-full bg-[#ec835a]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#fab219]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#0ca30c]" />
          <span className="ml-2 mono">source.c</span>
        </div>
        <button
          onClick={() => setTheme((t) => (t === "vs-dark" ? "light" : "vs-dark"))}
          className="flex items-center gap-1 text-[11px] text-(--text-muted) hover:text-(--text-primary) transition-colors px-2 py-1 rounded-md hover:bg-(--surface-2) focus-ring"
          title="Toggle editor theme"
        >
          {theme === "vs-dark" ? <Sun size={12} /> : <Moon size={12} />}
          {theme === "vs-dark" ? "Light" : "Dark"}
        </button>
      </div>
      <Editor
        height={height}
        language="c"
        theme={theme}
        value={value}
        onChange={(v) => onChange(v ?? "")}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: "ui-monospace, Consolas, monospace",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          autoIndent: "full",
          renderLineHighlight: "all",
          padding: { top: 12 },
          glyphMargin: !!highlightLines?.length,
        }}
      />
    </div>
  );
}
