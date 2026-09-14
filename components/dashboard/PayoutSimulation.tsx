"use client";

import { useState } from "react";

import {
  SIMULATED_RAILS,
  simulationHeadline,
  type SimulatedRail,
  type SimulationResult,
} from "./payout-simulation-model";

/**
 * "Preview a GCash or Maya payout" — a simulation, and it says so first.
 *
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY. The Transfer frame
 * draws a single PayPal flow. The completion contract asks for GCash and Maya
 * *simulated* (PRD FR-6: they wait on permits and registration), so this card
 * sits below the real controls, dashed and labelled "Simulation", and the API
 * behind it cannot move money (`payout_simulation`, tested on its source).
 */
export function PayoutSimulation() {
  const [rail, setRail] = useState<SimulatedRail | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function preview(next: SimulatedRail) {
    setRail(next);
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/payouts/simulate?rail=${next}`);
      if (!res.ok) {
        setResult(null);
        setError("Couldn't run the simulation.");
        return;
      }
      setResult((await res.json()) as SimulationResult);
    } catch {
      setResult(null);
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="simulation-heading"
      className="mt-8 rounded-[var(--radius-md)] border border-dashed border-[var(--line-hairline-30)] p-4"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--accent-trust)]">
        Simulation
      </p>
      <h2 id="simulation-heading" className="mt-1 text-[15px] font-semibold text-[var(--text-primary)]">
        Preview a GCash or Maya payout
      </h2>
      <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
        See how a payout of your current balance would go on either wallet. Nothing is sent and
        your balance does not change.
      </p>

      <div className="mt-3 flex gap-2" role="group" aria-label="Simulated payout wallet">
        {SIMULATED_RAILS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => preview(option.value)}
            aria-pressed={rail === option.value}
            disabled={busy}
            className={`h-9 cursor-pointer rounded-[var(--radius-pill)] px-4 text-[13px] font-medium disabled:cursor-wait ${
              rail === option.value
                ? "bg-[var(--accent-primary)] text-white"
                : "bg-[var(--surface-card)] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)]"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div aria-live="polite">
        {result ? (
          <div className="mt-4">
            <p className="text-[14px] font-medium text-[var(--text-primary)]">
              {simulationHeadline(result)}
            </p>
            {result.steps.length > 0 ? (
              <ol className="mt-3 flex flex-col gap-2">
                {result.steps.map((step, i) => (
                  <li key={step.status} className="flex items-start gap-3 text-[13px] text-[var(--text-secondary)]">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--surface-card)] text-[11px] font-semibold text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)]">
                      {i + 1}
                    </span>
                    {step.label}
                  </li>
                ))}
              </ol>
            ) : null}
            <p className="mt-3 text-[12px] text-[var(--text-muted)]">{result.disclaimer}</p>
          </div>
        ) : null}
        {error ? (
          <p role="alert" className="mt-3 text-[13px] text-[var(--accent-danger)]">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}

export default PayoutSimulation;
