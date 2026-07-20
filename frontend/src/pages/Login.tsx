import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ArrowRight, Lock, Mail, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";

import { ApiError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex h-screen w-screen items-center justify-center overflow-hidden bg-jarvis-bg">
      <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-40" />
      <div className="absolute inset-0 bg-aurora" />

      {/* Ambient floating orbs — subtle, slow, premium motion in the background */}
      <motion.div
        className="pointer-events-none absolute left-1/4 top-1/4 h-72 w-72 rounded-full bg-jarvis-cyan/10 blur-[100px]"
        animate={{ y: [0, -24, 0], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="pointer-events-none absolute bottom-1/4 right-1/4 h-64 w-64 rounded-full bg-jarvis-violet/10 blur-[100px]"
        animate={{ y: [0, 20, 0], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="hud-panel hud-corner relative z-10 w-full max-w-sm p-8 shadow-elevated-lg"
      >
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="mb-8 flex flex-col items-center gap-3 text-center"
        >
          <div className="relative flex h-14 w-14 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 shadow-glow-sm">
            <div className="absolute inset-0 animate-pulseGlow rounded-full border border-jarvis-cyan/30" />
            <ShieldCheck className="h-7 w-7 text-jarvis-cyan" />
          </div>
          <h1 className="font-display text-2xl font-bold tracking-widest text-jarvis-text text-glow">
            J.A.R.V.I.S.
          </h1>
          <p className="text-sm text-jarvis-muted">Business Operating System — Access Console</p>
        </motion.div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          <motion.label
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.18, duration: 0.4 }}
            className="flex items-center gap-3 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-3 transition-colors duration-200 focus-within:border-jarvis-cyan/60 focus-within:shadow-glow-sm"
          >
            <Mail className="h-4 w-4 shrink-0 text-jarvis-muted" />
            <input
              type="email"
              required
              placeholder="you@business.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-transparent text-sm text-jarvis-text placeholder:text-jarvis-faint focus:outline-none"
            />
          </motion.label>

          <motion.label
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.24, duration: 0.4 }}
            className="flex items-center gap-3 rounded-xl border border-jarvis-border bg-jarvis-panel2/60 px-4 py-3 transition-colors duration-200 focus-within:border-jarvis-cyan/60 focus-within:shadow-glow-sm"
          >
            <Lock className="h-4 w-4 shrink-0 text-jarvis-muted" />
            <input
              type="password"
              required
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-transparent text-sm text-jarvis-text placeholder:text-jarvis-faint focus:outline-none"
            />
          </motion.label>

          {error && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="text-sm text-jarvis-rose"
            >
              {error}
            </motion.p>
          )}

          <motion.button
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            type="submit"
            disabled={submitting}
            className="press-scale group mt-2 flex items-center justify-center gap-2 rounded-xl border border-jarvis-cyan/50 bg-jarvis-cyan/10 py-3 text-sm font-semibold uppercase tracking-widest text-jarvis-cyan transition-all duration-200 hover:bg-jarvis-cyan/20 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-jarvis-cyan/30 border-t-jarvis-cyan" />
                Authenticating
              </>
            ) : (
              <>
                Initialize Session
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
              </>
            )}
          </motion.button>
        </form>
      </motion.div>
    </div>
  );
}
