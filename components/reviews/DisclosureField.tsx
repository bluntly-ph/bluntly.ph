"use client";

import { useId } from "react";

import { DISCLOSURE_OPTIONS, type MaterialRelationship } from "@/components/reviews/disclosure-model";

/**
 * "Anything to disclose?" on the composer's last step.
 *
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY. Step 7's frame draws
 * the title and the preview only. Disclosure of a material relationship is
 * required (completion contract X.1), so it sits under the title in the step's
 * own type — the 12px Light blurb, 53px white answers at radius 16 like the
 * verdict step's (Figma 4435:1092), 10px Light for the note — and Submit waits
 * for an answer. "No, I bought it myself" is one of
 * the answers, so an ordinary reviewer is one tap from done.
 */
export function DisclosureField({
  value,
  onChange,
}: {
  value: MaterialRelationship | null;
  onChange: (next: MaterialRelationship) => void;
}) {
  const legendId = useId();
  return (
    <fieldset aria-labelledby={legendId} className="mt-6">
      <p
        id={legendId}
        className="text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]"
      >
        Anything to disclose? Did you get this for free or at a discount, or are you
        connected to the brand or seller?
      </p>
      <div className="mt-3 flex flex-col gap-2">
        {DISCLOSURE_OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-pressed={selected}
              className={`min-h-[53px] cursor-pointer rounded-[16px] bg-[var(--surface-card)] px-4 py-3 text-left text-[14px] leading-[21px] text-[var(--text-primary)] ${
                selected
                  ? "shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]"
                  : "shadow-[var(--shadow-card)]"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-[10px] font-light leading-[15px] text-[var(--text-primary)]">
        If you got it free or have a connection, readers see that on your review.
      </p>
    </fieldset>
  );
}

export default DisclosureField;
