// MOCK DATA — replace with a real `crm_contacts` table + endpoints once
// this module goes live. Shape mirrors what that table should look like.
import type { CrmContact } from "@/types";

export const MOCK_CONTACTS: CrmContact[] = [
  {
    id: "c1",
    name: "Dana Whitfield",
    company: "Whitfield & Co.",
    email: "dana@whitfieldco.com",
    phone: "(555) 201-4432",
    stage: "proposal",
    value: 8500,
    lastContact: "2026-07-14",
    notes: "Wants a 6-month consulting retainer for ops cleanup.",
  },
  {
    id: "c2",
    name: "Marcus Ibe",
    company: "Ibe Logistics",
    email: "marcus@ibelogistics.com",
    phone: "(555) 340-9981",
    stage: "contacted",
    value: 4200,
    lastContact: "2026-07-10",
    notes: "Follow up after his Q3 planning is done.",
  },
  {
    id: "c3",
    name: "Priya Nair",
    company: null,
    email: "priya.nair@gmail.com",
    phone: null,
    stage: "lead",
    value: null,
    lastContact: null,
    notes: "Inbound from a referral, hasn't been contacted yet.",
  },
  {
    id: "c4",
    name: "Retail Buyer — Coastal Market Co-op",
    company: "Coastal Market Co-op",
    email: "buying@coastalmarket.co",
    phone: "(555) 902-1187",
    stage: "won",
    value: 3100,
    lastContact: "2026-06-28",
    notes: "First wholesale order for Primal Penni Collective — recurring monthly.",
  },
  {
    id: "c5",
    name: "Tom Reyes",
    company: "Reyes Manufacturing",
    email: "tom@reyesmfg.com",
    phone: "(555) 774-2200",
    stage: "lost",
    value: 12000,
    lastContact: "2026-05-30",
    notes: "Went with a lower-cost overseas manufacturer instead.",
  },
];

export const CRM_STAGE_LABELS: Record<CrmContact["stage"], string> = {
  lead: "Lead",
  contacted: "Contacted",
  proposal: "Proposal",
  won: "Won",
  lost: "Lost",
};
