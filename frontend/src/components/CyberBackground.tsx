export default function CyberBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div className="cyber-grid" />
      <div className="cyber-orb-1" style={{ top: "-10%", left: "10%" }} />
      <div className="cyber-orb-2" style={{ top: "10%", right: "5%" }} />
    </div>
  );
}
