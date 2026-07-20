import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

import SampleDataBadge from "@/components/SampleDataBadge";
import type { MetricPoint } from "@/types";

const REVENUE_TREND: MetricPoint[] = [
  { label: "Mon", value: 4200 },
  { label: "Tue", value: 4800 },
  { label: "Wed", value: 4600 },
  { label: "Thu", value: 5400 },
  { label: "Fri", value: 6100 },
  { label: "Sat", value: 5800 },
  { label: "Sun", value: 6700 },
];

const STAT_CARDS = [
  { label: "Revenue (30d)", value: "$48,230", delta: "+12.4%", up: true },
  { label: "Active Orders", value: "312", delta: "+4.1%", up: true },
  { label: "Ad Spend", value: "$3,120", delta: "-6.8%", up: false },
  { label: "New Customers", value: "87", delta: "+18.2%", up: true },
];

export default function MetricsPanel() {
  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">
          BUSINESS METRICS
        </h2>
        <div className="flex items-center gap-2">
          <SampleDataBadge />
          <span className="text-xs text-jarvis-muted">Last 7 days</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
        {STAT_CARDS.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="rounded-xl border border-jarvis-border/60 bg-jarvis-panel2/40 p-3 transition-colors duration-200 hover:border-jarvis-border-soft"
          >
            <p className="text-xs text-jarvis-muted">{stat.label}</p>
            <p className="mt-1 font-data text-lg font-semibold text-jarvis-text">{stat.value}</p>
            <p
              className={clsx(
                "mt-1 flex items-center gap-1 text-xs font-medium",
                stat.up ? "text-jarvis-emerald" : "text-jarvis-rose"
              )}
            >
              {stat.up ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : (
                <ArrowDownRight className="h-3 w-3" />
              )}
              {stat.delta}
            </p>
          </motion.div>
        ))}
      </div>

      <div className="flex-1 px-3 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={REVENUE_TREND} margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2dd4f0" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#2dd4f0" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#7c8aa3", fontSize: 11, fontFamily: "Inter" }}
            />
            <YAxis hide domain={["dataMin - 500", "dataMax + 500"]} />
            <Tooltip
              contentStyle={{
                background: "#0f1521",
                border: "1px solid #1c2333",
                borderRadius: 12,
                fontSize: 12,
                fontFamily: "Inter",
                boxShadow: "0 12px 32px -12px rgba(0,0,0,0.55)",
              }}
              labelStyle={{ color: "#eef2f9" }}
              itemStyle={{ color: "#2dd4f0" }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#2dd4f0"
              strokeWidth={2}
              fill="url(#revenueGradient)"
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
