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

import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <PromptProvider>
            <AuthProvider>
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
            </AuthProvider>
          </PromptProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
