import "server-only";

import { apiFetch } from "./api/client";

/**
 * Membership tiers (ADR-012). These are *assigned status levels*, not purchased
 * plans — there is no checkout anywhere in this flow. A tier controls two things:
 * `revenue_share_bps`, the reviewer's cut of affiliate revenue in basis points,
 * and `payout_priority`, the order payouts are scheduled in.
 *
 * Tier config is DB-managed and moderator-editable, so this page reads it live
 * rather than hardcoding the numbers — the M2 revenue split and M3 payout
 * scheduler read the same rows.
 */

export type Tier = {
  id: string;
  code: "special" | "founding" | "standard";
  name: string;
  description: string | null;
  revenue_share_bps: number;
  payout_priority: number;
  benefits: Record<string, unknown> | null;
  is_active: boolean;
};

/**
 * The public tier table, ordered most-generous first so the page reads as a
 * ladder. Returns [] if the backend is unreachable — the page renders its
 * explanatory copy either way rather than erroring out.
 */
export async function getTiers(): Promise<Tier[]> {
  try {
    const tiers = await apiFetch<Tier[]>("/api/v1/membership-tiers");
    return tiers
      .filter((t) => t.is_active)
      .sort((a, b) => b.revenue_share_bps - a.revenue_share_bps);
  } catch {
    return [];
  }
}

/** 7500 bps → "75%". Basis points are integers; format, never round for math. */
export function bpsToPercent(bps: number): string {
  const pct = bps / 100;
  return `${Number.isInteger(pct) ? pct : pct.toFixed(2)}%`;
}

/** Human label for the payout-priority integer (lower runs earlier). */
export function priorityLabel(priority: number): string {
  if (priority <= 0) return "First in line";
  if (priority === 1) return "Early";
  return "Standard queue";
}

/**
 * The benefits JSONB is admin-editable free-form, so it can hold anything.
 * Render only string/number/boolean leaves as "Key: value" bullets and drop
 * nested structures rather than dumping JSON at the reader.
 */
export function benefitLines(benefits: Record<string, unknown> | null): string[] {
  if (!benefits) return [];
  const lines: string[] = [];
  for (const [key, value] of Object.entries(benefits)) {
    const label = key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
    if (typeof value === "boolean") {
      if (value) lines.push(label);
    } else if (typeof value === "string" || typeof value === "number") {
      lines.push(`${label}: ${value}`);
    }
  }
  return lines;
}
