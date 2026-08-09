"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowFatDown,
  ArrowFatUp,
  ChatCircle,
  Trash,
} from "@phosphor-icons/react/dist/ssr";

import type { Comment } from "@/lib/comments";

/** Local copies — lib/reviews is server-only, so it can't be imported here. */
function ageLabel(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  const h = Math.floor(secs / 3600);
  if (h < 1) return `${Math.max(1, Math.floor(secs / 60))}m`;
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return `${Math.floor(d / 7)}w`;
}

function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
}

const MAX_BODY = 2000;

/** Apply `fn` to the matching comment anywhere in the two-level tree. */
function mapTree(
  list: Comment[],
  id: string,
  fn: (c: Comment) => Comment,
): Comment[] {
  return list.map((c) =>
    c.id === id
      ? fn(c)
      : { ...c, replies: c.replies.map((r) => (r.id === id ? fn(r) : r)) },
  );
}

/**
 * Discussion under a review (BUG-014) — the page had no comment surface at all.
 *
 * Renders server-fetched comments immediately, then owns them client-side so a
 * post, vote, or removal lands without a full page round trip. Signed-out
 * visitors read the whole thread and are sent to log in the moment they try to
 * take part, matching how voting on the review itself behaves.
 */
export function CommentThread({
  reviewId,
  initial,
  viewerId,
}: {
  reviewId: string;
  initial: Comment[];
  /** null when signed out — also what decides "is this mine to delete?". */
  viewerId: string | null;
}) {
  const [comments, setComments] = useState<Comment[]>(initial);
  const [error, setError] = useState<string | null>(null);

  const total = comments.reduce((n, c) => n + 1 + c.replies.length, 0);

  return (
    <section className="mt-10 border-t border-[var(--border-subtle)] pt-8">
      <h2 className="flex items-center gap-2 text-[16px] font-semibold text-[var(--text-primary)]">
        <ChatCircle size={20} weight="fill" className="text-[var(--text-muted)]" />
        {total === 0 ? "Comments" : `${compact(total)} ${total === 1 ? "comment" : "comments"}`}
      </h2>

      <CommentComposer
        reviewId={reviewId}
        viewerId={viewerId}
        onPosted={(c) => setComments((prev) => [...prev, c])}
        onError={setError}
      />

      {error ? (
        <p role="alert" className="mt-3 text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}

      {comments.length === 0 ? (
        <p className="mt-8 text-[14px] text-[var(--text-secondary)]">
          No comments yet. Ask the reviewer something, or add what you know.
        </p>
      ) : (
        <ul className="mt-6 flex flex-col gap-6">
          {comments.map((c) => (
            <li key={c.id}>
              <CommentRow
                comment={c}
                reviewId={reviewId}
                viewerId={viewerId}
                onChange={(next) => setComments((prev) => mapTree(prev, next.id, () => next))}
                onReplied={(reply) =>
                  setComments((prev) =>
                    mapTree(prev, c.id, (parent) => ({
                      ...parent,
                      replies: [...parent.replies, reply],
                    })),
                  )
                }
                onError={setError}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CommentComposer({
  reviewId,
  viewerId,
  parentId,
  autoFocus = false,
  onPosted,
  onError,
  onCancel,
}: {
  reviewId: string;
  viewerId: string | null;
  parentId?: string;
  autoFocus?: boolean;
  onPosted: (c: Comment) => void;
  onError: (message: string | null) => void;
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);

  if (!viewerId) {
    return (
      <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
        <Link
          href={`/login?next=/reviews/${reviewId}`}
          className="font-medium text-[var(--accent-primary)] underline underline-offset-2"
        >
          Log in
        </Link>{" "}
        to join the discussion.
      </p>
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed || pending) return;
    setPending(true);
    onError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/reviews/${reviewId}/comments`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          body: trimmed,
          ...(parentId ? { parent_id: parentId } : {}),
        }),
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        onError(problem.detail ?? "Couldn't post your comment.");
        return;
      }
      const posted = (await res.json()) as Comment;
      // The API omits `replies` on a freshly created comment; the tree needs it.
      onPosted({ ...posted, replies: posted.replies ?? [] });
      setBody("");
      onCancel?.();
      // Keep the server's copy of the page in step for the next navigation.
      router.refresh();
    } catch {
      onError("Couldn't reach the server.");
    } finally {
      setPending(false);
    }
  }

  const over = body.length > MAX_BODY;

  return (
    <form onSubmit={submit} className={parentId ? "mt-3" : "mt-4"}>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        autoFocus={autoFocus}
        rows={parentId ? 2 : 3}
        placeholder={parentId ? "Write a reply…" : "Add a comment"}
        aria-label={parentId ? "Write a reply" : "Add a comment"}
        className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <div className="mt-2 flex items-center gap-3">
        <button
          type="submit"
          disabled={pending || !body.trim() || over}
          className="inline-flex items-center rounded-[var(--radius-pill)] bg-[var(--accent-primary)] px-5 py-2 text-[13px] font-semibold text-white hover:bg-[var(--accent-primary-strong)] disabled:bg-[rgba(32,32,32,0.14)] disabled:text-[rgba(32,32,32,0.52)]"
        >
          {pending ? "Posting…" : parentId ? "Reply" : "Comment"}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            Cancel
          </button>
        ) : null}
        {over ? (
          <span className="text-[12px] text-[var(--accent-danger)]">
            {body.length}/{MAX_BODY}
          </span>
        ) : null}
      </div>
    </form>
  );
}

function CommentRow({
  comment,
  reviewId,
  viewerId,
  isReply = false,
  onChange,
  onReplied,
  onError,
}: {
  comment: Comment;
  reviewId: string;
  viewerId: string | null;
  isReply?: boolean;
  onChange: (next: Comment) => void;
  onReplied?: (reply: Comment) => void;
  onError: (message: string | null) => void;
}) {
  const router = useRouter();
  const [replying, setReplying] = useState(false);
  const [pending, setPending] = useState(false);

  const name =
    comment.author?.display_name || comment.author?.username || "someone";
  const isMine = viewerId !== null && comment.author?.id === viewerId;

  async function vote(dir: "up" | "down") {
    if (!viewerId) {
      router.push(`/login?next=/reviews/${reviewId}`);
      return;
    }
    if (pending) return;
    setPending(true);
    onError(null);
    const remove = comment.my_vote === dir;
    try {
      const res = await fetch(`/api/bff/api/v1/comments/${comment.id}/vote`, {
        method: remove ? "DELETE" : "POST",
        headers: remove ? undefined : { "content-type": "application/json" },
        body: remove ? undefined : JSON.stringify({ vote: dir }),
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        onError(problem.detail ?? "Couldn't record your vote.");
        return;
      }
      const updated = (await res.json()) as Comment;
      onChange({
        ...comment,
        helpful_votes: updated.helpful_votes,
        unhelpful_votes: updated.unhelpful_votes,
        my_vote: remove ? null : dir,
      });
    } catch {
      onError("Couldn't reach the server.");
    } finally {
      setPending(false);
    }
  }

  async function remove() {
    if (pending) return;
    setPending(true);
    onError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/comments/${comment.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => ({}))) as { detail?: string };
        onError(problem.detail ?? "Couldn't remove your comment.");
        return;
      }
      // The row stays in the thread so replies keep their parent; only the body
      // and the author go.
      onChange({
        ...comment,
        is_removed: true,
        body: "[removed]",
        author: null,
      });
      router.refresh();
    } catch {
      onError("Couldn't reach the server.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full text-[12px] font-semibold text-white"
          style={{ background: comment.is_removed ? "hsl(0 0% 70%)" : "hsl(24 55% 55%)" }}
        >
          {comment.is_removed ? "–" : name.slice(0, 1).toUpperCase()}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            {comment.is_removed ? (
              <span className="text-[13px] font-semibold text-[var(--text-muted)]">
                removed
              </span>
            ) : comment.author?.id ? (
              <Link
                href={`/u/${comment.author.id}`}
                className="text-[13px] font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
              >
                {comment.author.username ? `@${comment.author.username}` : name}
              </Link>
            ) : (
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {name}
              </span>
            )}
            <span className="text-[12px] text-[var(--text-muted)]">
              {ageLabel(comment.created_at)}
            </span>
          </div>

          <p
            className={`mt-1 whitespace-pre-line text-[14px] leading-relaxed ${
              comment.is_removed
                ? "italic text-[var(--text-muted)]"
                : "text-[var(--text-primary)]"
            }`}
          >
            {comment.body}
          </p>

          {!comment.is_removed ? (
            <div className="mt-1.5 flex items-center gap-1">
              <button
                type="button"
                onClick={() => vote("up")}
                disabled={pending}
                aria-pressed={comment.my_vote === "up"}
                aria-label="Helpful"
                className={`inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-1 text-[12px] hover:bg-[var(--line-hairline-10)] disabled:opacity-60 ${
                  comment.my_vote === "up"
                    ? "text-[var(--accent-success)]"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                <ArrowFatUp
                  size={14}
                  weight={comment.my_vote === "up" ? "fill" : "regular"}
                />
                {compact(comment.helpful_votes)}
              </button>
              <button
                type="button"
                onClick={() => vote("down")}
                disabled={pending}
                aria-pressed={comment.my_vote === "down"}
                aria-label="Not helpful"
                className={`inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-1 text-[12px] hover:bg-[var(--line-hairline-10)] disabled:opacity-60 ${
                  comment.my_vote === "down"
                    ? "text-[var(--accent-danger)]"
                    : "text-[var(--text-muted)]"
                }`}
              >
                <ArrowFatDown
                  size={14}
                  weight={comment.my_vote === "down" ? "fill" : "regular"}
                />
                {compact(comment.unhelpful_votes)}
              </button>

              {/* Replies are one level deep, so a reply offers no reply button. */}
              {!isReply ? (
                <button
                  type="button"
                  onClick={() => setReplying((v) => !v)}
                  className="rounded-[var(--radius-pill)] px-2 py-1 text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--text-primary)]"
                >
                  Reply
                </button>
              ) : null}

              {isMine ? (
                <button
                  type="button"
                  onClick={remove}
                  disabled={pending}
                  className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2 py-1 text-[12px] text-[var(--text-muted)] hover:bg-[var(--line-hairline-10)] hover:text-[var(--accent-danger)] disabled:opacity-60"
                >
                  <Trash size={14} />
                  Delete
                </button>
              ) : null}
            </div>
          ) : null}

          {replying && onReplied ? (
            <CommentComposer
              reviewId={reviewId}
              viewerId={viewerId}
              parentId={comment.id}
              autoFocus
              onPosted={(reply) => {
                onReplied(reply);
                setReplying(false);
              }}
              onError={onError}
              onCancel={() => setReplying(false)}
            />
          ) : null}

          {comment.replies.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-4 border-l border-[var(--border-subtle)] pl-4">
              {comment.replies.map((r) => (
                <li key={r.id}>
                  <CommentRow
                    comment={r}
                    reviewId={reviewId}
                    viewerId={viewerId}
                    isReply
                    onChange={onChange}
                    onError={onError}
                  />
                </li>
              ))}
            </ul>
          ) : null}
      </div>
    </div>
  );
}

export default CommentThread;
