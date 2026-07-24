/**
 * Route transition wrapper. Next re-mounts `template.tsx` (unlike `layout.tsx`)
 * on every navigation, so this fades each page in — making moving around the
 * site feel smooth. Opacity only: a transform here would reparent the sticky
 * header and fixed bottom nav.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-page">{children}</div>;
}
