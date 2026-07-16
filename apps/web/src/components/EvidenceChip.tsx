type EvidenceChipProps = {
  id: string;
  label: string;
};

export function EvidenceChip({ id, label }: EvidenceChipProps) {
  return (
    <li className="evidence-chip">
      <span className="evidence-chip__label">{label}</span>
      <code className="evidence-chip__id">{id}</code>
    </li>
  );
}
