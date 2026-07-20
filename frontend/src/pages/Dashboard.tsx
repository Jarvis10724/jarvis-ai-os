import OrbitalHome from "@/components/orbital/OrbitalHome";

// The Home screen — the AI Core and its orbiting modules. Every other page
// in the app (CRM, Financials, SOP Library, ...) is unchanged; this is the
// one screen that became the immersive operating-system shell.
export default function Dashboard() {
  return (
    <main className="relative h-full min-h-0 flex-1 overflow-hidden">
      <OrbitalHome />
    </main>
  );
}
