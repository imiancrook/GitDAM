#!/usr/bin/env python3
"""
GitDAM reconciled financial model: infra COGS x build-model burn x P&L tiers and scenarios.

Run:  python3 docs/financials/reconciled_model.py [--csv] [--mix] [--plus-team-scale 2]

Reconciles the three models built in parallel on 2026-09-29 (all in this directory):
  * infra_model.py       per-customer monthly AWS cost by workload (LIGHT/BASE/HEAVY x whole-file/chunk dedup);
                         unit prices fetched from the AWS Price List Bulk API on 2026-09-29 except where marked
  * build_cost_model.py  team plan and monthly burn for months 1-24 (US remote and 50% EU/LatAm mix); copied from
                         the build-cost step's scratchpad, printing moved under main()
  * pnl_model.py         tiers (Solo $19 / Studio $299 / Plus $899), overage, workloads, BEAR/BASE/BULL scenarios and
                         the cohort engine; it ran with PLACEHOLDER COGS ($60/$90/$140) and PLACEHOLDER burn
                         ($95k/$140k/$180k) which this file replaces

What this file does
  1. Imports the three models and overrides the placeholders. COGS per cohort-month is computed by calling
     infra_model.scenario() with the cohort's workload, age (months of milestone history), live GB, and a COGS
     configuration (dedup, sync fan-out, tier retention). Platform-fixed cost (OpenSearch, NAT, Fargate bridge,
     ALB, misc) is added to COGS in total each month, which is the same as amortising it over that month's customers.
  2. Burn = build model payroll + non-payroll for M1-24, held at the M24 run-rate for M25-36, plus the scenario's
     paid marketing (excluded from the build model) and a support hire per 150 customers.
  3. Runs BEAR/BASE/BULL under four COGS configurations, A (as designed) to D (minimum viable change set), and
     prints: assumptions, tie-out to the infra model, COGS per tier, burn by period, scenario P&L tables,
     a cross-configuration summary, a unit-economics table, the T2 / T12 pass-bar checks, and the discrepancy list.

All figures USD. Fractional customers are expected values. Nothing outside docs/financials/ is touched.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT_DIR)

import infra_model as IM            # noqa: E402  (prices + per-customer cost engine)
import build_cost_model as BM       # noqa: E402  (payroll + non-payroll by month)
import pnl_model as PM              # noqa: E402  (tiers, overage, workloads, scenarios, monthly_bill)

MODEL_DATE = "2026-09-29"
VERIFY = "list price as of knowledge, verify"

# --------------------------------------------------------------------------
# 1. Reconciled inputs (every row has a source or "estimate")
# --------------------------------------------------------------------------
INPUTS: list[tuple[str, str, str]] = []


def R(name: str, value, source: str):
    INPUTS.append((name, str(value), source))
    return value


REVENUE_START = R("First revenue month", 11, "build model (Phase 2 ships M11); pnl model said M10 -> reconciled to M11")
HORIZON = 36
EXTRAPOLATE_TO = 96
OPENSEARCH_MONTH = R("OpenSearch Serverless turned on (Phase 3 complete)", 17, "build model: Phase 3 is M12-M16; infra platform fixed jumps from $100 to $451 when it ships")
SUPPORT_PER_CUSTOMERS = R("Customers per support/CS hire", 150, "estimate; SMB SaaS norm 100-200 accounts per CSM")
SUPPORT_BASE = R("Support/CS hire base salary", 100_000, "estimate; loaded x1.3 like the build model")
SUPPORT_LOADED = SUPPORT_BASE * BM.LOAD / 12
FOUNDER_GROWTH_TIME = R("Founder growth time attributed to S&M (non-cash, CAC only) $/mo", 5_000, "pnl model; founder salary deferred so it is not in cash burn")
PROD_AWS_STEP_MOVED = R("Build model 'production baseline' AWS step moved out of opex $/mo", 1_000, "build model had AWS $1.5k -> $2.5k at M12; the extra $1k is the platform-fixed cost now carried in COGS from the infra model, so it is removed from opex to avoid double counting")
Y3_ANNUALS = R("Year-3 non-payroll annuals", "accounting/tax $3k M36; dev programs $700 M29; conference $12k M32", "build model pattern continued")
PLUS_TEAM_SCALE_DEFAULT = R("Plus workload team scale vs 15-person reference", 1.0, "task mapping 'Plus ~ HEAVY'; a 30-60 person studio is 2-4x, see --plus-team-scale sensitivity")
SOLO_OVERRIDES = {"designers": 1, "active_users": 1, "guest_mau": 3,
                  "team_restore_gb_light": 50 / 8, "preview_cf_gb_light": 20 / 8, "release_dl_gb_light": 30 / 8,
                  "sync_fanout": 0.0}
R("Solo workload", "LIGHT infra scenario with 1 designer, 1 active user, 3 guests, per-team GB estimates /8, fan-out 0 (one member: nobody else's disk to fan out to)", "task mapping 'Solo ~ LIGHT/8'; live 80 GB +4/mo from pnl model")
R("HEAVY live growth GB/mo", 318, "infra: 12,000 RAW x 25 MB = 293 GB (binary GB) + 20 GB renders + 5 GB design; pnl model had 325 (decimal GB)")
R("Studio cohort workload mix LIGHT/BASE/HEAVY", "40/40/20", "pnl model")
R("COGS follows the cohort's WORKLOAD, not the billed tier", "yes", "reconciliation: a HEAVY agency right-sized to Plus still costs what a HEAVY agency costs; retention follows the billed tier")
R("Milestone history", "grows with cohort age (kept forever)", "pnl tiers 'milestones and releases forever'; infra model froze it at 6 months")
R("Intelligent-Tiering split on long-lived bytes", "age-aware: live/previews/proxies 50/30/20 (infra), milestone history newest month Frequent, next 2 Infrequent, older Archive-Instant", "estimate; infra used a fixed 50/30/20")
R("Auto-snapshot window cost by tier retention", "window GB x (retention_days/30 - 1) x $0.023 added on top of the infra 30-day window", "pnl tiers promise 30/90/365 d; DESIGN s11.3 squashes at 30 d (project setting); infra costed 30 d only")
R("Egress against the tier allowance", "infra model egress GB (S3 presigned + CloudFront)", "pnl model used 0.4-0.5 x live GB")
R("Paid marketing", "BEAR $6k / BASE $8k / BULL $10k per month from first revenue, added to burn", "pnl scenarios; the build model explicitly excluded paid marketing")
R("Burn M25-36", "M24 payroll ($124.0k US / $96.1k mix) + steady non-payroll ($5.1k) + support hires + paid marketing", "estimate; pnl placeholder was $180k")
R("Burn beyond M36 (breakeven search only)", "same formula as M25-36", "estimate")
R("Founder/CTO salary", "$0, deferred, excluded (would add ~$13k/mo at $120k base)", "build model")
R("Platform fixed $/mo", f"${IM.platform_fixed()[1]:,.2f} from M{OPENSEARCH_MONTH} (2 OCU OpenSearch); ${IM.platform_fixed()[1] - IM.platform_fixed()[0][0][1] - IM.platform_fixed()[0][1][1]:,.2f} M{REVENUE_START}-M{OPENSEARCH_MONTH-1}; $0 before revenue (dev/staging is opex)", "infra model; build model guessed OpenSearch ~$700 (4 OCU), reconciled to the fetched 2-OCU price, 4-OCU = +$350")

# Workloads: pnl model values, HEAVY growth reconciled to the infra RAW arithmetic
WORKLOADS = {k: PM.Workload(w.name, w.live_gb, w.live_growth_gb_mo, w.egress_mult) for k, w in PM.WORKLOADS.items()}
WORKLOADS["HEAVY"].live_growth_gb_mo = 318
TIER_OF_WORKLOAD = {"SOLO": "Solo", "LIGHT": "Studio", "BASE": "Studio", "HEAVY": "Studio", "PLUS": "Plus"}

# COGS configurations. A is the product as the docs stand at Phase 2 ship with the pnl tiers as proposed.
RETENTION_AS_PROPOSED = {t: PM.TIERS[t].retention_days for t in PM.TIER_ORDER}      # 30 / 90 / 365
RETENTION_30 = {t: 30 for t in PM.TIER_ORDER}
CONFIGS = OrderedDict([
    ("A", dict(label="A. As designed at Phase 2 ship: whole-file dedup, sync fan-out 1.0, tier retention 30/90/365 d",
               chunk=False, fanout=1.0, retention=RETENTION_AS_PROPOSED)),
    ("B", dict(label="B. A + chunk-level dedup in Phase 2 (ASSUMPTIONS decision 4; +2-3 EM, +1 month)",
               chunk=True, fanout=1.0, retention=RETENTION_AS_PROPOSED)),
    ("C", dict(label="C. B + pull-on-demand sync (auto-snapshots are not pushed to colleagues' disks; fan-out 0)",
               chunk=True, fanout=0.0, retention=RETENTION_AS_PROPOSED)),
    ("D", dict(label="D. C + auto-snapshot window 30 d on every tier (tiers differ by storage and support only)",
               chunk=True, fanout=0.0, retention=RETENTION_30)),
])
RECOMMENDED = "D"   # set after reading the results: A is negative-margin, B 42-47% GM, C 60-63%, D is the minimum set that clears the T2 70% bar at the published prices


# --------------------------------------------------------------------------
# 2. COGS engine (wraps infra_model.scenario)
# --------------------------------------------------------------------------
@contextmanager
def overrides(d: dict):
    saved = {k: IM.A[k] for k in d}
    IM.A.update(d)
    try:
        yield
    finally:
        IM.A.update(saved)


_COGS_CACHE: dict = {}


def cogs_detail(workload: str, age: int, cfg_key: str, billed_tier: str, plus_team_scale: float = 1.0,
                int_mode: str = "age", live_override: float | None = None) -> dict:
    """Per-customer-month COGS for a cohort of `workload` at `age` months under configuration `cfg_key`."""
    key = (workload, age, cfg_key, billed_tier, plus_team_scale, int_mode, live_override)
    if key in _COGS_CACHE:
        return _COGS_CACHE[key]
    cfg = CONFIGS[cfg_key]
    w = WORKLOADS[workload]
    live = live_override if live_override is not None else w.live_gb + w.live_growth_gb_mo * age
    ov = {"sync_fanout": cfg["fanout"], "history_months": age}
    if workload == "SOLO":
        ov.update(SOLO_OVERRIDES)
        kw = dict(video=False, photo=False)
    elif workload == "PLUS":
        s = plus_team_scale
        ov.update(designers=8 * s, editors=2 * s, active_users=15 * s, guest_mau=10 * s, shoots=4 * s,
                  team_restore_gb_light=50 * s, preview_cf_gb_light=20 * s, release_dl_gb_light=30 * s,
                  release_dl_gb_video=40 * s, release_dl_gb_photo=36 * s, preview_cf_gb_photo=6 * s,
                  mc_source_min=300 * s, renders_gb_month=20 * s, project_sync_gb_month=60 * s)
        kw = dict(video=True, photo=True)
    else:
        kw = dict(video=workload in ("BASE", "HEAVY"), photo=workload == "HEAVY")

    with overrides(ov):
        r = IM.scenario(workload, live, chunk=cfg["chunk"], **kw)
    if int_mode == "age":
        p = r["pools"]
        hot = p["live"] + p["previews"] + p.get("video_proxies", 0.0)
        hist = p["milestone_history"]
        per = hist / age if age else 0.0
        fa = 0.5 * hot + per * min(age, 1)
        ia = 0.3 * hot + per * min(max(age - 1, 0), 2)
        aia = 0.2 * hot + per * max(age - 3, 0)
        tot = fa + ia + aia
        with overrides({**ov, "int_long_lived_split": (fa / tot, ia / tot, aia / tot)}):
            r = IM.scenario(workload, live, chunk=cfg["chunk"], **kw)

    retention = cfg["retention"][billed_tier]
    window = r["pools"]["auto_snapshot_window"]
    retention_adder = window * (retention / 30.0 - 1.0) * IM.P["s3_int_fa_gbmo"]
    egress_usd = sum(v for l, v in r["lines"] if l.startswith("S3 egress") or l.startswith("CloudFront data"))
    out = {
        "workload": workload, "age": age, "cfg": cfg_key, "billed_tier": billed_tier,
        "live_gb": live, "stored_gb": r["storedGB"] + window * (retention / 30.0 - 1.0),
        "egress_gb": r["egressGB"], "egress_usd": egress_usd,
        "variable_usd": r["totalUSD"], "retention_adder_usd": retention_adder,
        "total_usd": r["totalUSD"] + retention_adder,
        "lines": r["lines"], "pools": r["pools"],
    }
    _COGS_CACHE[key] = out
    return out


def platform_fixed_month(m: int) -> float:
    items, total = IM.platform_fixed()
    if m < REVENUE_START:
        return 0.0
    if m < OPENSEARCH_MONTH:
        return total - items[0][1] - items[1][1]
    return total


# --------------------------------------------------------------------------
# 3. Burn engine (wraps build_cost_model)
# --------------------------------------------------------------------------
def build_opex(m: int, mix: bool) -> tuple[float, float]:
    """(payroll, non-payroll) for month m from the build model, extended past M24 at the M24 run-rate."""
    if m <= BM.MONTHS:
        pay, _ = BM.payroll_month(m, mix)
        nonpay = sum(f(m) for _, f in BM.NONPAY) - (PROD_AWS_STEP_MOVED if m >= 12 else 0)
        return pay, nonpay
    pay, _ = BM.payroll_month(BM.MONTHS, mix)
    steady = sum(f(23) for _, f in BM.NONPAY) - PROD_AWS_STEP_MOVED          # M23 is a plain month
    extra = (3_000 if m % 12 == 0 else 0) + (700 if m % 12 == 5 else 0) + (12_000 if m % 12 == 8 else 0)
    return pay, steady + extra


def devrel_cost(m: int, mix: bool) -> float:
    base, fte, s, e = BM.ROLES["DevRel / founding sales (0.5 FTE)"]
    if m < s:
        return 0.0
    c = base * fte * BM.LOAD / 12
    return c * ((1 - BM.EU_LATAM_SHARE) + BM.EU_LATAM_SHARE * BM.EU_LATAM_RATE) if mix else c


# --------------------------------------------------------------------------
# 4. Scenario engine (cohorts; adapted from pnl_model.run_scenario)
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
    cogs_variable: float = 0.0
    cogs_fixed: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    payroll: float = 0.0
    nonpayroll: float = 0.0
    support: float = 0.0
    marketing: float = 0.0
    burn: float = 0.0
    net_cash: float = 0.0
    cum_cash: float = 0.0
    sm_spend: float = 0.0


def run_scenario(sc: PM.Scenario, cfg_key: str, horizon: int, mix: bool = False, freeze_after: int | None = None,
                 plus_team_scale: float = 1.0) -> list[MonthRow]:
    cohorts: list[Cohort] = []
    rows: list[MonthRow] = []
    cum = 0.0
    for m in range(1, horizon + 1):
        row = MonthRow(month=m)
        if m >= REVENUE_START:
            k = (min(m, freeze_after) if freeze_after else m) - REVENUE_START
            new = sc.new_at_start * ((1 + sc.new_growth_mo) ** k)
            row.new_customers = new
            for tier, share in sc.tier_mix.items():
                if tier == "Studio":
                    for wl, wshare in PM.STUDIO_WORKLOAD_MIX.items():
                        cohorts.append(Cohort(tier, wl, m, new * share * wshare))
                elif tier == "Solo":
                    cohorts.append(Cohort(tier, "SOLO", m, new * share))
                else:
                    cohorts.append(Cohort(tier, "PLUS", m, new * share))
        by_tier = {t: 0.0 for t in PM.TIER_ORDER}
        for c in cohorts:
            age = m - c.start
            alive = c.n0 * ((1 - sc.churn_mo) ** age)
            if alive < 1e-9:
                continue
            w = WORKLOADS[c.workload]
            live = w.live_gb + w.live_growth_gb_mo * age
            # bill on live GB; egress against the allowance is the infra model's figure for this workload
            probe = cogs_detail(c.workload, age, cfg_key, c.tier, plus_team_scale)
            billed_tier, sub, so, eo = PM.monthly_bill(c.tier, live, probe["egress_gb"])
            d = probe if billed_tier == c.tier else cogs_detail(c.workload, age, cfg_key, billed_tier, plus_team_scale)
            by_tier[billed_tier] += alive
            row.subscription += alive * sub
            row.storage_overage += alive * so
            row.egress_overage += alive * eo
            row.cogs_variable += alive * d["total_usd"]
        row.customers = sum(by_tier.values())
        row.customers_by_tier = by_tier
        row.revenue = row.subscription + row.storage_overage + row.egress_overage
        row.cogs_fixed = platform_fixed_month(m)
        row.cogs = row.cogs_variable + row.cogs_fixed
        row.gross_profit = row.revenue - row.cogs
        row.payroll, row.nonpayroll = build_opex(m, mix)
        row.support = math.floor(row.customers / SUPPORT_PER_CUSTOMERS) * SUPPORT_LOADED * ((1 - BM.EU_LATAM_SHARE) + BM.EU_LATAM_SHARE * BM.EU_LATAM_RATE if mix else 1.0)
        row.marketing = sc.paid_marketing_mo if m >= REVENUE_START else 0.0
        row.burn = row.payroll + row.nonpayroll + row.support + row.marketing
        row.net_cash = row.gross_profit - row.burn
        cum += row.net_cash
        row.cum_cash = cum
        # S&M for CAC: paid marketing + devrel/sales + marketing site + conference + founder growth time (non-cash)
        row.sm_spend = row.marketing + devrel_cost(m, mix) + BM.marketing_site(m) + BM.conference(m) \
            + (FOUNDER_GROWTH_TIME if m >= REVENUE_START else 0.0)
        rows.append(row)
    return rows


def breakeven(ext_rows: list[MonthRow]) -> int | None:
    return next((x.month for x in ext_rows if x.month >= REVENUE_START and x.gross_profit >= x.burn), None)


def summarize(sc: PM.Scenario, cfg_key: str, rows: list[MonthRow], ext_frozen: list[MonthRow], ext_growth: list[MonthRow]) -> dict:
    r = {x.month: x for x in rows}
    m12, m24, m36 = r[12], r[24], r[36]
    total_new = sum(x.new_customers for x in rows)
    total_sm = sum(x.sm_spend for x in rows)
    cac = total_sm / total_new if total_new else float("nan")
    arpa = m36.revenue / m36.customers if m36.customers else float("nan")
    gm = m36.gross_profit / m36.revenue if m36.revenue else float("nan")
    gm_var = (m36.revenue - m36.cogs_variable) / m36.revenue if m36.revenue else float("nan")
    payback = cac / (arpa * gm) if gm > 0 else None
    ltv = arpa * gm / sc.churn_mo if gm > 0 else 0.0
    be_g, be_f = breakeven(ext_growth), breakeven(ext_frozen)
    need_be = -min(x.cum_cash for x in ext_growth) if be_g else None
    return {
        "scenario": sc.name, "config": cfg_key,
        "customersM12": round(m12.customers, 1), "customersM24": round(m24.customers, 1), "customersM36": round(m36.customers, 1),
        "byTierM36": {t: round(v, 1) for t, v in m36.customers_by_tier.items()},
        "arrM12": round(m12.revenue * 12), "arrM24": round(m24.revenue * 12), "arrM36": round(m36.revenue * 12),
        "mrrM36": round(m36.revenue), "cogsM36": round(m36.cogs), "cogsVariableM36": round(m36.cogs_variable), "cogsFixedM36": round(m36.cogs_fixed),
        "grossMarginPctM36": round(gm * 100, 1), "grossMarginPctM36ExFixed": round(gm_var * 100, 1),
        "grossMarginPctM24": round((m24.gross_profit / m24.revenue) * 100, 1) if m24.revenue else None,
        "burnM12": round(m12.burn), "burnM24": round(m24.burn), "burnM36": round(m36.burn),
        "netCashM12": round(m12.net_cash), "netCashM24": round(m24.net_cash), "netCashM36": round(m36.net_cash),
        "breakevenGrowthContinues": be_g, "breakevenGrowthFrozen": be_f,
        "cumCashNeed36": round(-min(x.cum_cash for x in rows)),
        "cumCashNeedToBreakeven": round(need_be) if need_be else None,
        "cumRevenue36": round(sum(x.revenue for x in rows)), "cumGrossProfit36": round(sum(x.gross_profit for x in rows)),
        "cumBurn36": round(sum(x.burn for x in rows)),
        "arpaM36": round(arpa, 2), "cac": round(cac), "totalNew36": round(total_new, 1), "totalSM36": round(total_sm),
        "paybackMonths": round(payback, 1) if payback else None, "ltv": round(ltv), "ltvCac": round(ltv / cac, 2) if cac else None,
        "expansionShareM36": round((m36.storage_overage + m36.egress_overage) / m36.revenue, 3) if m36.revenue else 0,
    }


# --------------------------------------------------------------------------
# 5. Reporting
# --------------------------------------------------------------------------
def money(x) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


def print_inputs():
    print("\n## Reconciled inputs (USD)\n")
    print("| # | Input | Value | Source |")
    print("|---|---|---|---|")
    for i, (n, v, s) in enumerate(INPUTS, 1):
        print(f"| {i} | {n} | {v} | {s} |")
    print("\nUnchanged from pnl_model.py: tiers (Solo $19/250 GB, Studio $299/2 TB, Plus $899/8 TB; egress allowance 3x storage), overage $0.10/GB-mo storage and $0.08/GB egress, billable unit = live GB, scenario growth/churn/mix, CAC method. Unchanged from infra_model.py: every unit price and workload assumption not listed above (run it for the full tables). Unchanged from build_cost_model.py: roles, salaries, non-payroll lines.")


def print_tieout():
    print("\n## Tie-out to the infra model (age 6, fixed 50/30/20 tiering split, retention 30 d, fan-out 1.0)\n")
    print("| Workload | Dedup | Infra model | This file | Delta |")
    print("|---|---|---|---|---|")
    ref = {("LIGHT", False): 285.67, ("BASE", False): 309.67, ("HEAVY", False): 345.77, ("LIGHT", True): 125.20, ("BASE", True): 147.55, ("HEAVY", True): 183.65}
    live = {"LIGHT": 200, "BASE": 500, "HEAVY": 1536}
    for wl in ("LIGHT", "BASE", "HEAVY"):
        for chunk in (False, True):
            cfg = "B" if chunk else "A"
            d = cogs_detail(wl, 6, cfg, "Solo", int_mode="infra", live_override=live[wl])   # 'Solo' retention = 30 d
            print(f"| {wl} | {'chunk' if chunk else 'whole-file'} | ${ref[(wl, chunk)]:,.2f} | ${d['variable_usd']:,.2f} | {d['variable_usd'] - ref[(wl, chunk)]:+.2f} |")
    print("\nThe infra headline numbers reproduce exactly; the P&L below differs from them because milestone history grows with age, the tiering split is age-aware, live GB grows, and tier retention is costed.")


def print_cogs_table(plus_team_scale: float):
    print("\n## COGS per customer-month by tier and workload (variable AWS cost; platform fixed is added in total per month)\n")
    print("| Tier / workload | Config | Age 0 | Age 12 | Age 24 | Age 36 | of which retention adder (age 12) | Egress $ (age 12) | Egress GB (age 12) | Price paid (age 12) | GM ex-fixed (age 12) | Egress % of price (T12 <15%) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = []
    for wl in ("SOLO", "LIGHT", "BASE", "HEAVY", "PLUS"):
        tier = TIER_OF_WORKLOAD[wl]
        for cfg_key in CONFIGS:
            w = WORKLOADS[wl]
            vals = {}
            for age in (0, 12, 24, 36):
                live = w.live_gb + w.live_growth_gb_mo * age
                d0 = cogs_detail(wl, age, cfg_key, tier, plus_team_scale)
                billed, sub, so, eo = PM.monthly_bill(tier, live, d0["egress_gb"])
                d = d0 if billed == tier else cogs_detail(wl, age, cfg_key, billed, plus_team_scale)
                vals[age] = (d, sub + so + eo, billed)
            d12, price12, billed12 = vals[12]
            gm12 = (price12 - d12["total_usd"]) / price12
            eg_pct = d12["egress_usd"] / price12
            print(f"| {tier} / {wl} | {cfg_key} | {vals[0][0]['total_usd']:,.0f} | {d12['total_usd']:,.0f} | {vals[24][0]['total_usd']:,.0f} | {vals[36][0]['total_usd']:,.0f} | {d12['retention_adder_usd']:,.0f} | {d12['egress_usd']:,.0f} | {d12['egress_gb']:,.0f} | {price12:,.0f} ({billed12}) | {gm12:.0%} | {eg_pct:.0%} |")
            out.append({"tier": tier, "workload": wl, "config": cfg_key,
                        "cogs": {a: round(vals[a][0]["total_usd"], 2) for a in vals},
                        "retentionAdderAge12": round(d12["retention_adder_usd"], 2), "egressUsdAge12": round(d12["egress_usd"], 2),
                        "egressGbAge12": round(d12["egress_gb"]), "priceAge12": round(price12, 2), "billedTierAge12": billed12,
                        "gmExFixedAge12": round(gm12 * 100, 1), "egressPctOfPriceAge12": round(eg_pct * 100, 1)})
    print("\nTop three cost lines, Studio/LIGHT at age 12:")
    for cfg_key in CONFIGS:
        d = cogs_detail("LIGHT", 12, cfg_key, "Studio", plus_team_scale)
        top = sorted(d["lines"], key=lambda x: -x[1])[:3]
        print(f"  {cfg_key}: " + " | ".join(f"{l.split(' (')[0]} ${v:,.0f}" for l, v in top) + (f" | retention adder ${d['retention_adder_usd']:,.0f}" if d["retention_adder_usd"] else ""))
    return out


def print_burn(mix: bool):
    print(f"\n## Burn by period ({'50% EU/LatAm mix' if mix else 'US remote'}; before support hires and paid marketing, which are scenario-dependent)\n")
    print("| Period | Payroll avg/mo | Non-payroll avg/mo | Opex avg/mo | Period total | Cumulative |")
    print("|---|---|---|---|---|---|")
    periods = [(l, a, b) for (l, a, b) in BM.PERIODS] + [("Q9-Q12 (M25-36): held at M24 run-rate", 25, 36)]
    cum = 0.0
    out = []
    for label, a, b in periods:
        pay = [build_opex(m, mix)[0] for m in range(a, b + 1)]
        non = [build_opex(m, mix)[1] for m in range(a, b + 1)]
        tot = sum(pay) + sum(non)
        cum += tot
        print(f"| {label} | {money(sum(pay) / len(pay))} | {money(sum(non) / len(non))} | {money(tot / len(pay))} | {money(tot)} | {money(cum)} |")
        out.append({"period": label, "payrollAvg": round(sum(pay) / len(pay)), "nonpayrollAvg": round(sum(non) / len(non)), "opexAvg": round(tot / len(pay)), "total": round(tot), "cumulative": round(cum)})
    fr = sum(sum(build_opex(m, mix)) for m in range(1, REVENUE_START + 1))
    print(f"\nOpex to first revenue (through M{REVENUE_START}): {money(fr)}; to M24: {money(sum(sum(build_opex(m, mix)) for m in range(1, 25)))}; to M36: {money(cum)}. Build model's own figures (before the $1k/mo AWS step was moved to COGS): $778,972 / $2,326,378 US.")
    return out


def print_scenario(sc: PM.Scenario, cfg_key: str, rows: list[MonthRow], s: dict):
    print(f"\n### {sc.name} under config {cfg_key}: churn {sc.churn_mo:.1%}/mo, {sc.new_at_start} new/mo at M{REVENUE_START} growing {sc.new_growth_mo:.0%}/mo, mix Solo {sc.tier_mix['Solo']:.0%} / Studio {sc.tier_mix['Studio']:.0%} / Plus {sc.tier_mix['Plus']:.0%}, paid marketing {money(sc.paid_marketing_mo)}/mo\n")
    print("| Month | New | Customers (Solo/Studio/Plus) | MRR | ARR | COGS var + fixed | Gross profit | GM% | Burn (payroll+nonpay+support+mktg) | Net cash | Cumulative cash |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        if x.month in (6, 11, 12, 18, 24, 30, 36):
            bt = x.customers_by_tier
            gm = f"{x.gross_profit / x.revenue:.0%}" if x.revenue else "-"
            print(f"| {x.month} | {x.new_customers:.1f} | {x.customers:.0f} ({bt['Solo']:.0f}/{bt['Studio']:.0f}/{bt['Plus']:.0f}) | {money(x.revenue)} | {money(x.revenue * 12)} | {money(x.cogs_variable)} + {money(x.cogs_fixed)} | {money(x.gross_profit)} | {gm} | {money(x.burn)} ({money(x.payroll)}+{money(x.nonpayroll)}+{money(x.support)}+{money(x.marketing)}) | {money(x.net_cash)} | {money(x.cum_cash)} |")
    be = f"M{s['breakevenGrowthContinues']}" if s["breakevenGrowthContinues"] else f">M{EXTRAPOLATE_TO}"
    bef = f"M{s['breakevenGrowthFrozen']}" if s["breakevenGrowthFrozen"] else f">M{EXTRAPOLATE_TO}"
    print(f"\n- Customers M12/M24/M36: {s['customersM12']} / {s['customersM24']} / {s['customersM36']} (M36 by tier {s['byTierM36']})")
    print(f"- ARR M12/M24/M36: {money(s['arrM12'])} / {money(s['arrM24'])} / {money(s['arrM36'])}; overage share of MRR at M36 {s['expansionShareM36']:.0%}")
    print(f"- Gross margin M36: {s['grossMarginPctM36']}% incl. platform fixed ({s['grossMarginPctM36ExFixed']}% ex-fixed); M24: {s['grossMarginPctM24']}%")
    print(f"- Breakeven (gross profit >= burn): {be} with new-customer growth continuing; {bef} with the rate frozen at M36")
    print(f"- Cumulative cash need through M36: {money(s['cumCashNeed36'])} (burn {money(s['cumBurn36'])} less cumulative gross profit {money(s['cumGrossProfit36'])}); to breakeven with growth continuing: {money(s['cumCashNeedToBreakeven'])}")
    print(f"- ARPA M36 ${s['arpaM36']}/mo; CAC {money(s['cac'])} ({money(s['totalSM36'])} S&M incl. devrel/sales and founder time over {s['totalNew36']} new customers); payback {s['paybackMonths']} months; LTV {money(s['ltv'])}; LTV/CAC {s['ltvCac']}")


def write_csv(sc: PM.Scenario, cfg_key: str, rows: list[MonthRow]) -> str:
    path = os.path.join(OUT_DIR, f"reconciled_monthly_{sc.name.lower()}_{cfg_key}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "new_customers", "customers", "solo", "studio", "plus", "subscription", "storage_overage", "egress_overage", "revenue",
                    "cogs_variable", "cogs_fixed", "cogs", "gross_profit", "payroll", "nonpayroll", "support", "marketing", "burn", "net_cash", "cum_cash", "sm_spend"])
        for x in rows:
            bt = x.customers_by_tier
            w.writerow([x.month, f"{x.new_customers:.2f}", f"{x.customers:.2f}", f"{bt['Solo']:.2f}", f"{bt['Studio']:.2f}", f"{bt['Plus']:.2f}",
                        f"{x.subscription:.0f}", f"{x.storage_overage:.0f}", f"{x.egress_overage:.0f}", f"{x.revenue:.0f}",
                        f"{x.cogs_variable:.0f}", f"{x.cogs_fixed:.0f}", f"{x.cogs:.0f}", f"{x.gross_profit:.0f}", f"{x.payroll:.0f}", f"{x.nonpayroll:.0f}",
                        f"{x.support:.0f}", f"{x.marketing:.0f}", f"{x.burn:.0f}", f"{x.net_cash:.0f}", f"{x.cum_cash:.0f}", f"{x.sm_spend:.0f}"])
    return path


DISCREPANCIES = [
    ("Studio COGS", "infra: LIGHT $286 / BASE $310 / HEAVY $346 whole-file (fan-out 1.0, age 6)", "pnl: $90 placeholder; own bottom-up $128-169 tiered", "Replaced by infra_model.scenario() called per cohort workload and age; fixed platform cost added in total per month"),
    ("Solo COGS", "infra: not modelled", "pnl: $60 placeholder; bottom-up $5-12", "LIGHT scenario re-run with 1 designer, 1 user, 3 guests, per-team GB /8, fan-out 0: see COGS table (about $13 whole-file, $8 chunk at age 12)"),
    ("Plus COGS", "infra: not modelled; task maps Plus ~ HEAVY", "pnl: $140 placeholder; sensitivity used $200-900", "HEAVY scenario at the Plus live GB (3 TB +150/mo) with the 15-person activity profile (team scale 1.0); --plus-team-scale 2 shows a 30-person studio"),
    ("Burn", "build: $31k M1 rising to $133k M24, $779k to first revenue, $2.33M to M24 (US)", "pnl: $95k / $140k / $180k placeholders, $4.98M over 36 months", "Build model imported month by month for M1-24; M25-36 held at the M24 run-rate + support hires + paid marketing; 36-month burn is ~$4.2-4.3M, below the placeholder"),
    ("First revenue month", "build: M11", "pnl: M10", "M11"),
    ("Paid marketing", "build: excluded", "pnl: $6k/$8k/$10k inside the burn placeholder", "Added to burn from M11 per scenario"),
    ("Production AWS baseline", "build: AWS opex steps $1.5k -> $2.5k at M12", "infra: platform fixed $100 (pre-OpenSearch) / $451 (2 OCU) as COGS", "The $1k step is removed from opex; platform fixed is carried in COGS from M11 ($100) and M17 ($451). No double count"),
    ("OpenSearch cost", "build: '~$700/mo when it turns on, verify'", "infra: $350 for 2 OCU (fetched price), $701 for 4-OCU redundancy", "$350 (2 OCU) from M17; production redundancy would add $350/mo, a sensitivity"),
    ("Working days / captured snapshots / milestones", "infra: 22 days, 6 captured/day, 2 milestones/week", "pnl: 21 days, 12 captured/day (60% of saves), 1 milestone/day", "Infra values (they drive COGS); pnl's snapshot arithmetic is superseded"),
    ("Egress volume and price", "infra: 2,112-2,418 GB/mo at S3 $0.09 (sync fan-out) + 50-154 GB CloudFront", "pnl: 0.4-0.5 x live GB at CloudFront $0.085 ($11-34/mo)", "Infra values; the difference is DESIGN s8 'clean on disk -> replace' fanning auto-snapshots out to colleagues"),
    ("Tier retention", "infra: 30-day squash window only", "pnl: tiers promise 30 / 90 / 365 days of auto-snapshot history", "Costed: window GB x (retention/30 - 1) x $0.023; config D removes it"),
    ("Milestone history", "infra: frozen at 6 months", "pnl: milestones kept forever", "Grows with cohort age; tiering split becomes age-aware so old milestones sit in Archive-Instant"),
    ("HEAVY live growth", "infra: 293 GB/mo RAW (binary GB)", "pnl: 325 GB/mo", "318 GB/mo (293 RAW + 20 renders + 5 design)"),
    ("HEAVY live at start", "infra: 1,536 GB (1.5 TiB)", "pnl: 1,500 GB", "1,500 (task value); the tie-out uses 1,536 to reproduce the infra headline"),
    ("Chunk dedup timing", "build: not in Phase 2; +2-3 EM, +1 month if T2 forces it", "pnl: sensitivity only", "Config B-D assume it is in Phase 2; the build cost of that (~$45-65k) is inside the build model's slack, not added to burn"),
    ("Founder salary", "build: excluded ($0 deferred)", "pnl: $5k/mo founder growth time in CAC", "Both kept: $0 in cash burn, $5k/mo in the CAC numerator"),
    ("Support / CS headcount", "build: none (devrel 0.5 FTE handles early support)", "pnl: none", "1 support hire per 150 customers ($100k base) added; matters only in BULL"),
    ("Free tiers", "infra: ignored (CloudFront 1 TB, S3 100 GB egress, Cognito 10k MAU)", "pnl: ignored", "Ignored; would remove ~$5-15/customer-month for the first ~10 customers"),
]


def print_discrepancies():
    print("\n## Discrepancies between the three models and how they were resolved\n")
    print("| Item | Infra / build model | P&L model | Resolution |")
    print("|---|---|---|---|")
    for item, a, b, res in DISCREPANCIES:
        print(f"| {item} | {a} | {b} | {res} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="write monthly CSVs per scenario and config")
    ap.add_argument("--mix", action="store_true", help="use the build model's 50% EU/LatAm payroll mix")
    ap.add_argument("--plus-team-scale", type=float, default=PLUS_TEAM_SCALE_DEFAULT, help="Plus workload team size vs the 15-person reference")
    args = ap.parse_args()
    mix = args.mix
    pts = args.plus_team_scale

    print(f"# GitDAM reconciled financial model (generated {MODEL_DATE} by reconciled_model.py; payroll {'50% EU/LatAm mix' if mix else 'US remote'}; Plus team scale {pts})")
    print_inputs()
    print_tieout()
    cogs_rows = print_cogs_table(pts)
    burn_rows = print_burn(mix)

    print("\n## COGS configurations\n")
    for k, c in CONFIGS.items():
        print(f"- {c['label']}")

    results = []
    for cfg_key in CONFIGS:
        print(f"\n## Scenarios under configuration {cfg_key}" + ("  (RECOMMENDED)" if cfg_key == RECOMMENDED else ""))
        for sc in PM.SCENARIOS:
            rows = run_scenario(sc, cfg_key, HORIZON, mix, plus_team_scale=pts)
            ext_f = run_scenario(sc, cfg_key, EXTRAPOLATE_TO, mix, freeze_after=HORIZON, plus_team_scale=pts)
            ext_g = run_scenario(sc, cfg_key, EXTRAPOLATE_TO, mix, plus_team_scale=pts)
            s = summarize(sc, cfg_key, rows, ext_f, ext_g)
            results.append(s)
            if cfg_key in ("A", RECOMMENDED):
                print_scenario(sc, cfg_key, rows, s)
            if args.csv:
                write_csv(sc, cfg_key, rows)

    print("\n## Cross-configuration summary (M36 unless stated)\n")
    print("| Config | Scenario | Customers M36 | ARR M36 | COGS M36 (var+fixed) | GM% M36 | Burn M36 | Net cash M36 | Breakeven (growth cont. / frozen) | Cash need to M36 | Cash need to breakeven | LTV/CAC |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in results:
        be = f"M{s['breakevenGrowthContinues']}" if s["breakevenGrowthContinues"] else f">M{EXTRAPOLATE_TO}"
        bef = f"M{s['breakevenGrowthFrozen']}" if s["breakevenGrowthFrozen"] else f">M{EXTRAPOLATE_TO}"
        print(f"| {s['config']} | {s['scenario']} | {s['customersM36']} | {money(s['arrM36'])} | {money(s['cogsVariableM36'])}+{money(s['cogsFixedM36'])} | {s['grossMarginPctM36']}% | {money(s['burnM36'])} | {money(s['netCashM36'])} | {be} / {bef} | {money(s['cumCashNeed36'])} | {money(s['cumCashNeedToBreakeven'])} | {s['ltvCac']} |")

    print("\n## Unit economics (M36, per scenario, recommended config " + RECOMMENDED + ")\n")
    print("| Scenario | ARPA $/mo | GM% | CAC | Payback (months) | LTV | LTV/CAC | Monthly churn |")
    print("|---|---|---|---|---|---|---|---|")
    for s in results:
        if s["config"] == RECOMMENDED:
            sc = next(x for x in PM.SCENARIOS if x.name == s["scenario"])
            print(f"| {s['scenario']} | {s['arpaM36']} | {s['grossMarginPctM36']}% | {money(s['cac'])} | {s['paybackMonths']} | {money(s['ltv'])} | {s['ltvCac']} | {sc.churn_mo:.1%} |")

    # T2 / T12 checks at the published prices, Studio reference agency, age 12, fixed amortised over 20 customers
    print("\n## ASSUMPTIONS.md pass bars at the published prices (Studio, reference agency, age 12, platform fixed amortised over 20 and over 50 customers)\n")
    print("| Config | Workload | Price paid | Variable COGS | + fixed/20 | GM% (fixed/20) | T2 >= 70%? | GM% (fixed/50) | Egress % of price | T12 < 15%? |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    fixed20 = IM.platform_fixed()[1] / 20
    fixed50 = IM.platform_fixed()[1] / 50
    t2 = {}
    for cfg_key in CONFIGS:
        for wl in ("LIGHT", "BASE", "HEAVY"):
            w = WORKLOADS[wl]
            live = w.live_gb + w.live_growth_gb_mo * 12
            d0 = cogs_detail(wl, 12, cfg_key, "Studio", pts)
            billed, sub, so, eo = PM.monthly_bill("Studio", live, d0["egress_gb"])
            d = d0 if billed == "Studio" else cogs_detail(wl, 12, cfg_key, billed, pts)
            price = sub + so + eo
            gm = (price - d["total_usd"] - fixed20) / price
            gm50 = (price - d["total_usd"] - fixed50) / price
            eg = d["egress_usd"] / price
            t2[(cfg_key, wl)] = gm
            print(f"| {cfg_key} | {wl} | {money(price)} ({billed}) | {money(d['total_usd'])} | {money(fixed20)} | {gm:.0%} | {'PASS' if gm >= 0.70 else 'FAIL'} | {gm50:.0%} | {eg:.0%} | {'PASS' if eg < 0.15 else 'FAIL'} |")

    # Sensitivities
    print("\n## Sensitivities\n")
    for cfg_key in ("A", RECOMMENDED):
        base_sc = PM.SCENARIOS[1]
        rows_us = run_scenario(base_sc, cfg_key, HORIZON, False, plus_team_scale=pts)
        rows_mx = run_scenario(base_sc, cfg_key, HORIZON, True, plus_team_scale=pts)
        print(f"- BASE scenario, config {cfg_key}: cash need to M36 US remote {money(-min(x.cum_cash for x in rows_us))} vs 50% EU/LatAm mix {money(-min(x.cum_cash for x in rows_mx))}")
    for scale in (1.0, 2.0, 3.0):
        d = cogs_detail("PLUS", 12, RECOMMENDED, "Plus", scale)
        print(f"- Plus COGS at team scale {scale:.0f}x (config {RECOMMENDED}, age 12): {money(d['total_usd'])} against $899 + overage -> GM ex-fixed {(899 - d['total_usd']) / 899:.0%}")
    items, total = IM.platform_fixed()
    print(f"- Platform fixed with 4-OCU OpenSearch (production redundancy): {money(total + 2 * 730 * IM.P['aoss_ocu_hr'])}/mo instead of {money(total)}; at 50 customers that is +${2 * 730 * IM.P['aoss_ocu_hr'] / 50:,.0f}/customer-month")
    d_a = cogs_detail("LIGHT", 12, "A", "Studio", pts)
    with overrides({"preview_on_put": False}):
        _COGS_CACHE.clear()
        d_p = cogs_detail("LIGHT", 12, RECOMMENDED, "Studio", pts)
    _COGS_CACHE.clear()
    d_c = cogs_detail("LIGHT", 12, RECOMMENDED, "Studio", pts)
    print(f"- Previews triggered by commit instead of S3 PUT (DESIGN s7 change): Studio/LIGHT config {RECOMMENDED} {money(d_c['total_usd'])} -> {money(d_p['total_usd'])}/mo")
    print(f"- STRESS_TEST high case (Phase 2 at 8 months, first revenue M13): adds ~2 months of M11-12 burn (~${2 * sum(build_opex(12, mix)):,.0f}) to cash-to-first-revenue and shifts every revenue figure two months right")

    print_discrepancies()

    summary = {
        "generated": MODEL_DATE, "payroll": "mix" if mix else "us", "plusTeamScale": pts,
        "inputs": [{"input": n, "value": v, "source": s} for n, v, s in INPUTS],
        "configs": {k: c["label"] for k, c in CONFIGS.items()}, "recommended": RECOMMENDED,
        "cogsByTier": cogs_rows, "burnByPeriod": burn_rows, "scenarios": results,
        "t2GrossMarginAge12": {f"{k[0]}/{k[1]}": round(v * 100, 1) for k, v in t2.items()},
        "discrepancies": [{"item": i, "modelA": a, "modelB": b, "resolution": r} for i, a, b, r in DISCREPANCIES],
    }
    with open(os.path.join(OUT_DIR, "reconciled_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {os.path.join(OUT_DIR, 'reconciled_summary.json')}" + (" and reconciled_monthly_<scenario>_<config>.csv" if args.csv else " (add --csv for monthly CSVs)"))


if __name__ == "__main__":
    main()
