import { Logo } from "@/components/ui/Logo";

/**
 * The form container for every step after the welcome screen.
 *
 * Mobile: Figma "Login & Signup" (5348:2789, 5357:2935), read 2026-09-15 — the
 * wordmark 191px down the gradient, and the AuthSheet (6825:473) from y365 to
 * the bottom edge: radius 32 on top, a 120x8 handle 12px down, the content 48px
 * from the sheet's top, and the pill 31px above the bottom edge. On a shorter
 * phone the gradient band gives way in proportion (43% of an 844 frame) rather
 * than pushing the pill below the fold; it never grows past the frame's 365.
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
      <header className="flex h-[min(365px,43.25dvh)] shrink-0 justify-center pt-[min(191px,22.6dvh)] text-[var(--base-gray-100)] lg:hidden">
        <Logo height={24} label="bluntly" />
      </header>

      <section
        className={[
          // Mobile: bottom sheet.
          "flex flex-1 flex-col rounded-t-[32px] bg-[var(--surface-app)] px-8 pb-[31px] pt-3",
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
        <div className="mt-8 shrink-0">{footer}</div>
      </section>
    </>
  );
}

export default AuthSheet;
