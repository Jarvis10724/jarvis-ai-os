// MOCK DATA — replace with a real `business_ideas` table once this module
// is backed by persistence. This is the natural landing spot for Greener
// Capitol Solutions LLC's "Future Ventures" division.
import type { BusinessIdea } from "@/types";

export const MOCK_IDEAS: BusinessIdea[] = [
  {
    id: "idea1",
    title: "Print-on-demand outdoor gear line",
    description: "Low-overhead test of a print-on-demand storefront targeting outdoor/hiking niches.",
    stage: "validating",
    division: "Side Hustles",
    score: 6,
    notes: "Running a small ad test before committing to inventory.",
  },
  {
    id: "idea2",
    title: "Fractional COO consulting package",
    description: "Productized version of the consulting work already being done ad hoc.",
    stage: "building",
    division: "Consulting",
    score: 8,
    notes: "Two warm leads already asking for something like this.",
  },
  {
    id: "idea3",
    title: "Short-term rental — first property",
    description: "Evaluate a first STR purchase as a new investing vertical.",
    stage: "idea",
    division: "Investing",
    score: 5,
    notes: "Need to run numbers on 2-3 target markets first.",
  },
  {
    id: "idea4",
    title: "Wholesale program for Primal Penni",
    description: "Formalize wholesale pricing/terms after the first successful co-op order.",
    stage: "building",
    division: "Future Ventures",
    score: 7,
    notes: "First wholesale customer already live — this is about scaling the process.",
  },
  {
    id: "idea5",
    title: "Local tax-prep side service",
    description: "Idea to offer basic tax prep for other small business owners in the network.",
    stage: "parked",
    division: "Taxes",
    score: 3,
    notes: "Interesting but not enough bandwidth right now — revisit next year.",
  },
];

export const IDEA_STAGE_LABELS: Record<BusinessIdea["stage"], string> = {
  idea: "Idea",
  validating: "Validating",
  building: "Building",
  launched: "Launched",
  parked: "Parked",
};

export const IDEA_COLUMNS: { key: BusinessIdea["stage"]; label: string }[] = [
  { key: "idea", label: "Idea" },
  { key: "validating", label: "Validating" },
  { key: "building", label: "Building" },
  { key: "launched", label: "Launched" },
  { key: "parked", label: "Parked" },
];
