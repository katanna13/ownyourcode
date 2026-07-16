type StatusBadgeProps = {
  tone: "confirmed" | "current" | "limited" | "locked" | "neutral";
  children: string;
};

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>;
}
