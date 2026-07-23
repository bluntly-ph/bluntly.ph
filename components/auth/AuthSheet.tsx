import { Logo } from "@/components/ui/Logo";

/**
 * The form container for every step after the welcome screen.
 *
 * Mobile: the frame as drawn — wordmark on the gradient, then a rounded-top
 * sheet rising from the bottom edge with a grabber, and the primary action
 * pinned to the bottom.
 *
 * Desktop: the bottom-sheet metaphor is meaningless with a mouse and a tall
 * viewport, so the same content becomes a self-contained card on the light
 * surface — all four corners rounded, no grabber, no full-height stretch, and
 * the action sits directly under the form instead of being pushed to the
 * screen edge. The brand column supplies the wordmark, so it is dropped here.
 */
export function AuthSheet({
  children,
  footer,
}: {
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <>
      <header className="flex h-[240px] shrink-0 items-center justify-center text-[var(--base-gray-100)] lg:hidden">
        <Logo height={24} label="bluntly" />
      </header>

      <section
        className={[
          // Mobile: bottom sheet.
          "flex flex-1 flex-col rounded-t-[32px] bg-[var(--surface-app)] px-8 pb-10 pt-3",
          // Desktop: a card that sizes to its content.
          "lg:w-full lg:max-w-[26rem] lg:flex-none lg:rounded-[20px] lg:bg-[var(--surface-card)]",
          "lg:p-10 lg:shadow-[var(--shadow-card)]",
        ].join(" ")}
      >
        <div
          aria-hidden="true"
          className="mx-auto mb-7 h-2 w-[120px] shrink-0 rounded-[12px] bg-[var(--base-gray-200)] lg:hidden"
        />
        <div className="flex flex-1 flex-col lg:flex-none">{children}</div>
        <div className="mt-8 shrink-0 lg:mt-8">{footer}</div>
      </section>
    </>
  );
}

export default AuthSheet;
