import { Logo } from "@/components/ui/Logo";

/**
 * The gradient hero + rounded-top sheet used by every step after the welcome
 * screen ("Let's get started!", "Enter the code").
 *
 * In the frames the logo sits on the gradient and the sheet rises from the
 * bottom edge with a grabber. The sheet is `flex-1` and its footer is pushed
 * down, so the primary action stays pinned to the bottom exactly as drawn —
 * without the absolute positioning the Figma export uses, which would not
 * survive a keyboard opening or a longer error message.
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
      <header className="flex h-[240px] shrink-0 items-center justify-center text-[var(--base-gray-100)]">
        <Logo height={24} label="bluntly" />
      </header>

      <section className="flex flex-1 flex-col rounded-t-[32px] bg-[var(--surface-app)] px-8 pb-10 pt-3">
        <div
          aria-hidden="true"
          className="mx-auto mb-7 h-2 w-[120px] shrink-0 rounded-[12px] bg-[var(--base-gray-200)]"
        />
        <div className="flex flex-1 flex-col">{children}</div>
        {footer ? <div className="mt-8 shrink-0">{footer}</div> : null}
      </section>
    </>
  );
}

export default AuthSheet;
