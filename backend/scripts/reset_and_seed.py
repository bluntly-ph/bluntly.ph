"""DANGER — destructive. Reset the database to a clean, curated, working state.

What it does, in order:
  1. TRUNCATE every content/activity table (reviews, products, Q&A, requests,
     tokens, payouts, sessions, …). Keeps config: badges, membership_tiers,
     alembic_version.
  2. Delete every synthetic user, keeping only real accounts (@gmail.com).
  3. Promote bluntly.ph@gmail.com to moderator (the platform superadmin).
  4. Reseed a small, realistic, fully working dataset (authors, products,
     published + monetized reviews, a seller, Q&A, and review requests).

Run: python -m scripts.reset_and_seed
"""

from __future__ import annotations

from sqlalchemy import text

from app.db.session import SessionLocal
from scripts import seed_showcase

# Content + activity — everything that is seeded/generated, never config.
_WIPE = (
    "review_votes, earn_eligible_votes, referral_links, review_versions, "
    "reviews, product_platforms, price_history, products, answers, questions, "
    "seller_reviews, request_upvotes, review_requests, review_contracts, "
    "payouts, commissions, honesty_fund_distributions, token_transactions, "
    "moderation_logs, sessions, user_badges, email_otps"
)

_SELLER = """
INSERT INTO public.users
  (id, user_id, email, username, display_name, role, member_type, trust_stage,
   seller_trust_score, seller_aggregates)
VALUES
  ('00000000-0000-0000-0000-0000000f0001','usr_show_seller',
   'seller@showcase.bluntly.ph','techhaven','TechHaven PH','seller','seller',2,
   0.87000,
   '{"count":42,"accuracy_pct":95,"completeness_pct":92,
     "customer_service_avg":4.6,"packaging_avg":4.8,"recommend_pct":94}'::jsonb)
ON CONFLICT (id) DO NOTHING;
"""

_QA = """
INSERT INTO public.questions (id, question_id, product_id, asker_id, body, directed_to)
VALUES
 ('00000000-0000-0000-0000-0000000f1001','qst_show_0001',
  '00000000-0000-0000-0000-0000000d0001','00000000-0000-0000-0000-0000000c0003',
  'How loud is it on the highest speed? Planning to use it in a quiet office.',
  'buyers'::question_directed_to),
 ('00000000-0000-0000-0000-0000000f1002','qst_show_0002',
  '00000000-0000-0000-0000-0000000d0002','00000000-0000-0000-0000-0000000c0003',
  'Is the 8GB base model enough for photo editing, or should I get 16GB?',
  'buyers'::question_directed_to)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.answers
 (id, answer_id, question_id, responder_id, body, is_best_answer,
  is_first_responder, helpful_votes, wilson_score)
VALUES
 ('00000000-0000-0000-0000-0000000f2001','ans_show_0001',
  '00000000-0000-0000-0000-0000000f1001','00000000-0000-0000-0000-0000000c0001',
  'On speed 3 it''s noticeable — about like a small desk fan. Speeds 1 and 2 are quiet enough for an office.',
  true,true,340,0.94000),
 ('00000000-0000-0000-0000-0000000f2002','ans_show_0002',
  '00000000-0000-0000-0000-0000000f1001','00000000-0000-0000-0000-0000000c0002',
  'I use mine at my desk on speed 1 all day and barely hear it.',false,false,120,0.80000),
 ('00000000-0000-0000-0000-0000000f2003','ans_show_0003',
  '00000000-0000-0000-0000-0000000f1002','00000000-0000-0000-0000-0000000c0002',
  'For Lightroom and light Photoshop 8GB works, but you''ll feel it with many tabs. If you can stretch to 16GB, do it — it ages much better.',
  true,true,510,0.96000)
ON CONFLICT (id) DO NOTHING;

UPDATE public.questions SET best_answer_id='00000000-0000-0000-0000-0000000f2001'
 WHERE id='00000000-0000-0000-0000-0000000f1001';
UPDATE public.questions SET best_answer_id='00000000-0000-0000-0000-0000000f2003'
 WHERE id='00000000-0000-0000-0000-0000000f1002';
"""

_REQUESTS = """
INSERT INTO public.review_requests
 (id, request_id, requester_id, title, details, bounty, status, upvote_count, expires_at)
VALUES
 ('00000000-0000-0000-0000-0000000f3001','req_show_1','00000000-0000-0000-0000-0000000c0003',
  'Is the Ugreen Nexode 100W worth it over Anker?',
  'Real-world charging speed and heat after a few weeks — does it actually hit 100W on a laptop, and how hot does it get?',
  120,'open',34,now()+interval '14 days'),
 ('00000000-0000-0000-0000-0000000f3002','req_show_2','00000000-0000-0000-0000-0000000c0001',
  'Best budget mechanical keyboard under PHP 2,000?',
  'Looking for something quiet-ish for an office with good build. Membrane vs mechanical at this price?',
  80,'open',22,now()+interval '14 days'),
 ('00000000-0000-0000-0000-0000000f3003','req_show_3','00000000-0000-0000-0000-0000000c0002',
  'Does the Xiaomi Robot Vacuum handle pet hair?',
  'Two cats, lots of shedding. Does it clog, and how often do you empty the bin?',
  150,'open',41,now()+interval '14 days'),
 ('00000000-0000-0000-0000-0000000f3004','req_show_4','00000000-0000-0000-0000-0000000c0003',
  'Honest take on the Oraimo FreePods 4?',
  'Are they actually good for calls in noisy places, and how is the battery after a few months?',
  60,'open',9,now()+interval '14 days'),
 ('00000000-0000-0000-0000-0000000f3005','req_show_5','00000000-0000-0000-0000-0000000c0001',
  'Which sunscreen actually works for oily skin in PH heat?',
  'Non-greasy, no white cast, survives commuting. What do you actually re-buy?',
  90,'open',28,now()+interval '14 days')
ON CONFLICT (id) DO NOTHING;
"""


def run() -> None:
    db = SessionLocal()
    try:
        print("Wiping content + activity…")
        db.execute(text(f"TRUNCATE {_WIPE} CASCADE"))
        print("Removing synthetic users (keeping real @gmail.com accounts)…")
        removed = db.execute(
            text("DELETE FROM public.users WHERE email NOT LIKE '%@gmail.com'")
        ).rowcount
        print(f"  removed {removed} synthetic users")
        print("Promoting bluntly.ph@gmail.com to moderator (superadmin)…")
        db.execute(text(
            "UPDATE public.users SET role='moderator', member_type='moderator' "
            "WHERE email='bluntly.ph@gmail.com'"
        ))
        db.commit()
    finally:
        db.close()

    print("Seeding authors / products / reviews…")
    seed_showcase.seed()

    print("Seeding seller / Q&A / requests…")
    db = SessionLocal()
    try:
        db.execute(text(_SELLER))
        db.execute(text(_QA))
        db.execute(text(_REQUESTS))
        db.commit()
    finally:
        db.close()

    print("Reset + seed complete.")


if __name__ == "__main__":
    run()
