import { CloudWarning } from "@phosphor-icons/react/dist/ssr";

/**
 * "We could not reach the server", as distinct from "there is nothing here".
 *
 * The read helpers in lib/ catch transport failures and used to return an empty
 * array, which every page then rendered as its ordinary empty state. A reader
 * whose request timed out was told "No open requests" — a confident, wrong
 * answer that invites them to leave rather than retry. The helpers now return
 * null for "could not load" and [] for "genuinely empty", and this is what null
 * looks like.
 *
 * Deliberately not an error.tsx boundary: nothing throws, so no boundary would
 * ever catch it. This is a rendered state, not an exception.
 */
export function Unavailable({ what }: { what: string }) {
  return (
    <div
      role="status"
      className="mt-6 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-10 text-center shadow-[var(--shadow-hairline-inset)]"
    >
      <CloudWarning size={32} className="mx-auto text-[var(--text-muted)]" />
      <p className="mt-3 text-[15px] font-semibold text-[var(--text-primary)]">
        Couldn&rsquo;t load {what}
      </p>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        We couldn&rsquo;t reach the server just now. This is on us — refresh in a
        moment and it should come back.
      </p>
    </div>
  );
}

export default Unavailable;
