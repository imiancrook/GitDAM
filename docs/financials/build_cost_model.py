#!/usr/bin/env python3
"""GitDAM build cost and team plan model. All USD. Month 1 = first month of Phase 0.
Salaries are estimates (US remote market, 2026, verify against levels.fyi / Pave / Carta).
Run: python3 build_cost_model.py
"""
from collections import OrderedDict

LOAD = 1.3                 # fully-loaded factor on base salary (payroll tax, benefits, payroll/HR SaaS)
EU_LATAM_RATE = 0.55       # EU/LatAm senior remote base as a fraction of US base (estimate)
EU_LATAM_SHARE = 0.50      # share of paid seats hired EU/LatAm in the alternative
MONTHS = 24

# role: (US base salary, FTE fraction, start month, end month inclusive)
ROLES = OrderedDict([
    ("Founder/CTO (salary deferred)",         (0,       1.0,  1, 24)),
    ("Senior backend eng #1 (TS/AWS)",         (185_000, 1.0,  1, 24)),
    ("Frontend eng #1 (React/Next)",           (170_000, 1.0,  2, 24)),
    ("Senior Rust eng #1 (sync client)",       (200_000, 1.0,  5, 24)),
    ("Product designer",                       (155_000, 1.0,  6, 24)),
    ("DevRel / founding sales (0.5 FTE)",      (150_000, 0.5,  9, 24)),
    ("Backend eng #2 (mid, search/issues)",    (160_000, 1.0, 13, 24)),
    ("Rust/desktop eng #2 (File Provider/CFAPI)", (200_000, 1.0, 19, 24)),
])

def payroll_month(m, mix=False):
    total = 0.0
    heads = 0.0
    for name, (base, fte, start, end) in ROLES.items():
        if start <= m <= end:
            heads += fte
            monthly = base * fte * LOAD / 12
            if mix and base > 0:
                monthly *= (1 - EU_LATAM_SHARE) + EU_LATAM_SHARE * EU_LATAM_RATE
            total += monthly
    return total, heads

# Non-payroll, by month. Each entry: (label, function(month)->USD, source/estimate)
def aws(m):        return 1_500 if m <= 11 else 2_500          # dev/staging given; +$1k prod after launch (estimate)
def tooling(m):
    _, heads = payroll_month(m)
    return 400 + 150 * heads + 180                              # fixed SaaS + per-head seats + 2 Adobe CC Teams seats (list price as of knowledge, verify)
def dev_programs(m):
    return 700 if m in (5, 17) else 0                            # Apple Dev $99/yr + Windows OV code-signing cert ~$500/yr + MS Partner Center (list price, verify)
def legal(m):
    if m == 1: return 1_000 + 4_000                              # Delaware C-corp (Clerky/Atlas ~$500-1k) + formation docs
    if m in (2, 3): return 2_000                                 # ToS, privacy, DPA, SAFE (estimate ~$8k total year 1)
    return 1_000 if m >= 6 else 0                                # ongoing contracts/ToS (estimate)
def accounting(m):
    return 500 + (3_000 if m in (12, 24) else 0)                 # bookkeeping ~$500/mo + annual tax/franchise ~$3k (estimate)
def hardware(m):
    starts = [s for (_, (b, _, s, _)) in ROLES.items() if b > 0]
    return 3_500 * starts.count(m) + (6_000 if m == 5 else 0)     # laptop per hire + Mac/Windows test rigs for the client (estimate)
def marketing_site(m):
    return 6_000 if m in (9, 10) else 0                           # design contractor, $12k one-off (estimate)
def conference(m):
    return 10_000 if m == 10 else (12_000 if m == 20 else 0)      # one conference + community/swag per year (estimate)
def insurance(m):
    return 400 if m >= 12 else 0                                  # GL + E&O/cyber once there are customers (estimate)
def interviews(m):
    return 1_000 if m == 2 else 0                                 # Phase 0.5 interview incentives 10 x $100 (estimate)

NONPAY = [("AWS dev/staging(+prod)", aws), ("Tooling/SaaS + Adobe CC", tooling),
          ("Apple/MS programs + code signing", dev_programs), ("Legal/incorporation", legal),
          ("Accounting", accounting), ("Hardware", hardware), ("Marketing site contractor", marketing_site),
          ("Conference/community", conference), ("Insurance", insurance), ("Interview incentives", interviews)]

PERIODS = [("Q1 (M1-3): Phase 0 + 0.5 + Phase 1 start", 1, 3),
           ("Q2 (M4-6): Phase 1 finish, concierge, Phase 2 start", 4, 6),
           ("Q3 (M7-9): Phase 2 (sync client)", 7, 9),
           ("Q4 (M10-12): Phase 2 ship, first revenue M11, Phase 3 start", 10, 12),
           ("Q5 (M13-15): Phase 3", 13, 15),
           ("Q6 (M16-18): Phase 3 finish, Phase 4 start", 16, 18),
           ("Q7 (M19-21): Phase 4", 19, 21),
           ("Q8 (M22-24): Phase 5 (partial)", 22, 24)]
FIRST_REVENUE_MONTH = 11

def run(mix):
    rows, cum, cum_fr = [], 0.0, None
    for m in range(1, MONTHS + 1):
        pay, heads = payroll_month(m, mix)
        nonpay = sum(f(m) for _, f in NONPAY)
        cum += pay + nonpay
        rows.append((m, heads, pay, nonpay, pay + nonpay, cum))
        if m == FIRST_REVENUE_MONTH: cum_fr = cum
    return rows, cum_fr, cum

# Engineer-month estimates per phase (low, high)
PHASES = [("Phase 0", 0.6, 1.0), ("Phase 0.5", 0.5, 1.0), ("Phase 1", 5, 8), ("Phase 2", 10.5, 16),
          ("Phase 3", 9, 13), ("Phase 4", 10, 16), ("Phase 5", 9.5, 16.5)]


def main():
    # Copied verbatim from the build-cost step's scratchpad on 2026-09-29; the only change is that
    # printing now lives under this main() so reconciled_model.py can import the functions above.
    for mix in (False, True):
        rows, cum_fr, cum24 = run(mix)
        print("\n=== %s ===" % ("50% EU/LatAm mix" if mix else "US remote"))
        print("month heads payroll nonpayroll burn cumulative")
        for r in rows:
            print("%3d %5.1f %9.0f %9.0f %9.0f %10.0f" % r)
        print("\nBy period (avg monthly burn):")
        for label, a, b in PERIODS:
            sel = [r for r in rows if a <= r[0] <= b]
            avg = sum(r[4] for r in sel) / len(sel)
            heads = max(r[1] for r in sel)
            print("  %-60s heads=%.1f avg burn=%8.0f period total=%9.0f" % (label, heads, avg, sum(r[4] for r in sel)))
        print("Cash to first revenue (through M%d): %.0f" % (FIRST_REVENUE_MONTH, cum_fr))
        print("Cash to month 24: %.0f" % cum24)
        print("Non-payroll total 24m: %.0f" % sum(r[3] for r in rows))

    print("\nFounder salary sensitivity: $120k base loaded = %.0f/mo, %.0f over 24m" % (120_000*LOAD/12, 120_000*LOAD*2))
    for name, (base, fte, s, e) in ROLES.items():
        if base:
            print("  %-45s loaded/mo US %7.0f | mix-seat %7.0f" % (name, base*fte*LOAD/12, base*fte*LOAD/12*EU_LATAM_RATE))

    print("\nEngineer-months: low=%.1f high=%.1f (P0-P2 low=%.1f high=%.1f)" % (
        sum(p[1] for p in PHASES), sum(p[2] for p in PHASES), sum(p[1] for p in PHASES[:4]), sum(p[2] for p in PHASES[:4])))
    print("Paid engineering capacity M1-24 (excl. designer/devrel, incl. founder ~50%%): %.0f EM" % (
        sum((min(e,24)-s+1) for n,(b,f,s,e) in ROLES.items() if b and ("eng" in n)) + 12))


if __name__ == "__main__":
    main()
