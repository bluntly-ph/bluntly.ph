/**
 * "Step N of 4" progress rail — Figma "StepBar" (6820:477): the label in 12px
 * Regular, 12px over four 4px segments at radius 12, 8px apart, completed in
 * brand orange and the rest in #d9d9d9. The segments fill the column, as the
 * component says, rather than the drawn fixed 75px.
 *
 * Rendered as a real progressbar so the step count is announced rather than
 * being carried only by colour. `action` sits against the right of the label
 * row — the Skip link some frames draw there.
 */
export function StepBar({
  step,
  total = 4,
  action,
}: {
  step: number;
  total?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex min-h-3 items-center justify-between">
        <span className="text-[12px] leading-none text-[var(--text-primary)]">{`Step ${step} of ${total}`}</span>
        {action}
      </div>
      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={step}
        aria-label={`Step ${step} of ${total}`}
        className="flex gap-2"
      >
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className={[
              "h-1 flex-1 rounded-[12px] transition-colors",
              "duration-[var(--duration-base)] ease-[var(--ease-standard)]",
              i < step ? "bg-[var(--accent-primary)]" : "bg-[var(--base-gray-200)]",
            ].join(" ")}
          />
        ))}
      </div>
    </div>
  );
}

export default StepBar;
