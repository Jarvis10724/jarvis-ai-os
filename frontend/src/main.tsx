import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "framer-motion";

import App from "@/App";
import { AssistantStatusProvider } from "@/context/AssistantStatusContext";
import { AuthProvider } from "@/context/AuthContext";
import { CompanyProvider } from "@/context/CompanyContext";
import { ProjectProvider } from "@/context/ProjectContext";
import { PromptProvider } from "@/context/PromptContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { ToastProvider } from "@/context/ToastContext";

import { SyncProvider } from "@/context/SyncContext";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <PromptProvider>
            <AuthProvider>
              {/* One connection to the backend's change feed, shared by the
                  whole app. Inside AuthProvider because it needs the session;
                  outside the workspace providers because a workspace switch
                  must not tear the stream down. */}
              <SyncProvider>
                <CompanyProvider>
                <ProjectProvider>
                  <AssistantStatusProvider>
                    {/* Every framer-motion animation honors the OS
                        "reduce motion" setting automatically. */}
                    <MotionConfig reducedMotion="user">
                      <App />
                    </MotionConfig>
                  </AssistantStatusProvider>
                </ProjectProvider>
                </CompanyProvider>
              </SyncProvider>
            </AuthProvider>
          </PromptProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
