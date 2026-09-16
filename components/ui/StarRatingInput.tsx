"use client";

import { Star, StarHalf } from "@phosphor-icons/react";
import { useId } from "react";

import { STAR_EMPTY, STAR_STEPS, formatRating, starColor, starFill } from "@/components/ui/star-ladder";

/**
 * The rating control: five stars, eleven answers — 0, 0.5, 1 … 5 (owner
 * requirement, 2026-09-16, replacing whole stars only). Zero is a real answer,
 * not an unanswered question, so it has its own selectable state.
 *
 * It is a radio group of eleven inputs behind the drawn stars. That is what
 * makes it work everywhere without hand-written key handling: arrow keys move
 * between steps, Space picks one, a screen reader announces "3.5 stars, 8 of
 * 11", and a tap lands on whichever half of a star was touched because each
 * radio's label is that half. Every hit area is the full height of the star and
 * half its width — 26px at the composer's 52px stars, comfortably tappable.
 *
 * The stars themselves are Figma "Icon/Star" (6805:431): filled takes the
 * rating ladder's colour, empty is the solid grey silhouette, and a half is the
 * two drawn over each other so the colour split lands mid-glyph.
 */
export function StarRatingInput({
  value,
  onChange,
  name,
  size = 52,
  gap = 8,
  label,
  /** Per-star vertical offsets, for the composer's arc. */
  arc,
  className = "",
}: {
  value: number | null;
  onChange: (next: number) => void;
  /** Radio group name; defaults to a generated one. */
  name?: string;
  size?: number;
  gap?: number;
  /** What is being rated, for assistive tech: "Star rating". */
  label: string;
  arc?: readonly number[];
  className?: string;
}) {
  const generated = useId();
  const group = name ?? `stars-${generated}`;

  return (
    <fieldset className={`min-w-0 border-0 p-0 ${className}`}>
      <legend className="sr-only">{label}</legend>

      <div className="flex items-start justify-center" style={{ gap }}>
        {[1, 2, 3, 4, 5].map((position) => {
          const fill = starFill(position, value);
          const colour = value !== null && fill !== "empty" ? starColor(value) : STAR_EMPTY;
          return (
            <span
              key={position}
              className="relative block shrink-0"
              style={{ width: size, height: size, marginTop: arc?.[position - 1] ?? 0 }}
            >
              {/* The glyph. A half is the grey star with the coloured half over
                  it, so the split is the icon's own, not a clipped rectangle. */}
              <Star
                size={size}
                weight="fill"
                aria-hidden="true"
                className="absolute inset-0 transition-colors"
                style={{ color: fill === "full" ? colour : STAR_EMPTY }}
              />
              {fill === "half" ? (
                <StarHalf
                  size={size}
                  weight="fill"
                  aria-hidden="true"
                  className="absolute inset-0"
                  style={{ color: colour }}
                />
              ) : null}

              {/* Two hit areas per star: its half step and its whole step. */}
              {[position - 0.5, position].map((step) => (
                <label
                  key={step}
                  className="absolute top-0 h-full w-1/2 cursor-pointer"
                  style={{ left: step === position ? "50%" : 0 }}
                >
                  <input
                    type="radio"
                    name={group}
                    value={step}
                    checked={value === step}
                    onChange={() => onChange(step)}
                    className="peer sr-only"
                  />
                  <span className="sr-only">
                    {formatRating(step)} {step === 1 ? "star" : "stars"}
                  </span>
                  {/* The focus ring belongs to the star, not to a 1px input. */}
                  <span
                    aria-hidden="true"
                    className="absolute inset-0 rounded-[6px] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent-primary)]"
                  />
                </label>
              ))}
            </span>
          );
        })}
      </div>

      {/* Zero: a real answer with no star to click, so it gets its own control
          rather than being the state you reach by never answering. */}
      <label className="mt-4 flex cursor-pointer items-center justify-center gap-2 text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">
        <input
          type="radio"
          name={group}
          value={0}
          checked={value === 0}
          onChange={() => onChange(0)}
          className="peer sr-only"
        />
        <span
          aria-hidden="true"
          className={`grid h-5 w-5 place-items-center rounded-full peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent-primary)] ${
            value === 0
              ? "bg-[var(--accent-primary)]"
              : "shadow-[inset_0_0_0_1px_var(--line-hairline-30)]"
          }`}
        >
          {value === 0 ? <span className="h-2 w-2 rounded-full bg-white" /> : null}
        </span>
        No stars (0)
      </label>

      {/* What was chosen, once, for anyone who cannot see the glyphs. */}
      <p role="status" className="sr-only">
        {value === null ? "No rating chosen yet." : `${formatRating(value)} out of 5.`}
      </p>
    </fieldset>
  );
}

export { STAR_STEPS };
export default StarRatingInput;
