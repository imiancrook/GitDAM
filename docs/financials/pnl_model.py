#!/usr/bin/env python3
"""
GitDAM revenue model and 36-month P&L.

Run:  python3 docs/financials/pnl_model.py [--csv]

What it does
------------
1. Proposes three pricing tiers (Solo / Studio / Studio Plus) that obey the
   VISION.md pricing principles: storage-based, guests free and unlimited,
   bandwidth included, no feature paywalls, published and stable.
2. Sanity-checks the Studio price against what the reference agency
   (WORKFLOWS.md s13 / PERSONAS.md: 15 people, 8 designers, 2 video editors,
   1 contract photographer, 3 client projects) pays today for
   Dropbox Business + Frame.io + a review tool.
3. Cross-checks the per-customer-month COGS placeholders ($60/$90/$140) against
   a bottom-up storage estimate for the LIGHT / BASE / HEAVY workloads, with
   whole-file dedup only and with chunk-level dedup.  This block exists so the
   infra model (built in parallel) has something concrete to reconcile with.
4. Runs three 36-month scenarios (BEAR / BASE / BULL) with cohort-level
   customer counts, tier mix, churn, storage-overage expansion, tier
   right-sizing, gross margin, breakeven against a placeholder burn, and
   cumulative cash need.  Computes ARPA, CAC, payback and LTV/CAC.

Every number that was not fetched from a live source is labelled in the
ASSUMPTIONS table below.  Outbound fetches to dropbox.com, frame.io,
ziflow.com and aws.amazon.com were attempted on 2026-09-29 and blocked by the
environment's egress proxy (HTTP 403 on CONNECT), so all vendor and AWS prices
are "list price as of knowledge cutoff (mid-2026), verify".

All figures USD.  Fractional customers are expected values, not people.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, field

MODEL_DATE = "2026-09-29"
KNOWLEDGE_CAVEAT = "list price as of knowledge cutoff (mid-2026), verify"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# 1. ASSUMPTIONS (one table, every row has a source or "estimate")
# --------------------------------------------------------------------------

ASSUMPTIONS: list[tuple[str, str, str]] = []


def A(name: str, value, source: str):
    """Register an assumption and return its value."""
    ASSUMPTIONS.append((name, str(value), source))
    return value


# ---- Tiers -----------------------------------------------------------------
# Principles (VISION.md "Pricing principles"): storage-based, free unlimited
# guests, bandwidth included with overage at cost and shown ahead, no feature
# paywalls (explorations, reviews, releases, Git access, desktop client in every
# plan), tiers differ by storage, retention and support.
#
# Billable unit decision: "stored GB" means LIVE GB = bytes reachable from the
# main line of every project plus releases plus pinned explorations.  Version
# history inside the tier's retention window is INCLUDED, not billed.  This is
# the only reading under which "tiers differ by retention" is a benefit rather
# than a cost to the customer, and it mirrors how Dropbox and Adobe price
# history.  Consequence: auto-snapshot history is a COGS risk carried by
# GitDAM, which is exactly STRESS_TEST A2/F2, quantified in section 3.


@dataclass
class Tier:
    name: str
    monthly_usd: float
    storage_gb: float        # included live GB
    egress_gb: float         # included egress GB per month
    retention_days: int      # auto-snapshot retention (milestones/releases: forever)
    persona: str
    extras: str


TIERS: dict[str, Tier] = {
    "Solo": Tier(
        "Solo",
        A("Solo price $/mo", 19, "estimate; at/below Dropbox Professional ($19.99/mo annual, " + KNOWLEDGE_CAVEAT + "); PERSONAS s5 churn risk 'price above a Dropbox subscription'"),
        A("Solo included live GB", 250, "estimate; Lena's layered PSDs + exports for 3-5 clients"),
        A("Solo included egress GB/mo", 750, "estimate; 3x included storage, VISION 'generous egress allowance per stored GB'"),
        A("Solo auto-snapshot retention days", 30, "DESIGN s11 default squash window"),
        "Lena (illustrator / freelancer, one-person org, P2)",
        "Unlimited guests, releases, approval records, desktop client, Git access",
    ),
    "Studio": Tier(
        "Studio",
        A("Studio price $/mo", 299, "estimate; inside the reference agency's current stack spend (section 2); ~$0.15/GB, at Unity VCS's $0.14/GB ("+KNOWLEDGE_CAVEAT+"), RESEARCH s5"),
        A("Studio included live GB", 2000, "estimate; covers LIGHT 200 GB, BASE 500 GB and HEAVY 1.5 TB starting points with headroom"),
        A("Studio included egress GB/mo", 6000, "estimate; 3x included storage"),
        A("Studio auto-snapshot retention days", 90, "estimate; tier differentiator per VISION 'tiers differ by storage, retention and support'"),
        "Rachel's 10-20 person agency (P1 buyer); Maya, Priya, Theo as users",
        "Everything in Solo + 90-day history, protected folders, audit CSV, email support",
    ),
    "Plus": Tier(
        "Plus",
        A("Studio Plus price $/mo", 899, "estimate; ~$0.11/GB; below Artstash's $800-2,500 flat tiers for previews-only ("+KNOWLEDGE_CAVEAT+"), RESEARCH s5"),
        A("Plus included live GB", 8000, "estimate; 30-60 person studios with video and game art"),
        A("Plus included egress GB/mo", 24000, "estimate; 3x included storage"),
        A("Plus auto-snapshot retention days", 365, "estimate; tier differentiator"),
        "30-60 person studios; Sam (technical artist), Marcus (IT/procurement) as gate",
        "Everything in Studio + SSO/SCIM, 365-day history, priority support, higher Git/CI rate limits",
    ),
}
TIER_ORDER = ["Solo", "Studio", "Plus"]

OVERAGE_STORAGE_PER_GB_MO = A("Storage overage $/GB-month", 0.10,
                              "estimate; between GitHub LFS $0.07/GiB and Unity VCS $0.14/GB ("+KNOWLEDGE_CAVEAT+"); ~4x S3 Standard list")
OVERAGE_EGRESS_PER_GB = A("Egress overage $/GB", 0.08,
                          "estimate; 'priced at cost' = CloudFront first-10-TB list ~$0.085/GB ("+KNOWLEDGE_CAVEAT+")")

# ---- COGS placeholders (from the task; infra model reconciles) --------------
COGS_PLACEHOLDER = {
    "Solo": A("COGS $/customer-month Solo (PLACEHOLDER)", 60, "task placeholder; RECONCILE with infra model"),
    "Studio": A("COGS $/customer-month Studio (PLACEHOLDER)", 90, "task placeholder; RECONCILE with infra model"),
    "Plus": A("COGS $/customer-month Plus (PLACEHOLDER)", 140, "task placeholder; RECONCILE with infra model"),
}

# ---- Burn placeholders (from the task) --------------------------------------
BURN_BY_MONTH = {
    (1, 12): A("Burn $/mo months 1-12 (PLACEHOLDER)", 95_000, "task placeholder; RECONCILE"),
    (13, 24): A("Burn $/mo months 13-24 (PLACEHOLDER)", 140_000, "task placeholder; RECONCILE"),
    (25, 36): A("Burn $/mo months 25-36 (PLACEHOLDER)", 180_000, "task placeholder; RECONCILE"),
}
BURN_BEYOND_36 = 180_000  # held flat when extrapolating breakeven past the plan
REVENUE_START_MONTH = A("First revenue month", 10, "task: end of Phase 2 (VISION roadmap Phases 0-2)")
HORIZON = 36
EXTRAPOLATE_TO = 96      # only used to locate a breakeven month beyond 36

# ---- Workload profiles for cohorts (live GB drives the bill) ---------------
# (start live GB, live growth GB/month, monthly egress as multiple of live GB)
@dataclass
class Workload:
    name: str
    live_gb: float
    live_growth_gb_mo: float
    egress_mult: float


WL_LIGHT = Workload("LIGHT", A("LIGHT live GB", 200, "task"), A("LIGHT live growth GB/mo", 5, "estimate; DESIGN s11 'designers 5 GB/month' of new deliverables"), A("LIGHT egress x live GB/mo", 0.5, "estimate; desktop pulls of colleagues' files + client release downloads"))
WL_BASE = Workload("BASE", A("BASE live GB", 500, "task"), A("BASE live growth GB/mo", 25, "task: 20 GB renders/mo (kept on main line) + 5 GB design"), A("BASE egress x live GB/mo", 0.5, "estimate"))
WL_HEAVY = Workload("HEAVY", A("HEAVY live GB", 1500, "task"), A("HEAVY live growth GB/mo", 325, "task: 4 shoots x 3,000 RAW x 25 MB = 300 GB/mo + 25 GB video/design"), A("HEAVY egress x live GB/mo", 0.4, "estimate; RAWs are pulled rarely"))
WL_SOLO = Workload("SOLO", A("Solo customer live GB", 80, "estimate"), A("Solo live growth GB/mo", 4, "estimate"), A("Solo egress x live GB/mo", 0.5, "estimate"))
WL_PLUS = Workload("PLUS", A("Plus customer live GB", 3000, "estimate; 30-60 person studio"), A("Plus live growth GB/mo", 150, "estimate"), A("Plus egress x live GB/mo", 0.4, "estimate"))

STUDIO_WORKLOAD_MIX = {
    WL_LIGHT.name: A("Studio cohort mix LIGHT", 0.40, "estimate; Maya-first release (ASSUMPTIONS decision 1)"),
    WL_BASE.name: A("Studio cohort mix BASE", 0.40, "estimate"),
    WL_HEAVY.name: A("Studio cohort mix HEAVY", 0.20, "estimate; Ana is P2"),
}
WORKLOADS = {w.name: w for w in (WL_LIGHT, WL_BASE, WL_HEAVY, WL_SOLO, WL_PLUS)}

# ---- Scenarios -------------------------------------------------------------
@dataclass
class Scenario:
    name: str
    new_at_start: float          # new customers/month at month 10
    new_growth_mo: float         # compounding monthly growth in new-customer rate
    churn_mo: float              # monthly logo churn, all tiers
    tier_mix: dict               # share of new customers by tier
    paid_marketing_mo: float     # $ per month, inside the burn placeholder
    growth_labour_mo: float      # $ per month of founder/growth time attributed to S&M


SCENARIOS = [
    Scenario("BEAR",
             A("BEAR new customers/mo at m10", 1.5, "estimate; word of mouth + a small paid budget, no cross-org loop"),
             A("BEAR new-customer rate growth/mo", 0.04, "estimate"),
             A("BEAR monthly logo churn", 0.03, "task; ~31%/yr, SMB self-serve benchmark 3-5%/mo for sub-$5k ACV (estimate)"),
             {"Solo": A("BEAR mix Solo", 0.50, "estimate; PLG skews to freelancers when agencies hesitate (A3)"), "Studio": A("BEAR mix Studio", 0.45, "estimate"), "Plus": A("BEAR mix Plus", 0.05, "estimate")},
             A("BEAR paid marketing $/mo", 6_000, "estimate; 'modest'"),
             A("Growth labour attributed to S&M $/mo", 5_000, "estimate; ~0.4 FTE of founder time")),
    Scenario("BASE",
             A("BASE new customers/mo at m10", 3.0, "estimate"),
             A("BASE new-customer rate growth/mo", 0.07, "estimate; content + Adobe/Figma community + agency referrals"),
             A("BASE monthly logo churn", 0.02, "task; ~22%/yr, plausible once history and releases live in the product (switching cost)"),
             {"Solo": A("BASE mix Solo", 0.40, "estimate"), "Studio": A("BASE mix Studio", 0.50, "estimate; first-customer profile"), "Plus": A("BASE mix Plus", 0.10, "estimate")},
             A("BASE paid marketing $/mo", 8_000, "estimate"),
             5_000),
    Scenario("BULL",
             A("BULL new customers/mo at m10", 5.0, "estimate"),
             A("BULL new-customer rate growth/mo", 0.09, "estimate; cross-org delivery loop works (T10 passes)"),
             A("BULL monthly logo churn", 0.015, "task; ~17%/yr, mid-market-like retention from SSO'd Plus studios and annual contracts"),
             {"Solo": A("BULL mix Solo", 0.35, "estimate"), "Studio": A("BULL mix Studio", 0.50, "estimate"), "Plus": A("BULL mix Plus", 0.15, "estimate")},
             A("BULL paid marketing $/mo", 10_000, "estimate"),
             5_000),
]

# ---- AWS list prices for the COGS cross-check -------------------------------
S3_STANDARD_GB_MO = A("S3 Standard $/GB-month", 0.023, KNOWLEDGE_CAVEAT)
S3_IT_INFREQUENT = A("S3 Intelligent-Tiering Infrequent $/GB-month", 0.0125, KNOWLEDGE_CAVEAT)
S3_IT_ARCHIVE_INSTANT = A("S3 Intelligent-Tiering Archive Instant $/GB-month", 0.004, KNOWLEDGE_CAVEAT)
CLOUDFRONT_EGRESS_GB = A("CloudFront egress $/GB (first 10 TB, US/EU)", 0.085, KNOWLEDGE_CAVEAT)
HISTORY_TIER_MIX = (
    A("History bytes still Frequent", 0.30, "estimate; last-30-day auto-snapshots are re-read for restore/compare"),
    A("History bytes in Infrequent", 0.40, "estimate"),
    A("History bytes in Archive Instant", 0.30, "estimate"),
)
PREVIEW_OVERHEAD = A("Preview/proxy storage overhead", 0.02, "DESIGN s11 '~2%'")
OTHER_INFRA_PER_CUSTOMER = A("Non-storage infra $/customer-month (DynamoDB, Lambda, MediaConvert, OpenSearch share)", 8, "estimate; DESIGN s11 'rounding error' plus a shared OpenSearch domain")

# ---- Workload snapshot maths for the COGS cross-check ----------------------
PSD_GB = A("Designer working file GB", 2.0, "task")
SAVES_PER_DAY = A("Saves per designer per day", 20, "task")
SNAPSHOT_CAPTURE = A("Share of saves that become an auto-snapshot (10-min quiet rule)", 0.60, "estimate; saves come in bursts, so not every save is followed by 10 quiet minutes")
MILESTONES_PER_DAY = A("Explicit milestones per designer per day (kept forever)", 1, "estimate; WORKFLOWS 1.1 'at a stopping point'")
WORK_DAYS_PER_MONTH = A("Working days per month", 21, "estimate")
DESIGNERS = A("Designers (reference agency)", 8, "task")
EDITORS = A("Video editors (reference agency)", 2, "task")
PRPROJ_GB = A("Premiere/AE project file GB", 0.3, "estimate")
RENDERS_GB_MO = A("New video renders GB/month", 20, "task")
PROJECT_SYNC_GB = A("Video project sync GB (one-off, live)", 60, "task")
RAW_GB_MO = A("RAW ingest GB/month", 4 * 3000 * 0.025, "task: 4 shoots x 3,000 x 25 MB")
CHUNK_DEDUP = {
    "psd": A("Chunk-level dedup reduction on PSD versions", 0.60, "task"),
    "video": A("Chunk-level dedup reduction on video re-exports", 0.40, "task"),
    "raw": A("Chunk-level dedup reduction on RAW", 0.0, "task"),
}

# ---- Reference agency's stack today (section 2) -----------------------------
STACK_TODAY = [
    # (line, monthly $, note)
    ("Dropbox Business Standard, 12 paid seats x $15 (annual billing)", 12 * A("Dropbox Business Standard $/user/mo (annual)", 15, KNOWLEDGE_CAVEAT), "8 designers + 2 editors + Theo + Rachel; photographer as guest"),
    ("Frame.io Pro, 3 members x $15 (annual billing)", 3 * A("Frame.io Pro $/member/mo (annual)", 15, KNOWLEDGE_CAVEAT), "2 editors + Theo; reviewers free"),
    ("Design review/proofing tool (Ziflow/Filestage class), team plan", A("Design review tool $/mo", 149, "estimate; Filestage Starter ~$49 to Ziflow/Filestage team ~$249 ("+KNOWLEDGE_CAVEAT+"); midpoint"), "pinned client feedback on stills/PDF"),
    ("WeTransfer Pro, 2 seats x $12", 2 * A("WeTransfer Pro $/mo", 12, KNOWLEDGE_CAVEAT), "deliveries to clients"),
]

# --------------------------------------------------------------------------
# 2. Helpers
# --------------------------------------------------------------------------

def burn_for_month(m: int) -> float:
    for (lo, hi), b in BURN_BY_MONTH.items():
        if lo <= m <= hi:
            return b
    return BURN_BEYOND_36


def monthly_bill(tier_name: str, live_gb: float, egress_gb: float) -> tuple[str, float, float, float]:
    """Return (billed tier, subscription, storage overage, egress overage).

    A customer on `tier_name` is right-sized to the cheapest tier at or above
    their current one (a customer paying $600 in Studio overage would move to
    Plus; the usage view in WORKFLOWS 5.5 exists to make that visible)."""
    best = None
    for name in TIER_ORDER[TIER_ORDER.index(tier_name):]:
        t = TIERS[name]
        so = max(0.0, live_gb - t.storage_gb) * OVERAGE_STORAGE_PER_GB_MO
        eo = max(0.0, egress_gb - t.egress_gb) * OVERAGE_EGRESS_PER_GB
        total = t.monthly_usd + so + eo
        if best is None or total < best[1] + best[2] + best[3] - 1e-9:
            best = (name, t.monthly_usd, so, eo)
    return best


# --------------------------------------------------------------------------
# 3. COGS cross-check per workload (whole-file vs chunk dedup)
# --------------------------------------------------------------------------

def workload_storage(workload: str, chunk: bool, month_of_life: int = 12) -> dict:
    """Stored GB for the reference agency at `month_of_life`, plus a
    bottom-up monthly cost.  History = auto-snapshots inside the 30-day squash
    window + milestones kept forever.  Egress = egress_mult x live.
    """
    r_psd = CHUNK_DEDUP["psd"] if chunk else 0.0
    r_vid = CHUNK_DEDUP["video"] if chunk else 0.0
    r_raw = CHUNK_DEDUP["raw"] if chunk else 0.0

    # designers (all workloads)
    snaps_per_day = SAVES_PER_DAY * SNAPSHOT_CAPTURE
    window_psd = DESIGNERS * snaps_per_day * WORK_DAYS_PER_MONTH * PSD_GB * (1 - r_psd)
    milestones_psd_mo = DESIGNERS * MILESTONES_PER_DAY * WORK_DAYS_PER_MONTH * PSD_GB * (1 - r_psd)
    live = WORKLOADS["LIGHT"].live_gb
    live_growth = WORKLOADS["LIGHT"].live_growth_gb_mo
    egress_mult = WORKLOADS["LIGHT"].egress_mult
    window_video = 0.0
    milestones_video_mo = 0.0
    raw_mo = 0.0

    if workload in ("BASE", "HEAVY"):
        window_video = EDITORS * snaps_per_day * WORK_DAYS_PER_MONTH * PRPROJ_GB * (1 - r_vid)
        # renders: new files on the main line; re-exports of the same cut dedup by chunk
        milestones_video_mo = RENDERS_GB_MO * (1 - r_vid)
        live = WORKLOADS["BASE"].live_gb  # the task's 500 GB already includes the 60 GB synced video project
        live_growth = WORKLOADS["BASE"].live_growth_gb_mo
        egress_mult = WORKLOADS["BASE"].egress_mult
    if workload == "HEAVY":
        raw_mo = RAW_GB_MO * (1 - r_raw)
        live = WORKLOADS["HEAVY"].live_gb
        live_growth = WORKLOADS["HEAVY"].live_growth_gb_mo
        egress_mult = WORKLOADS["HEAVY"].egress_mult

    months_of_milestones = max(0, month_of_life - 1)  # older than the window
    history_window = window_psd + window_video
    history_kept = (milestones_psd_mo + milestones_video_mo) * months_of_milestones
    live_now = live + live_growth * month_of_life     # includes RAW growth for HEAVY
    total = live_now + history_window + history_kept
    total *= (1 + PREVIEW_OVERHEAD)

    f, i, a = HISTORY_TIER_MIX
    history_blend = f * S3_STANDARD_GB_MO + i * S3_IT_INFREQUENT + a * S3_IT_ARCHIVE_INSTANT
    cost_standard = total * S3_STANDARD_GB_MO
    cost_tiered = live_now * (1 + PREVIEW_OVERHEAD) * S3_STANDARD_GB_MO + (history_window + history_kept) * (1 + PREVIEW_OVERHEAD) * history_blend
    egress_gb = live_now * egress_mult
    egress_cost = egress_gb * CLOUDFRONT_EGRESS_GB
    return {
        "workload": workload, "dedup": "chunk" if chunk else "whole-file",
        "live_gb": live_now, "history_window_gb": history_window, "history_kept_gb": history_kept,
        "total_stored_gb": total, "egress_gb": egress_gb,
        "storage_cost_standard": cost_standard, "storage_cost_tiered": cost_tiered,
        "egress_cost": egress_cost,
        "cogs_bottom_up_standard": cost_standard + egress_cost + OTHER_INFRA_PER_CUSTOMER,
        "cogs_bottom_up_tiered": cost_tiered + egress_cost + OTHER_INFRA_PER_CUSTOMER,
    }


# --------------------------------------------------------------------------
# 4. Scenario engine (cohorts)
# --------------------------------------------------------------------------

@dataclass
class Cohort:
    tier: str
    workload: str
    start: int
    n0: float


@dataclass
class MonthRow:
    month: int
    new_customers: float = 0.0
    customers: float = 0.0
    customers_by_tier: dict = field(default_factory=dict)
    subscription: float = 0.0
    storage_overage: float = 0.0
    egress_overage: float = 0.0
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    burn: float = 0.0
    net_cash: float = 0.0
    cum_cash: float = 0.0
    sm_spend: float = 0.0


def run_scenario(sc: Scenario, horizon: int, freeze_after: int | None = None) -> list[MonthRow]:
    """Cohort simulation.  With `freeze_after`, the new-customer rate stops
    compounding after that month (held flat); used only to locate a breakeven
    month past the 36-month plan, conservatively."""
    cohorts: list[Cohort] = []
    rows: list[MonthRow] = []
    cum = 0.0
    for m in range(1, horizon + 1):
        row = MonthRow(month=m)
        if m >= REVENUE_START_MONTH:
            k = (min(m, freeze_after) if freeze_after else m) - REVENUE_START_MONTH
            new = sc.new_at_start * ((1 + sc.new_growth_mo) ** k)
            row.new_customers = new
            for tier, share in sc.tier_mix.items():
                if tier == "Studio":
                    for wl, wshare in STUDIO_WORKLOAD_MIX.items():
                        cohorts.append(Cohort(tier, wl, m, new * share * wshare))
                elif tier == "Solo":
                    cohorts.append(Cohort(tier, "SOLO", m, new * share))
                else:
                    cohorts.append(Cohort(tier, "PLUS", m, new * share))
            row.sm_spend = sc.paid_marketing_mo + sc.growth_labour_mo
        by_tier = {t: 0.0 for t in TIER_ORDER}
        for c in cohorts:
            age = m - c.start
            alive = c.n0 * ((1 - sc.churn_mo) ** age)
            if alive < 1e-9:
                continue
            w = WORKLOADS[c.workload]
            live = w.live_gb + w.live_growth_gb_mo * age
            egress = live * w.egress_mult
            billed_tier, sub, so, eo = monthly_bill(c.tier, live, egress)
            by_tier[billed_tier] += alive
            row.subscription += alive * sub
            row.storage_overage += alive * so
            row.egress_overage += alive * eo
            row.cogs += alive * COGS_PLACEHOLDER[billed_tier]
        row.customers = sum(by_tier.values())
        row.customers_by_tier = by_tier
        row.revenue = row.subscription + row.storage_overage + row.egress_overage
        row.gross_profit = row.revenue - row.cogs
        row.burn = burn_for_month(m)
        row.net_cash = row.gross_profit - row.burn
        cum += row.net_cash
        row.cum_cash = cum
        rows.append(row)
    return rows


def breakeven_label(ext_rows: list[MonthRow], how: str) -> tuple[str, int | None]:
    be = next((x.month for x in ext_rows if x.gross_profit >= x.burn), None)
    if be is None:
        return f">{EXTRAPOLATE_TO} (not reached, {how})", None
    if be <= HORIZON:
        return f"m{be}", be
    return f"m{be} (extrapolated past the 36-month plan, {how}, burn held at ${BURN_BEYOND_36:,}/mo)", be


def summarize(sc: Scenario, rows: list[MonthRow], ext_rows: list[MonthRow], ext_growth_rows: list[MonthRow]) -> dict:
    r = {x.month: x for x in rows}
    m12, m24, m36 = r[12], r[24], r[36]
    plan = [x for x in rows if x.month <= HORIZON]
    total_new = sum(x.new_customers for x in plan)
    total_sm = sum(x.sm_spend for x in plan)
    cac = total_sm / total_new if total_new else float("nan")
    arpa = m36.revenue / m36.customers if m36.customers else float("nan")
    gm = m36.gross_profit / m36.revenue if m36.revenue else float("nan")
    payback = cac / (arpa * gm) if arpa and gm and gm > 0 else float("inf")
    ltv = arpa * gm / sc.churn_mo if gm > 0 else 0.0
    be_label_frozen, be_frozen = breakeven_label(ext_rows, "new-customer rate frozen at its m36 level")
    be_label_growth, be_growth = breakeven_label(ext_growth_rows, f"new-customer rate keeps compounding at {sc.new_growth_mo:.0%}/mo")
    be_label = f"{be_label_growth}; {be_label_frozen}" if be_label_growth != be_label_frozen else be_label_growth
    peak_deficit_36 = -min(x.cum_cash for x in plan)
    deficit_to_be = -min(x.cum_cash for x in ext_growth_rows) if be_growth else None
    # gross margin excluding Solo (placeholder COGS makes Solo negative-margin)
    return {
        "name": sc.name,
        "customersM12": round(m12.customers, 1), "customersM24": round(m24.customers, 1), "customersM36": round(m36.customers, 1),
        "byTierM36": {t: round(v, 1) for t, v in m36.customers_by_tier.items()},
        "arrM12USD": round(m12.revenue * 12), "arrM24USD": round(m24.revenue * 12), "arrM36USD": round(m36.revenue * 12),
        "mrrM36": round(m36.revenue), "expansionShareM36": round((m36.storage_overage + m36.egress_overage) / m36.revenue, 3) if m36.revenue else 0,
        "grossMarginPct": round(gm * 100, 1),
        "grossProfitM36": round(m36.gross_profit),
        "breakevenMonth": be_label,
        "breakevenMonthGrowthContinues": be_growth,
        "breakevenMonthGrowthFrozen": be_frozen,
        "cumulativeCashNeedUSD": round(peak_deficit_36),
        "cumulativeCashNeedToBreakevenUSD": round(deficit_to_be) if deficit_to_be else None,
        "cumRevenue36": round(sum(x.revenue for x in plan)),
        "cumGrossProfit36": round(sum(x.gross_profit for x in plan)),
        "cumBurn36": round(sum(x.burn for x in plan)),
        "arpaM36": round(arpa, 2), "cac": round(cac), "totalNew36": round(total_new, 1), "totalSM36": round(total_sm),
        "paybackMonths": round(payback, 1) if payback != float("inf") else None,
        "ltv": round(ltv), "ltvCac": round(ltv / cac, 2) if cac else None,
        "churnMo": sc.churn_mo,
    }


# --------------------------------------------------------------------------
# 5. Reporting
# --------------------------------------------------------------------------

def fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def print_assumptions():
    print("\n## Assumptions (all USD)\n")
    print("| # | Assumption | Value | Source |")
    print("|---|---|---|---|")
    for i, (n, v, s) in enumerate(ASSUMPTIONS, 1):
        print(f"| {i} | {n} | {v} | {s} |")


def print_tiers():
    print("\n## Proposed tiers\n")
    print("| Tier | $/mo | Included live GB | Included egress GB/mo | History retention | $/included GB | Persona | Extras |")
    print("|---|---|---|---|---|---|---|---|")
    for t in TIERS.values():
        print(f"| {t.name} | {t.monthly_usd} | {t.storage_gb:,.0f} | {t.egress_gb:,.0f} | {t.retention_days} d auto-snapshots; milestones & releases forever | ${t.monthly_usd / t.storage_gb:.3f} | {t.persona} | {t.extras} |")
    print(f"\nOverage: storage ${OVERAGE_STORAGE_PER_GB_MO:.2f}/GB-month, egress ${OVERAGE_EGRESS_PER_GB:.2f}/GB, both shown in the Usage view before they are billed (WORKFLOWS 5.5).")
    print("Guests, reviewers and clients: free and unlimited on every tier. No feature paywalls: explorations, reviews, releases, approval records, Git access and the desktop client are in every plan (VISION). SSO/SCIM sits in Plus as an identity/support item, not a creative feature; if T1 interviews show 15-person agencies being asked for SSO by their clients, move it down rather than up.")
    print("Billable unit: LIVE GB (main line + releases + pinned explorations). History inside the retention window is included, so auto-snapshot volume is GitDAM's COGS risk, not the customer's bill (see COGS cross-check).")


def print_stack_check():
    print("\n## Sanity check: what the reference agency pays today\n")
    total = 0.0
    print("| Line | $/mo | Note |")
    print("|---|---|---|")
    for line, usd, note in STACK_TODAY:
        total += usd
        print(f"| {line} | {usd:,.0f} | {note} |")
    print(f"| **Total** | **{total:,.0f}** | {KNOWLEDGE_CAVEAT} |")
    studio = TIERS["Studio"].monthly_usd
    print(f"\nStudio at ${studio}/mo is {studio / total:.0%} of the current stack. If Dropbox stays for non-project files (likely in year one), the agency's total rises to ${total - (STACK_TODAY[1][1] + STACK_TODAY[2][1] + STACK_TODAY[3][1]) + studio:,.0f}/mo (+{(studio - (STACK_TODAY[1][1] + STACK_TODAY[2][1] + STACK_TODAY[3][1])):,.0f}); if Dropbox is dropped for project work, it falls to ${studio:,.0f}/mo (-{total - studio:,.0f}). Either way the price sits inside a budget line Rachel already has, which is the A3 test: the interview price ladder should bracket it ($149 / $299 / $499).")
    print(f"Per-person, Studio is ${studio / 15:.0f}/person/mo for 15 people vs Dropbox Standard $15 + Frame.io $15 per paid seat; Studio Plus is ${TIERS['Plus'].monthly_usd / 45:.0f}/person/mo at 45 people, below Diversion Pro ($25/user) and Anchorpoint (EUR 20/user) ({KNOWLEDGE_CAVEAT}).")


def print_cogs_check():
    print("\n## COGS cross-check for the reference agency (Studio tier), month 12 of the customer's life\n")
    print("Bottom-up = S3 storage (Standard list, and Intelligent-Tiering blend for history) + CloudFront egress + $8 other infra. RECONCILE with the infra model; this is the revenue model's view only.\n")
    print("| Workload | Dedup | Live GB | History in 30-day window GB | Milestones kept GB | Total stored GB | Egress GB/mo | Storage $ (Standard) | Storage $ (tiered) | Egress $ | Bottom-up COGS (Standard) | Bottom-up COGS (tiered) | Placeholder | GM at $299 (tiered) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = []
    for wl in ("LIGHT", "BASE", "HEAVY"):
        for chunk in (False, True):
            d = workload_storage(wl, chunk)
            gm = (TIERS["Studio"].monthly_usd + max(0, d["live_gb"] - TIERS["Studio"].storage_gb) * OVERAGE_STORAGE_PER_GB_MO - d["cogs_bottom_up_tiered"])
            price = TIERS["Studio"].monthly_usd + max(0, d["live_gb"] - TIERS["Studio"].storage_gb) * OVERAGE_STORAGE_PER_GB_MO
            print(f"| {wl} | {d['dedup']} | {d['live_gb']:,.0f} | {d['history_window_gb']:,.0f} | {d['history_kept_gb']:,.0f} | {d['total_stored_gb']:,.0f} | {d['egress_gb']:,.0f} | {d['storage_cost_standard']:,.0f} | {d['storage_cost_tiered']:,.0f} | {d['egress_cost']:,.0f} | {d['cogs_bottom_up_standard']:,.0f} | {d['cogs_bottom_up_tiered']:,.0f} | {COGS_PLACEHOLDER['Studio']} | {gm / price:.0%} of ${price:,.0f} |")
            out.append(d)
    print("\nReading: the $90 Studio placeholder holds for LIGHT/BASE only with chunk-level dedup AND Intelligent-Tiering on history; with whole-file dedup and S3 Standard, LIGHT alone is ~$180-190/mo, i.e. STRESS_TEST A2/F2 in numbers. HEAVY is fine on storage (RAW is live, billed as overage) but pushes the customer to Plus by ~month 15.")
    print("Solo placeholder $60 vs bottom-up: a Solo customer at ~130 GB live + ~150 GB history costs roughly $5-12/mo at list prices; $60 is 5-10x too high and makes Solo negative-margin in every scenario below. Flag for reconciliation before reading the Solo mix as a problem.")
    return out


def print_scenario(sc: Scenario, rows: list[MonthRow], s: dict):
    print(f"\n## Scenario {sc.name}: churn {sc.churn_mo:.1%}/mo, {sc.new_at_start} new/mo at m10 growing {sc.new_growth_mo:.0%}/mo, mix Solo {sc.tier_mix['Solo']:.0%} / Studio {sc.tier_mix['Studio']:.0%} / Plus {sc.tier_mix['Plus']:.0%}, paid marketing ${sc.paid_marketing_mo:,.0f}/mo\n")
    print("| Month | New | Customers (Solo/Studio/Plus) | MRR | of which overage | COGS | Gross profit | GM% | Burn | Net cash | Cumulative cash |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        if x.month in (6, 10, 12, 18, 24, 30, 36):
            bt = x.customers_by_tier
            gm = f"{x.gross_profit / x.revenue:.0%}" if x.revenue else "-"
            print(f"| {x.month} | {x.new_customers:.1f} | {x.customers:.0f} ({bt['Solo']:.0f}/{bt['Studio']:.0f}/{bt['Plus']:.0f}) | {fmt_money(x.revenue)} | {fmt_money(x.storage_overage + x.egress_overage)} | {fmt_money(x.cogs)} | {fmt_money(x.gross_profit)} | {gm} | {fmt_money(x.burn)} | {fmt_money(x.net_cash)} | {fmt_money(x.cum_cash)} |")
    print(f"\n- Customers m12/m24/m36: {s['customersM12']} / {s['customersM24']} / {s['customersM36']}  (m36 by tier: {s['byTierM36']})")
    print(f"- ARR m12/m24/m36: {fmt_money(s['arrM12USD'])} / {fmt_money(s['arrM24USD'])} / {fmt_money(s['arrM36USD'])}; expansion (overage) share of MRR at m36: {s['expansionShareM36']:.0%}")
    print(f"- Gross margin at m36: {s['grossMarginPct']}% (placeholder COGS)")
    print(f"- Breakeven (gross profit >= burn): {s['breakevenMonth']}")
    print(f"- Cumulative cash need through m36: {fmt_money(s['cumulativeCashNeedUSD'])} (burn {fmt_money(s['cumBurn36'])} less cumulative gross profit {fmt_money(s['cumGrossProfit36'])}); to breakeven with growth continuing: {fmt_money(s['cumulativeCashNeedToBreakevenUSD']) if s['cumulativeCashNeedToBreakevenUSD'] else 'n/a'}")
    print(f"- ARPA m36: ${s['arpaM36']}/mo; CAC: {fmt_money(s['cac'])} ({fmt_money(s['totalSM36'])} S&M over {s['totalNew36']} new customers); payback: {s['paybackMonths']} months; LTV: {fmt_money(s['ltv'])}; LTV/CAC: {s['ltvCac']}")


def write_csv(sc: Scenario, rows: list[MonthRow]):
    path = os.path.join(OUT_DIR, f"pnl_monthly_{sc.name.lower()}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "new_customers", "customers", "solo", "studio", "plus", "subscription", "storage_overage", "egress_overage", "revenue", "cogs", "gross_profit", "burn", "net_cash", "cum_cash", "sm_spend"])
        for x in rows:
            bt = x.customers_by_tier
            w.writerow([x.month, f"{x.new_customers:.2f}", f"{x.customers:.2f}", f"{bt['Solo']:.2f}", f"{bt['Studio']:.2f}", f"{bt['Plus']:.2f}",
                        f"{x.subscription:.0f}", f"{x.storage_overage:.0f}", f"{x.egress_overage:.0f}", f"{x.revenue:.0f}", f"{x.cogs:.0f}", f"{x.gross_profit:.0f}", f"{x.burn:.0f}", f"{x.net_cash:.0f}", f"{x.cum_cash:.0f}", f"{x.sm_spend:.0f}"])
    return path


# COGS sets for the sensitivity run.  "infra model" values are the per-customer
# totals printed by docs/financials/infra_model.py on 2026-09-29 (LIGHT/BASE/
# HEAVY blended 40/40/20 with STUDIO_WORKLOAD_MIX; sync fan-out 1.0, i.e.
# colleagues pull every auto-snapshot).  Solo and Plus are not modelled there;
# Solo is scaled from LIGHT by 1/8 of the designers plus a floor, Plus is ~3x
# Studio (estimate).  Reconcile when the infra model adds those tiers.
INFRA_MODEL_COGS = {
    "infra model, whole-file dedup, fan-out 1.0": {"Solo": 40, "Studio": 0.4 * 285.67 + 0.4 * 309.67 + 0.2 * 345.77, "Plus": 900},
    "infra model, chunk dedup, fan-out 1.0": {"Solo": 20, "Studio": 0.4 * 125.20 + 0.4 * 147.55 + 0.2 * 183.65, "Plus": 420},
    # infra model prints only LIGHT at fan-out 0 ($49.16 chunk); BASE $70 and HEAVY $105 are this file's estimates by scaling
    "infra model, chunk dedup, fan-out 0 (pull on demand only; BASE/HEAVY estimated)": {"Solo": 12, "Studio": 0.4 * 49.16 + 0.4 * 70 + 0.2 * 105, "Plus": 200},
}


def sensitivity(sc: Scenario) -> dict:
    """Gross margin at m36 under alternative COGS sets: this file's own
    bottom-up (chunk + Intelligent-Tiering) estimate, and the infra model's
    outputs.  Placeholders are restored afterwards."""
    global COGS_PLACEHOLDER
    saved = dict(COGS_PLACEHOLDER)
    studio_alt = sum(workload_storage(w, True)["cogs_bottom_up_tiered"] * STUDIO_WORKLOAD_MIX[w] for w in STUDIO_WORKLOAD_MIX)
    sets = {"this file bottom-up, chunk + tiered": {"Solo": 12, "Studio": studio_alt, "Plus": 220}}
    sets.update(INFRA_MODEL_COGS)
    out = {}
    for label, cogs in sets.items():
        COGS_PLACEHOLDER = cogs
        m36 = run_scenario(sc, HORIZON)[-1]
        out[label] = {"cogs": {k: round(v) for k, v in cogs.items()},
                      "gmM36": round(m36.gross_profit / m36.revenue * 100, 1),
                      "grossProfitM36": round(m36.gross_profit)}
    COGS_PLACEHOLDER = saved
    return out


def main():
    want_csv = "--csv" in sys.argv
    print(f"# GitDAM revenue model and P&L (generated {MODEL_DATE} by pnl_model.py)")
    print_assumptions()
    print_tiers()
    print_stack_check()
    cogs_rows = print_cogs_check()

    results = []
    for sc in SCENARIOS:
        rows = run_scenario(sc, HORIZON)
        # extended run for breakeven search: same scenario, growth in new-customer rate frozen at m36 level
        ext_frozen = run_scenario(sc, EXTRAPOLATE_TO, freeze_after=HORIZON)
        ext_growth = run_scenario(sc, EXTRAPOLATE_TO)
        s = summarize(sc, rows, ext_frozen, ext_growth)
        s["sensitivityBottomUpCogs"] = sensitivity(sc)
        print_scenario(sc, rows, s)
        print("- Sensitivity, gross margin at m36 under other COGS sets (Solo/Studio/Plus $ per customer-month):")
        for label, v in s["sensitivityBottomUpCogs"].items():
            c = v["cogs"]
            print(f"    {label}: ${c['Solo']}/${c['Studio']}/${c['Plus']} -> GM {v['gmM36']}%, gross profit {fmt_money(v['grossProfitM36'])}/mo")
        results.append(s)
        if want_csv:
            write_csv(sc, rows)

    with open(os.path.join(OUT_DIR, "pnl_summary.json"), "w") as f:
        json.dump({"generated": MODEL_DATE, "tiers": {k: vars(v) for k, v in TIERS.items()},
                   "overage": {"storage_per_gb_mo": OVERAGE_STORAGE_PER_GB_MO, "egress_per_gb": OVERAGE_EGRESS_PER_GB},
                   "cogs_placeholders": COGS_PLACEHOLDER, "cogs_crosscheck": cogs_rows, "scenarios": results}, f, indent=2)
    print(f"\nWrote {os.path.join(OUT_DIR, 'pnl_summary.json')}" + (" and per-scenario CSVs" if want_csv else " (add --csv for monthly CSVs)"))


if __name__ == "__main__":
    main()
