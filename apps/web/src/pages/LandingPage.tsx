import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <main className="page page--landing">
      <nav className="landing-nav glass-surface" aria-label="Primary navigation">
        <span className="product-wordmark">OwnYourCode</span>
        <span>Repository learning, without guesswork.</span>
      </nav>
      <section className="landing-hero" aria-labelledby="landing-title">
        <p className="eyebrow">Evidence-grounded engineering practice</p>
        <h1 id="landing-title">Understand the software you build with AI.</h1>
        <p className="landing-hero__copy">
          Turn a bounded public-repository inspection into a lesson, verified practice,
          and a clearer explanation of your engineering decisions.
        </p>
        <div className="landing-hero__actions">
          <Link className="button" to="/projects/new">
            Start a project
          </Link>
          <p>Nothing is stored until a future persistence phase.</p>
        </div>
      </section>
      <section className="workflow-preview glass-surface" aria-labelledby="workflow-preview-title">
        <div>
          <p className="eyebrow">The product loop</p>
          <h2 id="workflow-preview-title">Learn {"\u2192"} Verify {"\u2192"} Defend</h2>
        </div>
        <ol>
          <li><strong>Inspect</strong><span>Bounded, deterministic repository evidence.</span></li>
          <li><strong>Learn</strong><span>An evidence-grounded architecture orientation.</span></li>
          <li><strong>Verify</strong><span>Deterministic checks on teaching fixtures.</span></li>
          <li><strong>Defend</strong><span>Explain decisions and limitations in context.</span></li>
        </ol>
      </section>
    </main>
  );
}
