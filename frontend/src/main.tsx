import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import { AssistantStatusProvider } from "@/context/AssistantStatusContext";
import { AuthProvider } from "@/context/AuthContext";
import { CompanyProvider } from "@/context/CompanyContext";
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
                <AssistantStatusProvider>
                  <App />
                </AssistantStatusProvider>
              </CompanyProvider>
            </AuthProvider>
          </PromptProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
