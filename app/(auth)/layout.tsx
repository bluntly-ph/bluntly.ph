/**
 * Auth shell.
 *
 * Page 1 of the Figma file is the design of record and it is drawn at 390px.
 * Rather than inventing a separate desktop treatment, the mobile composition is
 * preserved and centred: the brand gradient fills the viewport at every size,
 * and the content column is capped at the frame width. That keeps the design
 * intact on a phone and makes it a deliberate, centred layout on a monitor.
 */
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-dvh bg-[image:var(--brand-gradient)] bg-cover bg-fixed">
      <div className="mx-auto flex min-h-dvh w-full max-w-[430px] flex-col">
        {children}
      </div>
    </div>
  );
}
