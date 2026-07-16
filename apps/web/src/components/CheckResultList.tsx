type Check = { id: string; passed: boolean; message: string };

export function CheckResultList({ checks }: { checks: Check[] }) {
  return (
    <ul className="check-result-list" aria-label="Deterministic checks">
      {checks.map((check) => (
        <li className={check.passed ? "check-result-list__item--passed" : "check-result-list__item--failed"} key={check.id}>
          <strong>{check.passed ? "Passed" : "Needs work"}</strong>
          <span>{check.message}</span>
        </li>
      ))}
    </ul>
  );
}
