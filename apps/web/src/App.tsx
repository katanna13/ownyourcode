import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { RequireSession } from "./components/RequireSession";
import { LandingPage } from "./pages/LandingPage";
import { AppProjectWorkspacePage } from "./pages/AppProjectWorkspacePage";
import { CreateProjectPage } from "./pages/CreateProjectPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { ProjectsDashboardPage } from "./pages/ProjectsDashboardPage";
import { ProjectWorkspacePage } from "./pages/ProjectWorkspacePage";
import { SignInPage } from "./pages/SignInPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/projects/new" element={<NewProjectPage />} />
      <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
      <Route path="/sign-in/*" element={<SignInPage />} />
      <Route path="/app" element={<RequireSession><AppShell /></RequireSession>}>
        <Route index element={<Navigate to="projects" replace />} />
        <Route path="projects" element={<ProjectsDashboardPage />} />
        <Route path="projects/new" element={<CreateProjectPage />} />
        <Route path="projects/:projectId" element={<AppProjectWorkspacePage />} />
      </Route>
    </Routes>
  );
}
