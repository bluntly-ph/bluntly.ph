# Lazada affiliate integration

Shopee stays on the manual CSV import. Lazada has both a postback and a signed
Open API, so it is the one platform we can automate — but the two mechanisms are
**not** interchangeable and the difference decides what each is allowed to do.

| | Postback | `/marketing/conversion/report` |
|---|---|---|
| Direction | Lazada pushes, D+1 | we pull, on demand |
| Authentication | a shared secret in the URL | HMAC-SHA256 with the app secret |
| Can it be forged? | **yes**, by anyone who sees the URL | no |
| Therefore | evidence only — audit + funnel status | **source of truth → `commissions`** |

Lazada's macro list contains no request signature. A postback URL appears in
their dashboard, travels in query strings, and lands in access logs; it is not a
credential you can rotate quietly. So a postback records *what Lazada claimed*
and nothing more. Money comes from the signed API, which is also the only source
that reports an order going `Returned` after the fact.

---

## 1. Generate the postback secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put it in the environment as `LAZADA_POSTBACK_SECRET` — Vercel project settings
for production, `.env` locally (already gitignored). Anything under 32 characters
is refused by `settings.production_issues()`.

## 2. Fill in the Lazada Adsense form

- **Name:** `bluntly.ph`
- **Type:** **Order** — the other five (Add to Cart, PDP View, App Visit) are
  engagement events that never become commission. Only add them if you later
  want funnel analytics.
- **PostBack URL:** one line, no spaces, `<SECRET>` from `.env`:

```
https://bluntly.ph/api/v1/postback/lazada?t=<SECRET>&c={sub_id2}&r={sub_id1}&o={_p_transaction}&so={_p_sub_transaction}&s={_p_status}
```

Replace `bluntly.ph` with whatever domain the Vercel deployment answers on.
`vercel.json` routes `/api/v1/*` to the FastAPI service, so this reaches the
backend without any extra hosting.

### Why the URL cannot just be `/postback/lazada`

Lazada does not POST a body. It performs a GET against **exactly the string you
registered**, textually replacing each `{...}` macro with a value — and it
substitutes only the macros literally present in that string. There is no "send
me everything" mode. A bare `/postback/lazada` would therefore arrive carrying
nothing at all: no order, no attribution, no status, just a ping saying something
happened somewhere.

So the macros have to be in the URL. The **parameter names**, though, are ours,
which is why the form above uses one-letter aliases — roughly half the length,
same data. Both spellings work permanently:

| Short | Long | Macro |
|---|---|---|
| `t` | `token` | *(our secret)* |
| `c` | `click_ref` | `{sub_id2}` |
| `r` | `review_sub_id` | `{sub_id1}` |
| `o` | `order_id` | `{_p_transaction}` |
| `so` | `sub_order_id` | `{_p_sub_transaction}` |
| `s` | `status` | `{_p_status}` |

Optional extras, same pattern: `p`/`payout`, `a`/`amount`, `cur`/`currency`,
`ot`/`order_type`, `at`/`attribution`, `ct`/`conversion_time`.

**Why these six are the floor:**

| Parameter | Why it cannot be dropped |
|---|---|
| `token` | the only authentication that exists |
| `sub_order_id` | the idempotency key — Lazada retries, and the per-item sub-order is the finest grain they report |
| `click_ref` | per-click attribution; without it a conversion is only traceable to a review, which the CSV already gave us |
| `status` | one order fires repeatedly as it moves `Fulfilled → Delivered → Returned`; without it a returned order stays counted |
| `order_id` | groups sub-orders into the customer's actual order |
| `review_sub_id` | fallback attribution when `click_ref` misses (link built before per-click tagging, or hand-made by a moderator) |

**Money figures are deliberately absent.** `{_p_payout}`, `{_p_pay_amount}` and
`{_p_currency}` were in the first draft of this URL and are gone, because the
postback is not allowed to create commissions anyway — the signed conversion
report supplies those numbers, and it is the one source that can be trusted with
them. Carrying unverifiable amounts through a forgeable channel adds length and
invites someone to reconcile against them by mistake.

Every parameter beyond the token is optional in the handler, so append these if
you want richer audit rows before the signed sync is wired up:

```
...&p={_p_payout}&a={_p_pay_amount}&cur={_p_currency}&at={_p_attribution_type}
```

**Do not use `{sub_aff_id}` as the click id.** Lazada reserves it for
sub-affiliate channels and their troubleshooting note #4 calls this out
explicitly; use `sub_id1`–`sub_id6`, as above.

## 3. Nothing to do for tracking links

The redirect decorates them at click time. `GET /r/{review_id}` appends:

- `sub_id1` = the review's sub-ID (`blt_<review>`) — survives into the monthly report
- `sub_id2` = a **per-click** ref (`ref_<random>`) — the new part

Review-level attribution is all the CSV ever gave us. `sub_id2` is what turns a
conversion into *this person clicked at this moment*. If a moderator already
typed a `sub_id1` into the Lazada dashboard when generating the link, theirs
wins — overwriting it would break the reporting on their side.

## 4. Test it

Use **Run Test** in Adsense. It sends mock `test_XXX` values, and their guide
warns that a server which validates them looks broken — so the endpoint
acknowledges the test and writes nothing:

```json
{"status": "ok", "mode": "test"}
```

Then place a small real order through a `/r/{review_id}` link. Postbacks arrive
**D+1**, not immediately.

## 5. Open API credentials

`LAZADA_APP_KEY`, `LAZADA_APP_SECRET`, `LAZADA_USER_TOKEN`, and optionally
`LAZADA_API_BASE` (defaults to `https://api.lazada.com.ph/rest`). API access is
approved within ~5 working days.

Available once configured (`app/adapters/lazada.py`):

- `fetch_conversions(date_start, date_end)` — paginated conversion report; the
  signed source that may create commissions
- `get_tracking_links([product_url], sub_id1=..., sub_id2=...)` — batch link
  generation, so a moderator can monetise a Lazada review without leaving the
  queue. Capped at 100 URLs; the 400 QPS ceiling is shared across all six Lazada
  country sites and they throttle abusers.

---

## What is deliberately NOT built

**Automatic commission creation from postbacks.** A forged GET would mint money.
Postbacks set `sessions.conversion_status` and write an `affiliate_postbacks`
row; `reconciled_commission_id` links to the commission once a signed source
confirms it.

**The scheduled conversion sync.** `fetch_conversions` works and is tested, but
nothing calls it on a timer yet, and the reconciliation that turns a `Conversion`
into a `Commission` — matching `subId2` back to a session, applying the 40/30/30
split, handling an order that later returns — is the remaining work. Until then
Lazada commissions still come from the CSV import, exactly like Shopee.

That ordering is deliberate: the postback gives immediate visibility with no
money at risk, and the money path lands only when it can be reconciled properly.

## Security notes

- The secret is compared with `secrets.compare_digest` and **fails closed** when
  unset — an unconfigured secret rejects everything rather than accepting it.
- `token` is stripped before the payload is persisted, so the secret never lands
  in `affiliate_postbacks.raw`.
- Idempotent on `(platform, external_sub_order_id)`; retries and replays cannot
  double-count.
- A malformed amount is stored as `NULL` rather than raising — a 500 here reads
  as a broken integration on Lazada's side.
- The endpoint is public by necessity. It creates no money, mutates no wallet,
  and the worst a valid-token forgery achieves is a false conversion row visible
  to admins and contradicted by the signed report.
