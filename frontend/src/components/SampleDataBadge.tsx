import { FlaskConical } from "lucide-react";

export default function SampleDataBadge({ label = "Sample" }: { label?: string }) {
  return (
    <span
      title="Not connected to a real data source — for layout/demo purposes only."
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-jarvis-amber/30 bg-jarvis-amber/[0.08] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-jarvis-amber/90"
    >
      <FlaskConical className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}
