/**
 * The simulated GCash / Maya payout preview (completion contract X.4).
 *
 * The API returns a description, never a payout. The headline is what a
 * reviewer reads first, so it is written in the conditional and names the rail:
 * nothing on this card may read like money that has moved.
 */

export type SimulatedRail = "gcash" | "maya";

export const SIMULATED_RAILS: readonly { value: SimulatedRail; label: string }[] = [
  { value: "gcash", label: "GCash" },
  { value: "maya", label: "Maya" },
];

export type SimulationResult = {
  simulated: boolean;
  rail: SimulatedRail;
  real_rail: string;
  eligible: boolean;
  amount: string;
  minimum: string;
  short_by: string;
  currency: string;
  steps: { status: "scheduled" | "processing" | "paid"; label: string }[];
  disclaimer: string;
  as_of: string;
};

function peso(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : value;
}

export function simulationHeadline(
  result: Pick<SimulationResult, "rail" | "eligible" | "amount" | "short_by"> & { minimum?: string },
): string {
  const name = SIMULATED_RAILS.find((r) => r.value === result.rail)?.label ?? result.rail;
  if (result.eligible) {
    return `A ${peso(result.amount)} payout to ${name} would go like this`;
  }
  return `You are ${peso(result.short_by)} short of the ${peso(result.minimum ?? "300")} minimum, so no ${name} payout would be made yet`;
}
