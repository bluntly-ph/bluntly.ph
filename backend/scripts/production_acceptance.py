"""Production acceptance harness — exercises the deployed system, then cleans up.

Zient authorised bluntly.ph production as the QA target for this release
sprint. That authorisation is not a licence to leave things behind, so every
flow here is:

    create -> test -> verify -> clean up -> verify cleanup

and the run **fails loudly if cleanup fails**. A green run that left an account
behind is a failed run.

Deliberately not the pytest suite. That suite generates large fixture sets and
belongs on an isolated database; this creates a handful of clearly-marked rows
against the real deployment and removes them again. Keep it that way — if you
find yourself adding a loop that creates hundreds of anything, it belongs in
the other suite.

Everything it creates carries the `qa_` marker and a per-run id, so a leaked
row is identifiable months later.

    python -m scripts.production_acceptance --base https://www.bluntly.ph
    python -m scripts.production_acceptance --phase anonymous

Exit codes: 0 all passed and cleanup verified, 1 a check failed, 2 cleanup
failed (investigate immediately — there is residue in production).
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import uuid

DEFAULT_BASE = "https://www.bluntly.ph"
MARKER = "qa_"


class Result:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if ok:
            self.passed += 1
        else:
            self.failed.append(name)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
        return ok


class Api:
    """Minimal client. Returns (status, parsed-or-text) and never raises."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token: str | None = None

    def __call__(self, method: str, path: str, json_body=None, raw: bytes | None = None,
                 content_type: str | None = None, timeout: int = 45):
        headers = {"User-Agent": "bluntly-acceptance/1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = raw
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                try:
                    return resp.status, json.loads(body) if body else None
                except json.JSONDecodeError:
                    return resp.status, body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(body) if body else None
            except json.JSONDecodeError:
                return exc.code, body
        except Exception as exc:  # noqa: BLE001
            return f"ERR:{type(exc).__name__}", str(exc)


class Created:
    """Everything this run made, so teardown can be exhaustive rather than hopeful."""

    def __init__(self) -> None:
        self.reviews: list[str] = []
        self.questions: list[str] = []
        self.requests: list[str] = []
        self.comments: list[str] = []
        self.voted_reviews: list[str] = []
        self.users: list[tuple[str, str]] = []   # (id, email)
        self.photo_urls: list[str] = []
        self.receipt_keys: list[str] = []

    def summary(self) -> str:
        return (f"reviews={len(self.reviews)} questions={len(self.questions)} "
                f"requests={len(self.requests)} comments={len(self.comments)} "
                f"votes={len(self.voted_reviews)} users={len(self.users)} "
                f"photos={len(self.photo_urls)} receipts={len(self.receipt_keys)}")


def anonymous_phase(api: Api, r: Result) -> None:
    print("\nANONYMOUS")
    for path, label in (("/", "landing"), ("/search", "search"),
                        ("/categories", "categories"), ("/compare", "comparison"),
                        ("/questions", "public Q&A"), ("/requests", "request board"),
                        ("/membership", "membership")):
        st, body = api("GET", path)
        r.check(f"{label} renders", st == 200 and isinstance(body, str) and len(body) > 40000,
                f"{st}")

    st, feed = api("GET", "/api/v1/reviews/feed?limit=24")
    r.check("public feed", st == 200 and isinstance(feed, list) and len(feed) > 0,
            f"{len(feed) if isinstance(feed, list) else st} reviews")

    leaked = [k for k in ("password_hash", "receipt_key", "payout_account", "affiliate_link")
              if k in json.dumps(feed)]
    r.check("feed leaks nothing sensitive", not leaked, str(leaked or "none"))

    for path in ("/api/v1/admin/review-queue", "/api/v1/payouts", "/api/v1/contracts",
                 "/api/v1/auth/me"):
        st, _ = api("GET", path)
        r.check(f"gated: {path.split('/v1')[1]}", st == 401, str(st))


def user_phase(api: Api, r: Result, made: Created, run_id: str) -> None:
    """A reviewer's journey, one of each thing rather than many."""
    print("\nAUTHENTICATED USER")
    email = f"{MARKER}user_{run_id}@example.com"
    password = "QaRelease!" + uuid.uuid4().hex[:12]

    st, body = api("POST", "/api/v1/auth/register", {
        "email": email, "password": password, "display_name": "QA Acceptance User"})
    if not r.check("register", st == 201 and isinstance(body, dict), str(st)):
        return
    api.token = body["access_token"]
    made.users.append((body["user"]["id"], email))

    st, me = api("GET", "/api/v1/auth/me")
    r.check("session works", st == 200 and me.get("email") == email, str(st))

    st, _ = api("PATCH", "/api/v1/users/me", {
        "username": f"qa{run_id[:10]}", "display_name": "QA Acceptance User",
        "interests": ["electronics-tech", "beauty", "gaming"]})
    r.check("onboarding profile + interests", st == 200, str(st))

    st, me = api("GET", "/api/v1/auth/me")
    r.check("interests stored canonically", isinstance(me, dict)
            and set(me.get("interests") or []) == {"electronics-tech", "beauty", "gaming"},
            str(me.get("interests") if isinstance(me, dict) else st))

    st, _ = api("PATCH", "/api/v1/users/me", {"interests": ["not-a-real-category"]})
    r.check("unknown interest refused", st == 422, str(st))

    st, products = api("GET", "/api/v1/products?limit=5")
    product_id = products[0]["id"] if isinstance(products, list) and products else None
    r.check("products readable while signed in", bool(product_id), str(st))

    st, price = api("POST", f"/api/v1/products/{product_id}/prices", {
        "platform": "shopee", "price": "1234.50",
        "observed_at": "2026-08-20", "variant": f"{MARKER}{run_id[:8]}"})
    r.check("price observation accepted (FR-2)", st in (200, 201), str(st))

    st, _ = api("POST", f"/api/v1/products/{product_id}/prices", {
        "platform": "shopee", "price": "1234.50",
        "observed_at": "2099-01-01", "variant": "future"})
    r.check("future price refused", st == 422, str(st))

    st, q = api("POST", "/api/v1/questions", {
        "product_id": product_id, "body": f"{MARKER}{run_id}: does this hold up after a year?",
        "directed_to": "buyers"})
    if st in (200, 201) and isinstance(q, dict):
        made.questions.append(q["id"])
    r.check("ask a question", st in (200, 201), str(st))

    st, req = api("POST", "/api/v1/requests", {
        "title": f"{MARKER}{run_id}: please review a budget power bank",
        "details": ("Looking for an honest review of a sub-1000 peso power bank, "
                    "specifically how it holds up after six months of daily use.")})
    if st in (200, 201) and isinstance(req, dict):
        made.requests.append(req["id"])
    r.check("post a review request", st in (200, 201), str(st))

    st, feed = api("GET", "/api/v1/reviews/feed?limit=6")
    other = None
    if isinstance(feed, list):
        other = next((i["review"]["id"] for i in feed if i.get("review")), None)
    if other:
        st, _ = api("POST", f"/api/v1/reviews/{other}/vote", {"vote": "up"})
        if st in (200, 201):
            made.voted_reviews.append(other)
        r.check("vote on a published review", st in (200, 201), str(st))

        st, c = api("POST", f"/api/v1/reviews/{other}/comments", {
            "body": f"{MARKER}{run_id}: acceptance check, will be removed."})
        if st in (200, 201) and isinstance(c, dict):
            made.comments.append(c["id"])
        r.check("comment on a review", st in (200, 201), str(st))


def _pending_ids(queue) -> list[str]:
    """Review ids in the moderator queue's pending list.

    The queue is `{"pending": [...], "edited_since_monetized": [...]}`, and each
    entry is a card wrapping the review rather than the review itself. Reading
    it as a bare list, or reaching for `items`, yields an empty result that
    looks exactly like a product bug — that misreading cost an afternoon once,
    so the shape lives in one function.
    """
    if not isinstance(queue, dict):
        return []
    return [(card.get("review") or {}).get("id") for card in queue.get("pending", [])]


def moderator_phase(api: Api, r: Result, made: Created, run_id: str,
                    mod_token: str) -> None:
    """Moderation, exercised against a review this run created — never a real one.

    Needs a moderator token from outside: promoting an account is a database
    operation and this harness deliberately has none. Promote a `qa_` account
    with

        UPDATE users SET role = 'moderator' WHERE email = '<the qa_ account>';

    and pass `--moderator-token`. Without one the phase is skipped, not faked.
    """
    print("\nMODERATOR")

    # A dedicated author, so the review being moderated is unambiguously ours.
    author = Api(api.base)
    email = f"{MARKER}author_{run_id}@example.com"
    st, body = author("POST", "/api/v1/auth/register", {
        "email": email, "password": "QaRelease!" + uuid.uuid4().hex[:12],
        "display_name": "QA Review Author"})
    if not r.check("moderation author registered",
                   st == 201 and isinstance(body, dict), str(st)):
        return
    author.token = body["access_token"]
    made.users.append((body["user"]["id"], email))

    st, products = author("GET", "/api/v1/products?limit=5")
    product_id = products[0]["id"] if isinstance(products, list) and products else None
    if not r.check("product available to review", bool(product_id), str(st)):
        return

    st, review = author("POST", "/api/v1/reviews", {
        "product_id": product_id,
        "title": f"{MARKER}{run_id} acceptance review",
        "discussion": ("Created by the release acceptance harness to exercise the "
                       "moderation queue end to end, and removed immediately after."),
        "verdict": "it_depends",
        "verdict_explanation": "Acceptance testing of the moderation flow.",
        "target_audience": "Engineers verifying the moderation queue.",
        "anti_target_audience": "Anyone expecting a real product opinion.",
        "star_rating": 4,
        "pros": ["exercises the queue"], "cons": ["not a real review"]})
    if not r.check("review created", st in (200, 201) and isinstance(review, dict), str(st)):
        return
    review_id = review["id"]
    made.reviews.append(review_id)

    # The publication gate (M2 slice 1) and FR-3 verification, on live data.
    r.check("new review is unpublished", review.get("published_at") is None,
            str(review.get("published_at")))
    r.check("unverified without an owned proof photo",
            review.get("verification_status") == "unverified",
            str(review.get("verification_status")))

    mod = Api(api.base)
    mod.token = mod_token
    st, me = mod("GET", "/api/v1/auth/me")
    role = me.get("role") if isinstance(me, dict) else None
    if not r.check("moderator session", st == 200 and role in ("moderator", "admin"),
                   str(role or st)):
        return

    st, queue = mod("GET", "/api/v1/admin/review-queue?limit=100")
    if not r.check("queue reachable and shaped as documented",
                   st == 200 and isinstance(queue, dict) and "pending" in queue, str(st)):
        return
    r.check("our review is in the queue", review_id in _pending_ids(queue),
            f"{len(_pending_ids(queue))} pending")

    st, published = mod("POST", f"/api/v1/admin/reviews/{review_id}/publish")
    r.check("moderator can publish", st == 200, str(st))
    if isinstance(published, dict):
        r.check("published_at set", published.get("published_at") is not None,
                str(published.get("published_at")))
        r.check("routed to an earnings state",
                published.get("earn_eligible_status") in ("approved", "honesty_fund"),
                str(published.get("earn_eligible_status")))

    st, unpublished = mod("POST", f"/api/v1/admin/reviews/{review_id}/unpublish",
                          {"reason": f"{MARKER}{run_id} acceptance"})
    r.check("moderator can unpublish", st == 200, str(st))

    # Regression guard. Unpublishing used to clear `published_at` and leave the
    # status alone, which took the review off the site AND out of the queue in
    # the same move: no moderator control could reach it again. Production had
    # two reviews stranded that way, the older one for eleven days.
    st, queue = mod("GET", "/api/v1/admin/review-queue?limit=100")
    r.check("unpublished review returns to the queue",
            review_id in _pending_ids(queue),
            str(unpublished.get("earn_eligible_status")
                if isinstance(unpublished, dict) else st))

    st, _ = mod("GET", "/api/v1/admin/reports")
    r.check("reports queue reachable", st == 200, str(st))


def teardown(api: Api, r: Result, made: Created) -> bool:
    """Remove everything, then prove it is gone. Returns True when clean."""
    print("\nCLEANUP")
    print(f"  created: {made.summary()}")

    for cid in made.comments:
        st, _ = api("DELETE", f"/api/v1/comments/{cid}")
        r.check(f"comment {cid[:8]} removed", st in (200, 204, 404), str(st))
    for rid in made.voted_reviews:
        st, _ = api("DELETE", f"/api/v1/reviews/{rid}/vote")
        r.check(f"vote on {rid[:8]} withdrawn", st in (200, 204, 404), str(st))
    # Questions have no DELETE route — POST, GET, GET/{id}, answers and
    # best-answer only — even though the `questions_delete_own` RLS policy
    # implies one was intended, and comments and requests both have one. So a
    # question created here cannot be removed through the API. A 405 is not
    # cleanup, and counting it as cleanup is how residue becomes invisible.
    undeletable_questions = list(made.questions)
    for rid in made.requests:
        st, _ = api("DELETE", f"/api/v1/requests/{rid}")
        r.check(f"request {rid[:8]} removed", st in (200, 204, 404), str(st))

    # The API has no delete-user endpoint by design, so the account and anything
    # the API cannot reach is named here for database teardown. Printed rather
    # than silently skipped: residue nobody knows about is the failure mode.
    needs_db = bool(made.users or undeletable_questions or made.reviews)
    if needs_db:
        print()
        print("  REQUIRES DATABASE TEARDOWN (no API route exists):")
        for uid, email in made.users:
            print(f"    user     {uid}  {email}")
        for qid in undeletable_questions:
            print(f"    question {qid}  (no DELETE route on /questions)")
        for rid in made.reviews:
            print(f"    review   {rid}  (no DELETE route on /reviews)")
        print()
        print("    -- children first; reviews and users are both referenced.")
        print("    DELETE FROM review_versions WHERE review_id IN")
        print("      (SELECT id FROM reviews WHERE title LIKE 'qa\\_%');")
        print("    DELETE FROM moderation_logs WHERE target_ref IN")
        print("      (SELECT id FROM reviews WHERE title LIKE 'qa\\_%');")
        print("    DELETE FROM reviews   WHERE title LIKE 'qa\\_%';")
        print("    DELETE FROM questions WHERE body  LIKE 'qa\\_%';")
        print("    DELETE FROM sessions  WHERE user_id IN")
        print("      (SELECT id FROM users WHERE email LIKE 'qa\\_%@example.com');")
        print("    DELETE FROM users     WHERE email LIKE 'qa\\_%@example.com';")

    # Cleanup counts as verified only once the residue is actually gone. This
    # harness cannot reach the database, so it reports rather than claims, and
    # returns False so the caller exits non-zero and nobody reads a run that
    # left an account behind as green.
    return not needs_db


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--phase", choices=["anonymous", "user", "moderator", "all"],
                    default="all")
    ap.add_argument("--moderator-token",
                    help="Bearer token for a moderator account. Required by the "
                         "moderator phase, which is skipped without it — promoting "
                         "an account is a database operation this harness has no "
                         "access to, and a skipped check is honest where a faked "
                         "one is not.")
    args = ap.parse_args()

    run_id = uuid.uuid4().hex[:12]
    api = Api(args.base)
    r = Result()
    made = Created()

    print(f"target : {args.base}")
    print(f"run id : {run_id}   (every created row carries '{MARKER}{run_id}')")

    cleanup_ok = True
    try:
        if args.phase in ("anonymous", "all"):
            anonymous_phase(api, r)
        if args.phase in ("user", "all"):
            user_phase(api, r, made, run_id)
        if args.phase in ("moderator", "all"):
            if args.moderator_token:
                moderator_phase(api, r, made, run_id, args.moderator_token)
            else:
                print("\nMODERATOR\n  SKIPPED — no --moderator-token supplied.")
    finally:
        if made.users or made.reviews or made.questions:
            cleanup_ok = teardown(api, r, made)

    print(f"\n{r.passed} passed, {len(r.failed)} failed")
    for name in r.failed:
        print(f"  FAILED: {name}")
    if not cleanup_ok:
        print("\nCLEANUP FAILED — there is QA residue in production. Investigate now.")
        return 2
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
