"""Matplotlib rendering for the ranking scenarios -> docs/assets/ranking/*.png.

Headless `Agg` backend, so this runs in CI and over SSH. Output is deterministic:
the scenarios are seeded and PNG metadata is pinned, so re-running produces
byte-identical files and unrelated commits never show image churn.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must follow the backend selection)

from app.services.ranking import (  # noqa: E402
    GATE_WILSON_LB,
    VELOCITY_THRESHOLD,
)
from sim import scenarios as S  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "assets" / "ranking"

# Accessible categorical palette, consistent across every figure.
BLUE = "#2563eb"
RED = "#dc2626"
AMBER = "#d97706"
GREEN = "#059669"
GREY = "#94a3b8"
INK = "#1e293b"

PNG_METADATA = {"Software": "bluntly.ph ranking simulation"}


def _style() -> None:
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.edgecolor": "#cbd5e1",
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": "#64748b",
        "ytick.color": "#64748b",
        "grid.color": "#e2e8f0",
        # Framed legends: several panels shade their event window, and an
        # unframed legend over that shading is hard to read.
        "legend.frameon": True,
        "legend.facecolor": "white",
        "legend.framealpha": 0.92,
        "legend.edgecolor": "#e2e8f0",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def _save(fig, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.savefig(path, metadata=PNG_METADATA)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
def chart_small_n(result: S.SmallNResult) -> Path:
    """S1 — naive percentage is flat; Wilson earns its way up with evidence."""
    fig, ax = plt.subplots(figsize=(7.2, 4.0))

    ax.plot(result.counts, result.naive["100% positive"], color=RED,
            ls="--", lw=1.6, label="Naive % — 100% positive")
    ax.plot(result.counts, result.wilson["100% positive"], color=BLUE,
            lw=2.0, label="Wilson LB — 100% positive")
    ax.plot(result.counts, result.naive["95% positive"], color=AMBER,
            ls="--", lw=1.4, label="Naive % — 95% positive")
    ax.plot(result.counts, result.wilson["95% positive"], color=GREEN,
            lw=1.8, label="Wilson LB — 95% positive")

    # The rank flip that justifies the whole approach.
    lb5 = result.wilson_at("100% positive", 5)
    lb95 = result.wilson_at("95% positive", 100)
    ax.scatter([5, 100], [lb5, lb95], color=INK, zorder=5, s=28)
    ax.annotate(f"5/5 → {lb5:.3f}", xy=(5, lb5), xytext=(26, lb5 - 0.13),
                arrowprops={"arrowstyle": "->", "color": INK, "lw": 1},
                fontsize=8.5)
    ax.annotate(f"95/100 → {lb95:.3f}\n(ranks higher despite a lower %)",
                xy=(100, lb95), xytext=(110, lb95 - 0.22),
                arrowprops={"arrowstyle": "->", "color": INK, "lw": 1},
                fontsize=8.5)

    ax.set_xlabel("Votes cast (n)")
    ax.set_ylabel("Score used for feed ordering")
    ax.set_title("S1 — Wilson lower bound penalises small samples; a naive % does not")
    ax.set_ylim(0, 1.05)
    ax.set_xlim(0, result.max_n)
    ax.grid(True, lw=0.6)
    ax.legend(loc="lower right")
    return _save(fig, "wilson_small_n.png")


# --------------------------------------------------------------------------
def chart_brigade(result: S.BurstResult) -> Path:
    """S2 — 200 up-votes in 10 minutes, and what the homepage does about it."""
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.2, 6.0), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.18})

    ax1.axvspan(0, result.burst_minutes, color=RED, alpha=0.07,
                label=f"{result.burst_size} up-votes injected")
    ax1.plot(result.minutes, result.target_score, color=RED, lw=2.2,
             label="Brigaded review")
    ax1.plot(result.minutes, result.control_score, color=BLUE, lw=1.8,
             label="Organic control (40 votes / 30 days)")
    ax1.plot(result.minutes, result.cutoff, color=GREY, ls=":", lw=1.6,
             label=f"Homepage slot #{S.HOMEPAGE_SLOTS} cut-off")

    entry = result.minute_entering_homepage
    if entry is not None:
        idx = result.minutes.index(entry)
        ax1.scatter([entry], [result.target_score[idx]], color=INK, zorder=5, s=30)
        ax1.annotate(
            f"enters top {S.HOMEPAGE_SLOTS} at minute {entry:.0f}\n"
            f"rank {result.target_rank[0]} → {result.target_rank[-1]}",
            xy=(entry, result.target_score[idx]), xytext=(24, 0.78),
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 1}, fontsize=8.5)

    ax1.set_ylabel("Time-decayed Wilson score")
    ax1.set_title("S2 — A brigade of 200 up-votes reaches the homepage in about a minute")
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, lw=0.6)
    ax1.legend(loc="lower left")

    ax2.axvspan(0, result.burst_minutes, color=RED, alpha=0.07)
    ax2.plot(result.minutes, result.hourly_upvotes, color=AMBER, lw=2.0,
             label="Up-votes in the trailing hour")
    ax2.axhline(VELOCITY_THRESHOLD, color=INK, ls="--", lw=1.2,
                label=f"VELOCITY_THRESHOLD = {VELOCITY_THRESHOLD}")
    flagged = [m for m, f in zip(result.minutes, result.velocity_flag, strict=True) if f]
    if flagged:
        ax2.axvspan(min(flagged), max(flagged), color=AMBER, alpha=0.16,
                    label="velocity_exceeded() == True (advisory only)")
    ax2.set_xlabel("Minutes relative to the start of the burst")
    ax2.set_ylabel("Up-votes / hour")
    ax2.grid(True, lw=0.6)
    ax2.legend(loc="center right")
    return _save(fig, "brigade_burst.png")


# --------------------------------------------------------------------------
def chart_decay(result: S.DecayResult) -> Path:
    """S3 — the 45-day half-life hands the crown over with no new champion votes."""
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.2, 6.0), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.18})

    ax1.plot(result.days, result.champion_score, color=BLUE, lw=2.2,
             label="Champion — 100 votes, all on day 0, none since")
    ax1.plot(result.days, result.challenger_score, color=GREEN, lw=2.2,
             label="Challenger — 1 vote/day, same 95% positive rate")

    day = result.crossover_day
    if day is not None:
        ax1.axvline(day, color=INK, ls="--", lw=1.1)
        ax1.scatter([day], [result.challenger_score[day]], color=INK, zorder=5, s=30)
        ax1.annotate(f"crossover: day {day}\n(no new champion votes needed)",
                     xy=(day, result.challenger_score[day]),
                     xytext=(day + 8, result.challenger_score[day] - 0.20),
                     arrowprops={"arrowstyle": "->", "color": INK, "lw": 1},
                     fontsize=8.5)

    ax1.set_ylabel("Time-decayed Wilson score")
    ax1.set_title("S3 — Recency decay reorders the feed without a single new vote")
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, lw=0.6)
    ax1.legend(loc="lower right")

    ax2.plot(result.days, result.champion_effective_n, color=BLUE, lw=1.8,
             label="Champion effective n")
    ax2.plot(result.days, result.challenger_effective_n, color=GREEN, lw=1.8,
             label="Challenger effective n")
    ax2.axhline(45 / 0.6931471805599453, color=GREY, ls=":", lw=1.4,
                label="Steady-state ceiling = half-life / ln 2 ≈ 64.9")
    ax2.set_xlabel("Simulated days")
    ax2.set_ylabel("Effective n (sum of decay weights)")
    ax2.grid(True, lw=0.6)
    ax2.legend(loc="upper right")
    return _save(fig, "decay_handover.png")


# --------------------------------------------------------------------------
def chart_raid(result: S.RaidResult) -> Path:
    """S4 — a down-vote raid buries a good review and trips no signal at all."""
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.2, 6.0), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.18})

    ax1.axvspan(0, result.raid_minutes, color=RED, alpha=0.07,
                label=f"{result.raid_size} down-votes injected")
    ax1.plot(result.minutes, result.score, color=RED, lw=2.2,
             label="Raided review (was 80 up / 5 down)")
    ax1.plot(result.minutes, result.cutoff, color=GREY, ls=":", lw=1.6,
             label=f"Homepage slot #{S.HOMEPAGE_SLOTS} cut-off")
    ax1.axhline(GATE_WILSON_LB, color=AMBER, ls="--", lw=1.3,
                label=f"GATE_WILSON_LB = {GATE_WILSON_LB}")

    below = result.minute_below_gate
    if below is not None:
        idx = result.minutes.index(below)
        ax1.scatter([below], [result.score[idx]], color=INK, zorder=5, s=30)
        ax1.annotate(
            f"below the earn-eligible gate\nat minute {below:.0f}   "
            f"(rank {result.rank[0]} → {result.rank[-1]})",
            xy=(below, result.score[idx]), xytext=(16, 0.40),
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 1}, fontsize=8.5)

    ax1.set_ylabel("Time-decayed Wilson score")
    ax1.set_title("S4 — A down-vote raid buries the review; no fraud signal fires")
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, lw=0.6)
    ax1.legend(loc="upper right")

    ax2.axvspan(0, result.raid_minutes, color=RED, alpha=0.07)
    ax2.plot(result.minutes, result.hourly_downvotes, color=RED, lw=2.0,
             label="Down-votes in the trailing hour")
    ax2.axhline(VELOCITY_THRESHOLD, color=INK, ls="--", lw=1.2,
                label=f"VELOCITY_THRESHOLD = {VELOCITY_THRESHOLD} (up-votes only)")
    ax2.plot(result.minutes, [int(f) for f in result.velocity_flag], color=GREEN,
             lw=2.4, label="velocity_exceeded() — flat False throughout")
    ax2.set_xlabel("Minutes relative to the start of the raid")
    ax2.set_ylabel("Down-votes / hour")
    ax2.grid(True, lw=0.6)
    ax2.legend(loc="center right")
    return _save(fig, "downvote_raid.png")


# --------------------------------------------------------------------------
def render_all() -> list[Path]:
    """Regenerate every figure. Returns the written paths in document order."""
    _style()
    return [
        chart_small_n(S.small_n_vs_large_n()),
        chart_brigade(S.brigade_burst()),
        chart_decay(S.decay_handover()),
        chart_raid(S.downvote_raid()),
    ]
