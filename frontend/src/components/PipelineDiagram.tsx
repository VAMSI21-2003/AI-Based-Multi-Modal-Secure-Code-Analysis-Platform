import {
  FileCode2, Hash, Cpu, Network, BarChart3, Combine, TreePine, Target, BookOpen, Wand2, ChevronRight,
} from "lucide-react";

const STAGES = [
  { label: "Source Code", icon: FileCode2, color: "#3987e5" },
  { label: "Tokenizer", icon: Hash, color: "#199e70" },
  { label: "CodeBERT", icon: Cpu, color: "#9085e9" },
  { label: "AST", icon: Network, color: "#d55181" },
  { label: "Software Metrics", icon: BarChart3, color: "#c98500" },
  { label: "Feature Fusion", icon: Combine, color: "#d95926" },
  { label: "XGBoost", icon: TreePine, color: "#3987e5" },
  { label: "Prediction", icon: Target, color: "#d03b3b" },
  { label: "Knowledge Base", icon: BookOpen, color: "#199e70" },
  { label: "Recommendations", icon: Wand2, color: "#0ca30c" },
];

export default function PipelineDiagram({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-y-6">
      {STAGES.map((stage, i) => (
        <div key={stage.label} className="flex items-center">
          <div className="flex flex-col items-center gap-2 px-1">
            <div
              className={`rounded-xl flex items-center justify-center shrink-0 ${compact ? "w-11 h-11" : "w-14 h-14"}`}
              style={{ background: `${stage.color}1f`, border: `1.5px solid ${stage.color}55`, boxShadow: `0 0 20px ${stage.color}22` }}
            >
              <stage.icon size={compact ? 18 : 22} style={{ color: stage.color }} />
            </div>
            <span className={`text-center font-medium text-(--text-secondary) whitespace-nowrap ${compact ? "text-[10px]" : "text-xs"}`}>
              {stage.label}
            </span>
          </div>

          {i < STAGES.length - 1 && (
            <div className={`relative ${compact ? "w-6 mx-0.5" : "w-10 mx-1"} h-[2px] bg-(--border-hairline-strong) rounded-full self-start mt-5`}>
              <span
                className="flow-dot-x absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full"
                style={{ background: stage.color, boxShadow: `0 0 6px ${stage.color}`, animationDelay: `${i * 0.15}s` }}
              />
              <ChevronRight size={12} className="absolute -right-2.5 top-1/2 -translate-y-1/2 text-(--text-muted)" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
