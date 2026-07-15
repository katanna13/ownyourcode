import { Route, Routes } from "react-router-dom";

import { LandingPage } from "./pages/LandingPage";
import { NewProjectPage } from "./pages/NewProjectPage";
import { ProjectWorkspacePage } from "./pages/ProjectWorkspacePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/projects/new" element={<NewProjectPage />} />
      <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
    </Routes>
  );
}
