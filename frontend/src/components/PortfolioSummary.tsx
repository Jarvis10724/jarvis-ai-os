import { Link } from "react-router-dom";
import { motion } from "framer-motion";

import { useCompany } from "@/context/CompanyContext";

// Real companies from the multi-company workspace — no mock/demo ventures
// here anymore. "Profile set up" is a genuine computed percentage (how many
// of a company's sections have moved past "not started"), not a fabricated
// business metric.
export default function PortfolioSummary() {
  const { companies, loading, setActiveCompanyId } = useCompany();

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
          PORTFOLIO SUMMARY
        </h2>
        <span className="text-xs text-jarvis-muted">
          {companies.length} {companies.length === 1 ? "company" : "companies"}
        </span>
      </div>

      {loading ? (
        <div className="flex-1 space-y-3 p-5">
          {[0, 1].map((i) => (
            <div key={i} className="skeleton h-16 w-full" />
          ))}
        </div>
      ) : companies.length === 0 ? (
        <div className="flex flex-1 items-center justify-center px-5 text-center text-xs text-jarvis-muted">
          No companies yet — use the switcher in the sidebar to create one.
        </div>
      ) : (
        <ul className="flex-1 space-y-3 overflow-y-auto p-5">
          {companies.map((company, i) => {
            const sectionValues = Object.values(company.sections);
            const started = sectionValues.filter((s) => s.status !== "not_started").length;
            const percent = sectionValues.length
              ? Math.round((started / sectionValues.length) * 100)
              : 0;

            return (
              <motion.li
                key={company.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.06 * i, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                <Link
                  to="/company"
                  onClick={() => setActiveCompanyId(company.id)}
                  className="block rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3 transition-all duration-200 hover:border-jarvis-cyan/40 hover:bg-jarvis-cyan/5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-jarvis-text">{company.name}</p>
                      <p className="text-xs text-jarvis-muted">
                        {company.industry ?? "No industry set"}
                      </p>
                    </div>
                    <span className="font-data shrink-0 rounded-full border border-jarvis-cyan/40 bg-jarvis-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-jarvis-cyan">
                      {percent}% set up
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-jarvis-border/50">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-jarvis-cyan to-jarvis-blue"
                      initial={{ width: 0 }}
                      animate={{ width: `${percent}%` }}
                      transition={{ duration: 0.6, delay: 0.1 + 0.06 * i, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                </Link>
              </motion.li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
