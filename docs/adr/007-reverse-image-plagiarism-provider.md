# ADR-007: Reverse-image-search & plagiarism provider (build, on-platform)

- **Status:** Accepted (M0), implementation M2
- **Context (PRD A3, Architecture §8 Q5):** Providers are unnamed. Sending user
  proof photos to a third party triggers a privacy assessment under RA 10173.

## Decision
**Build on-platform, no third-party photo egress** for the launch:

- **Plagiarism / AI-mirroring (fraud layer 2):** Postgres **`pg_trgm`** trigram
  similarity + **RapidFuzz** against the pre-seeded description/pattern database.
  Runs in-database / in-process; no data leaves the platform. This is the interim
  fuzzy matcher the spec anticipates replacing with an NLP classifier later (M5).
- **Reverse-image (fraud layer 3):** **perceptual hashing** (pHash via
  `imagehash`) computed on upload and compared against previously stored proof
  photos to catch reuse, plus EXIF metadata inconsistency checks. All local.

An **external** reverse-image service (Google Vision, TinEye) is explicitly **not**
adopted now precisely because it would export user photos and require a formal
privacy assessment. If ever adopted, that assessment becomes a prerequisite.

## Consequences
Lower recall than a global reverse-image index, but zero third-party PII exposure
and no per-call cost. All signals are **advisory** to the human moderator (never
auto-blocking), consistent with FR-8.
