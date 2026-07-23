import { Logo } from "@/components/ui/Logo";

/**
 * The auth shell, at two scales.
 *
 * Below `lg` this is the Figma frame verbatim: the gradient fills the screen
 * and the page composes its own hero + sheet on top of it.
 *
 * At `lg` and above the same ingredients are re-laid-out for a wide viewport
 * rather than being letterboxed — the gradient becomes a brand column carrying
 * the wordmark and the product promise, and the form sits on the light app
 * surface beside it. Nothing new is invented: the colours, type ramp, radii and
 * copy are the ones the mobile frames already use.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-[image:var(--brand-gradient)] lg:grid lg:grid-cols-[1.05fr_1fr] lg:bg-none lg:bg-[var(--surface-app)]">
      {/* Brand column — desktop only. On mobile the gradient above carries the
          brand and each page draws its own logo. */}
      <aside className="hidden bg-[image:var(--brand-gradient)] p-12 text-[var(--base-gray-100)] lg:flex lg:flex-col lg:justify-between xl:p-16">
        <Logo height={26} label="bluntly" />

        <div className="max-w-[26rem]">
          <h2 className="text-[32px] font-semibold leading-[1.2] xl:text-[40px]">
            Honest reviews.
            <br />
            Real Payouts.
          </h2>
          <p className="mt-4 text-[15px] font-light leading-relaxed tracking-[0.168px] text-[rgba(242,242,242,0.85)]">
            Join Filipinos making smarter purchases and the reviewers earning
            from honest opinions.
          </p>
        </div>

        <p className="text-[12px] font-light text-[rgba(242,242,242,0.7)]">
          No sponsorships. No bias. Ever.
        </p>
      </aside>

      <div className="flex min-h-dvh flex-col lg:min-h-0 lg:items-center lg:justify-center lg:p-12">
        {children}
      </div>
    </div>
  );
}

export default AuthShell;
