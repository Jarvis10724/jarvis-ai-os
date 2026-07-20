import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import JarvisCore from "@/components/JarvisCore";
import ConnectionLines from "@/components/orbital/ConnectionLines";
import OrbitalNode from "@/components/orbital/OrbitalNode";
import OrbitRing from "@/components/orbital/OrbitRing";
import { GLOBAL_ITEMS, SYSTEM_ITEMS, WORKSPACE_ITEMS, type NavEntry } from "@/components/Sidebar";
import { useAssistantStatus } from "@/context/AssistantStatusContext";
import { useCompany } from "@/context/CompanyContext";

function polar(cx: number, cy: number, radius: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
}

function isActive(pathname: string, item: NavEntry): boolean {
  return item.end ? pathname === item.to : pathname.startsWith(item.to);
}

/**
 * Full-screen radial navigation menu — the replacement for a traditional
 * vertical sidebar list. Every route the app has is reachable here, grouped
 * into three concentric rings around a small central Jarvis mark: System
 * (innermost), Global (middle), and the active workspace's modules
 * (outermost, only shown when a company is active). Reuses the same
 * OrbitalNode/OrbitRing/ConnectionLines primitives as the Home screen so the
 * whole shell reads as one consistent visual system.
 */
export default function RadialMenuOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCompany } = useCompany();
  const { status } = useAssistantStatus();
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !open) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [open]);

  function go(to: string) {
    navigate(to);
    onClose();
  }

  const { width, height } = size;
  const cx = width / 2;
  const cy = height / 2;
  const shortSide = Math.min(width, height) || 0;

  const systemRadius = Math.max(90, shortSide * 0.16);
  const globalRadius = Math.max(150, shortSide * 0.28);
  const workspaceRadius = Math.max(220, shortSide * 0.42);

  const workspaceItems = activeCompany ? WORKSPACE_ITEMS : [];

  const systemPositions = useMemo(
    () => SYSTEM_ITEMS.map((item, i) => ({ item, ...polar(cx, cy, systemRadius, -90 + (360 / SYSTEM_ITEMS.length) * i) })),
    [cx, cy, systemRadius]
  );
  const globalPositions = useMemo(
    () => GLOBAL_ITEMS.map((item, i) => ({ item, ...polar(cx, cy, globalRadius, -90 + (360 / GLOBAL_ITEMS.length) * i) })),
    [cx, cy, globalRadius]
  );
  const workspacePositions = useMemo(
    () =>
      workspaceItems.map((item, i) => ({
        item,
        ...polar(cx, cy, workspaceRadius, -90 + (360 / Math.max(workspaceItems.length, 1)) * i),
      })),
    [cx, cy, workspaceRadius, workspaceItems]
  );

  const ready = width > 0 && height > 0;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-jarvis-bg/85 backdrop-blur-xl"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-0 z-50"
          >
            <div ref={containerRef} className="relative h-full w-full">
              {ready && (
                <>
                  <OrbitRing diameter={workspaceRadius * 2 + 100} durationSec={100} opacity={0.08} />
                  <OrbitRing diameter={globalRadius * 2 + 80} durationSec={80} reverse opacity={0.1} />
                  <OrbitRing diameter={systemRadius * 2 + 60} durationSec={60} opacity={0.12} />

                  <ConnectionLines
                    width={width}
                    height={height}
                    origin={{ x: cx, y: cy }}
                    points={[...systemPositions, ...globalPositions, ...workspacePositions].map((p) => ({
                      x: p.x,
                      y: p.y,
                    }))}
                  />

                  <button
                    onClick={onClose}
                    className="absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-jarvis-cyan/40 bg-jarvis-panel/70 backdrop-blur-xl transition hover:border-jarvis-cyan"
                    style={{ left: cx, top: cy }}
                    title="Close (Esc)"
                  >
                    <JarvisCore state={status} size={36} />
                  </button>

                  {systemPositions.map(({ item, x, y }, i) => (
                    <OrbitalNode
                      key={item.to}
                      x={x}
                      y={y}
                      icon={item.icon}
                      label={item.label}
                      tone="violet"
                      active={isActive(location.pathname, item)}
                      delay={i * 0.03}
                      compact
                      onClick={() => go(item.to)}
                    />
                  ))}
                  {globalPositions.map(({ item, x, y }, i) => (
                    <OrbitalNode
                      key={item.to}
                      x={x}
                      y={y}
                      icon={item.icon}
                      label={item.label}
                      tone="cyan"
                      active={isActive(location.pathname, item)}
                      delay={0.1 + i * 0.03}
                      compact
                      onClick={() => go(item.to)}
                    />
                  ))}
                  {workspacePositions.map(({ item, x, y }, i) => (
                    <OrbitalNode
                      key={item.to}
                      x={x}
                      y={y}
                      icon={item.icon}
                      label={item.label}
                      tone="blue"
                      active={isActive(location.pathname, item)}
                      delay={0.2 + i * 0.03}
                      compact
                      onClick={() => go(item.to)}
                    />
                  ))}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
