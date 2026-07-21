import type { LucideIcon } from "lucide-react";

import type { OrbitalTone } from "@/components/orbital/OrbitalNode";

/**
 * One module/action on the Home screen — the same spec drives both the desktop
 * orbital constellation and the mobile command deck, so the two layouts stay in
 * sync from a single source (see OrbitalHome).
 */
export interface NodeSpec {
  key: string;
  icon: LucideIcon;
  label: string;
  sublabel?: string;
  tone?: OrbitalTone;
  badge?: number | string;
  active?: boolean;
  onClick: () => void;
}
