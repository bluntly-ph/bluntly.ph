"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { notificationHref, type NotificationItem } from "./notification-model";

const WHEN = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Manila",
});

/**
 * The signed-in account's notifications (FR-1 1.6).
 *
 * Opening one marks it read and follows its link; "Mark all read" clears the
 * rest. Both update the list immediately and tell the API in the background —
 * the read state is a convenience, and waiting on a round trip before
 * navigating would make every notification feel slow.
 */
export function NotificationList({ initial }: { initial: NotificationItem[] }) {
  const router = useRouter();
  const [items, setItems] = useState(initial);
  const [busy, setBusy] = useState(false);
  const unread = items.filter((n) => !n.read_at).length;

  function open(item: NotificationItem) {
    if (!item.read_at) {
      const now = new Date().toISOString();
      setItems((list) => list.map((n) => (n.id === item.id ? { ...n, read_at: now } : n)));
      fetch(`/api/bff/api/v1/notifications/${item.id}/read`, { method: "POST", keepalive: true })
        .catch(() => {});
    }
    router.push(notificationHref(item.link));
  }

  async function markAll() {
    if (busy || unread === 0) return;
    setBusy(true);
    try {
      const res = await fetch("/api/bff/api/v1/notifications/read-all", { method: "POST" });
      if (res.ok) {
        const now = new Date().toISOString();
        setItems((list) => list.map((n) => (n.read_at ? n : { ...n, read_at: now })));
        router.refresh();
      }
    } catch {
      /* the read state is a convenience; leave the list as it was */
    } finally {
      setBusy(false);
    }
  }

  if (items.length === 0) {
    return (
      <p className="mt-6 text-[14px] text-[var(--text-secondary)]">
        Nothing yet. This is where you hear when a review of yours is published or rejected,
        when a question you asked is answered, and when a claim or price you sent is decided.
      </p>
    );
  }

  return (
    <>
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-[13px] text-[var(--text-secondary)]" aria-live="polite">
          {unread === 0 ? "All read" : `${unread} unread`}
        </p>
        <button
          type="button"
          onClick={markAll}
          disabled={busy || unread === 0}
          className="cursor-pointer text-[13px] font-medium text-[var(--accent-primary)] underline-offset-4 hover:underline disabled:cursor-default disabled:text-[var(--text-muted)] disabled:no-underline"
        >
          {busy ? "Marking…" : "Mark all read"}
        </button>
      </div>

      <ul className="mt-3 border-t border-[var(--line-hairline-10)]">
        {items.map((item) => {
          const isUnread = !item.read_at;
          return (
            <li key={item.id} className="border-b border-[var(--line-hairline-10)]">
              <button
                type="button"
                onClick={() => open(item)}
                className="flex w-full cursor-pointer items-start gap-3 py-4 text-left hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
              >
                <span
                  aria-hidden="true"
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    isUnread ? "bg-[var(--accent-primary)]" : "bg-transparent"
                  }`}
                />
                <span className="min-w-0 flex-1">
                  <span
                    className={`block text-[14px] text-[var(--text-primary)] ${
                      isUnread ? "font-semibold" : "font-normal"
                    }`}
                  >
                    {item.title}
                    {isUnread ? <span className="sr-only"> (unread)</span> : null}
                  </span>
                  {item.body ? (
                    <span className="mt-0.5 block text-[13px] text-[var(--text-secondary)]">
                      {item.body}
                    </span>
                  ) : null}
                  <span className="mt-1 block text-[12px] text-[var(--text-muted)]">
                    <time dateTime={item.created_at}>{WHEN.format(new Date(item.created_at))}</time>
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export default NotificationList;
