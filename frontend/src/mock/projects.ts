// MOCK DATA — replace with `api.listProjects(companyId)` once the Project
// Manager module is backed by real persistence (the `projects`/`tasks`
// tables already exist; this module just needs its own endpoints).
import type { ProjectBoardItem } from "@/types";

export const MOCK_PROJECTS: ProjectBoardItem[] = [
  {
    id: "p1",
    title: "Rebuild Shopify theme",
    description: "New storefront theme post-recovery, mobile-first.",
    status: "backlog",
    division: null,
    dueDate: "2026-08-01",
    assignee: "Nick",
  },
  {
    id: "p2",
    title: "Q3 consulting retainer proposals",
    description: "Draft proposals for 3 warm consulting leads.",
    status: "in_progress",
    division: "Consulting",
    dueDate: "2026-07-25",
    assignee: "Nick",
  },
  {
    id: "p3",
    title: "Side hustle: print-on-demand test run",
    description: "Validate a print-on-demand storefront as a low-lift side hustle.",
    status: "backlog",
    division: "Side Hustles",
    dueDate: null,
    assignee: null,
  },
  {
    id: "p4",
    title: "Amazon FBA listing draft",
    description: "First Amazon listing for the flagship Primal Penni product.",
    status: "review",
    division: null,
    dueDate: "2026-07-30",
    assignee: "Wife",
  },
  {
    id: "p5",
    title: "2026 tax organization",
    description: "Gather receipts and mileage logs for quarterly estimated taxes.",
    status: "in_progress",
    division: "Taxes",
    dueDate: "2026-07-31",
    assignee: "Nick",
  },
  {
    id: "p6",
    title: "New SOPs for order fulfillment",
    description: "Document the current fulfillment process before handing off to a VA.",
    status: "done",
    division: null,
    dueDate: "2026-07-10",
    assignee: "Nick",
  },
];

export const PROJECT_COLUMNS: { key: ProjectBoardItem["status"]; label: string }[] = [
  { key: "backlog", label: "Backlog" },
  { key: "in_progress", label: "In Progress" },
  { key: "review", label: "Review" },
  { key: "done", label: "Done" },
];
