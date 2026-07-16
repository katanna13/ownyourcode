type CodeFixtureEditorProps = {
  id: string;
  value: string;
  maximumLength: number;
  onChange: (value: string) => void;
  onReset: () => void;
  isSubmitting: boolean;
  submitLabel: string;
  submittingLabel: string;
};

export function CodeFixtureEditor({
  id,
  value,
  maximumLength,
  onChange,
  onReset,
  isSubmitting,
  submitLabel,
  submittingLabel
}: CodeFixtureEditorProps) {
  return (
    <section className="code-fixture" aria-label="Teaching fixture editor">
      <header className="code-fixture__toolbar">
        <p>Teaching fixture {"\u2014"} not repository source</p>
        <span>AST parsing only; learner code is never executed.</span>
      </header>
      <label className="field" htmlFor={id}>
        Teaching fixture code
        <textarea
          className="code-fixture__input"
          id={id}
          value={value}
          maxLength={maximumLength}
          onChange={(event) => onChange(event.target.value)}
          spellCheck={false}
        />
      </label>
      <p className="field-hint">Maximum source length: {maximumLength} characters.</p>
      <div className="code-fixture__actions">
        <button className="button button--secondary" type="button" onClick={onReset} disabled={isSubmitting}>
          Reset fixture
        </button>
        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? submittingLabel : submitLabel}
        </button>
      </div>
    </section>
  );
}
