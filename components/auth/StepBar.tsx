/**
 * "Step N of 4" progress rail — four segments that fill orange as the user
 * advances, exactly as drawn on the onboarding frames.
 *
 * Rendered as a real progressbar so the step count is announced rather than
 * being carried only by colour.
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
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-[var(--text-secondary)]">
          {`Step ${step} of ${total}`}
        </span>
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
              "h-1 flex-1 rounded-full",
              i < step
                ? "bg-[var(--accent-primary)]"
                : "bg-[var(--base-gray-200)]",
            ].join(" ")}
          />
        ))}
      </div>
    </div>
  );
}

export default StepBar;
