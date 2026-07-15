import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <main className="page page--landing">
      <p className="eyebrow">OwnYourCode</p>
      <h1>Understand the software you build with AI.</h1>
      <p>
        A learning platform for explaining, testing, securing, and defending
        your engineering decisions.
      </p>
      <Link className="button" to="/projects/new">
        Start a project
      </Link>
    </main>
  );
}
