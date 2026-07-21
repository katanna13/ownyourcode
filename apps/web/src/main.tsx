import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ClerkProviderBoundary } from "./auth/ClerkProviderBoundary";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ClerkProviderBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ClerkProviderBoundary>
  </StrictMode>
);
