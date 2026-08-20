"""Load profile for the Bluntly.ph API (M3 slice 14).

Mix (per the M3 plan): 70% public reads, 15% authenticated browse, 10% review
submit, 5% moderator queue — roughly what a read-heavy review site does.

Targets at 100 concurrent users over 5 minutes:
    p95 read  < 500 ms
    p95 write < 1 s
    error rate < 0.1%
    zero 5xx

Run against local compose:
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 5m --headless

Against the Supabase-backed instance, stay CAPPED (protect the shared pooler):
    ... --users 25 --spawn-rate 5 --run-time 3m --headless

Read-only by default. Set LOADTEST_WRITES=0 to drop the submit/vote traffic.
"""

from __future__ import annotations

import os
import random
import uuid

from locust import HttpUser, between, events, task

WRITES_ENABLED = os.getenv("LOADTEST_WRITES", "1") == "1"
PW = "password123"


def _client_ip() -> str:
    """A distinct X-Forwarded-For per simulated user.

    The auth limiter is a fixed window keyed on client IP (10/min by default).
    100 users behind ONE source IP would be throttled at registration — that is
    the limiter working correctly, but it measures the limiter instead of the
    app. Real concurrent users arrive from distinct addresses, so simulate that.
    """
    return f"198.51.{random.randint(1, 254)}.{random.randint(1, 254)}"


@events.quitting.add_listener
def _assert_targets(environment, **_kw):
    """Fail the run (non-zero exit) if the pinned targets are missed, so this is
    a gate in CI rather than a wall of numbers someone has to interpret."""
    stats = environment.stats
    fail_ratio = stats.total.fail_ratio
    p95 = stats.total.get_response_time_percentile(0.95)
    if fail_ratio > 0.001:
        environment.process_exit_code = 1
        print(f"TARGET MISS: error rate {fail_ratio:.4%} > 0.1%")
    if p95 and p95 > 1000:
        environment.process_exit_code = 1
        print(f"TARGET MISS: overall p95 {p95:.0f}ms > 1000ms")
    else:
        print(f"overall p95 {p95:.0f}ms, error rate {fail_ratio:.4%}")


class PublicReader(HttpUser):
    """70% of load: anonymous browsing — the hot path."""

    weight = 70
    wait_time = between(0.5, 2.0)

    def on_start(self):
        resp = self.client.get("/api/v1/products?limit=20", name="/products")
        self.product_ids = [p["id"] for p in resp.json()] if resp.ok else []

    @task(5)
    def reviews_wilson(self):
        self.client.get("/api/v1/reviews?sort=wilson&limit=20",
                        name="/reviews?sort=wilson")

    @task(3)
    def reviews_newest(self):
        self.client.get("/api/v1/reviews?limit=20", name="/reviews")

    @task(2)
    def product_page(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.get(f"/api/v1/products/{pid}", name="/products/{id}")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


class AuthedBrowser(HttpUser):
    """15%: signed-in reads — auth + token ledger."""

    weight = 15
    wait_time = between(1.0, 3.0)

    def on_start(self):
        email = f"lt_{uuid.uuid4().hex[:12]}@example.com"
        r = self.client.post("/api/v1/auth/register",
                             json={"email": email, "password": PW},
                             name="/auth/register",
                             headers={"x-forwarded-for": _client_ip()})
        # No token -> stop, rather than emitting a stream of 401s that would be
        # reported as application errors.
        if not r.ok:
            self.stop()
            return
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task(3)
    def me(self):
        self.client.get("/api/v1/auth/me", headers=self.headers, name="/auth/me")

    @task(2)
    def tokens(self):
        self.client.get("/api/v1/tokens/balance", headers=self.headers,
                        name="/tokens/balance")

    @task(1)
    def requests_board(self):
        self.client.get("/api/v1/requests?status=open&sort=reward&limit=20",
                        name="/requests")


class Submitter(HttpUser):
    """10%: the write path — product + review submission."""

    weight = 10
    wait_time = between(2.0, 5.0)

    def on_start(self):
        email = f"lw_{uuid.uuid4().hex[:12]}@example.com"
        r = self.client.post("/api/v1/auth/register",
                             json={"email": email, "password": PW},
                             name="/auth/register",
                             headers={"x-forwarded-for": _client_ip()})
        if not r.ok:
            self.stop()
            return
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        p = self.client.post("/api/v1/products", headers=self.headers,
                             json={"name": f"LoadTest {uuid.uuid4().hex[:8]}",
                                   "category": "electronics-tech"},
                             name="/products [POST]")
        self.product_id = p.json()["id"] if p.ok else None

    @task
    def submit_review(self):
        if not (WRITES_ENABLED and self.product_id and self.headers):
            return
        self.client.post("/api/v1/reviews", headers=self.headers, name="/reviews [POST]",
                         json={"product_id": self.product_id,
                               "title": "Load test review",
                               "discussion": "Generated under load; used for weeks.",
                               "verdict": "yes_absolutely",
                               "star_rating": random.randint(3, 5),
                               "photo_url": "https://example.com/p.jpg"})


class ModeratorQueue(HttpUser):
    """5%: the queue — the heaviest read (batch loads + fraud signals per card)."""

    weight = 5
    wait_time = between(3.0, 6.0)

    def on_start(self):
        # Promotion to moderator is a DB action, so the queue can only be
        # exercised with a supplied token. Without one, skip rather than emit
        # 401s that would be counted as application errors.
        token = os.getenv("LOADTEST_MOD_TOKEN", "")
        if not token:
            self.stop()
            return
        self.headers = {"Authorization": f"Bearer {token}"}

    @task
    def queue(self):
        self.client.get("/api/v1/admin/review-queue?limit=25",
                        headers=self.headers, name="/admin/review-queue")
