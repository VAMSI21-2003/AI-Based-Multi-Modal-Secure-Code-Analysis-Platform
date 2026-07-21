import { useEffect, useState } from "react";
import {
  ShieldCheck, Target, Award, Bug, Flame, Sparkles, FolderGit2, Layers, GitFork, Eye, Pin, Shield,
  Trophy, Lock,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import StatCard from "../components/StatCard";
import { Spinner } from "../components/Loading";
import { getGamificationStatus, type GamificationStatus, type GamificationBadge } from "../api/client";

const ICONS: Record<string, any> = {
  "shield-check": ShieldCheck, target: Target, award: Award, bug: Bug, flame: Flame,
  sparkles: Sparkles, "folder-git": FolderGit2, layers: Layers, "git-fork": GitFork,
  eye: Eye, pin: Pin, shield: Shield,
};

export default function Gamification() {
  const [data, setData] = useState<GamificationStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    getGamificationStatus().then((d) => { if (!cancelled) setData(d); });
    return () => { cancelled = true; };
  }, []);

  if (!data) {
    return <PageShell title="Security Gamification" subtitle="Real achievements, earned from real scan history"><Spinner label="Tallying achievements..." /></PageShell>;
  }

  if (data.total_scans === 0) {
    return (
      <PageShell title="Security Gamification" subtitle="Real achievements, earned from real scan history">
        <div className="card p-10 text-center">
          <Trophy size={32} className="mx-auto text-(--text-muted) mb-3" />
          <div className="text-sm font-semibold">No scans yet</div>
          <div className="text-xs text-(--text-muted) mt-1">Run your first scan to start earning badges — every achievement here is computed from your real scan history, nothing is pre-unlocked.</div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="Security Gamification" subtitle="Every badge below is computed live from your real scan history — nothing is pre-unlocked">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
        <div className="card p-6 flex flex-col items-center justify-center text-center md:col-span-1" style={{ boxShadow: `0 0 40px -14px ${data.tier.color}` }}>
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center mb-3 border-2"
            style={{ borderColor: data.tier.color, background: `${data.tier.color}1f` }}
          >
            <Trophy size={32} style={{ color: data.tier.color }} />
          </div>
          <div className="text-xl font-bold" style={{ color: data.tier.color }}>{data.tier.name}</div>
          <div className="text-xs text-(--text-muted) mt-1">Security Tier</div>
          {data.next_tier && (
            <div className="w-full mt-4">
              <div className="flex justify-between text-[10px] text-(--text-muted) mb-1">
                <span>{data.tier.name}</span><span>{data.next_tier.name}</span>
              </div>
              <div className="h-1.5 rounded-full bg-(--surface-3) overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${data.progress_to_next}%`, background: data.next_tier.color }} />
              </div>
              <div className="text-[10px] text-(--text-muted) mt-1.5">{data.progress_to_next.toFixed(0)}% of the way to {data.next_tier.name}</div>
            </div>
          )}
        </div>

        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <StatCard label="Security Score" value={data.security_score} suffix="%" icon={Shield} accent={data.tier.color} />
          <StatCard label="Total Scans" value={data.total_scans} icon={Target} accent="var(--series-1)" />
          <StatCard label="Badges Earned" value={data.badges_earned} suffix={`/${data.badges_total}`} icon={Award} accent="var(--series-4)" />
          <StatCard label="Clean Streak" value={data.clean_streak ?? 0} icon={Sparkles} accent="var(--status-good)" />
        </div>
      </div>

      <ChartCard title="Achievements" subtitle={`${data.badges_earned} of ${data.badges_total} earned`}>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.badges.map((b) => <BadgeCard key={b.id} badge={b} />)}
        </div>
      </ChartCard>
    </PageShell>
  );
}

function BadgeCard({ badge }: { badge: GamificationBadge }) {
  const Icon = ICONS[badge.icon] ?? Award;
  const pct = badge.target > 0 ? Math.min(100, (badge.progress / badge.target) * 100) : 0;
  return (
    <div className={`rounded-xl p-4 border transition-all ${badge.earned ? "bg-(--status-good)/8 border-(--status-good)/30" : "bg-(--surface-2) border-(--border-hairline) opacity-70"}`}>
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${badge.earned ? "bg-(--status-good)/15" : "bg-(--surface-3)"}`}>
          {badge.earned ? <Icon size={18} className="text-(--status-good)" /> : <Lock size={16} className="text-(--text-muted)" />}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate">{badge.name}</div>
          <div className="text-[11px] text-(--text-muted)">{badge.earned ? "Earned" : "Locked"}</div>
        </div>
      </div>
      <div className="text-xs text-(--text-muted) mb-2">{badge.description}</div>
      {!badge.earned && (
        <div className="h-1 rounded-full bg-(--surface-3) overflow-hidden">
          <div className="h-full rounded-full bg-(--accent)" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}
