#!/usr/bin/env python3
"""
GitDAM per-customer monthly AWS infrastructure cost model.

Reference customer (WORKFLOWS.md §13, PERSONAS.md): a 15-person agency with
8 designers, 2 video editors, 1 contract photographer, 3 client projects.

Scenarios (× whole-file dedup only / chunk-level dedup):
  LIGHT  designers only: 2 GB PSDs saved 20×/day, auto-snapshot after 10 min
         quiet (~6 captured/day/designer), 30-day squash; 200 GB live
  BASE   + video: 20 GB new renders/month, 60 GB project sync; 500 GB live
  HEAVY  + photography: 3,000 RAW × 25 MB per shoot, 4 shoots/month; 1.5 TB live

All figures USD, us-east-1, on-demand, no free tiers, no reserved/savings plans.
Unit prices were fetched from the AWS Price List Bulk API
(https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<Service>/current/us-east-1/index.csv)
on 2026-09-29 unless marked "estimate" or "verify". Run with --verify-prices to
re-fetch the live SKUs and diff them against the constants below.

Usage:  python3 infra_model.py [--verify-prices] [--json]
"""
import argparse
import json
import sys

# ----------------------------------------------------------------------------
# 1. Unit prices
# ----------------------------------------------------------------------------
PRICE_LIST_DATE = "2026-09-29"
API = "AWS Price List Bulk API, us-east-1 offer file, fetched " + PRICE_LIST_DATE

# (key, description, price, unit, source, [live-check: service csv, usageType, operation-or-None, startingRange])
UNIT_PRICES = [
    # --- S3 ---
    ("s3_std_gbmo", "S3 Standard storage, first 50 TB", 0.023, "GB-month", API,
     ("AmazonS3", "TimedStorage-ByteHrs", None, "0")),
    ("s3_int_fa_gbmo", "S3 Intelligent-Tiering, Frequent Access tier", 0.023, "GB-month", API,
     ("AmazonS3", "TimedStorage-INT-FA-ByteHrs", None, "0")),
    ("s3_int_ia_gbmo", "S3 Intelligent-Tiering, Infrequent Access tier (>=30 d untouched)", 0.0125, "GB-month", API,
     ("AmazonS3", "TimedStorage-INT-IA-ByteHrs", None, "0")),
    ("s3_int_aia_gbmo", "S3 Intelligent-Tiering, Archive Instant Access tier (>=90 d untouched)", 0.004, "GB-month", API,
     ("AmazonS3", "TimedStorage-INT-AIA-ByteHrs", None, "0")),
    ("s3_int_monitor_per_obj", "S3 Intelligent-Tiering monitoring", 0.0000025, "object-month", API,
     ("AmazonS3", "Monitoring-Automation-INT", None, "0")),
    ("s3_int_early_delete_gbmo", "S3 Intelligent-Tiering early delete (<30 d), prorated to 30 d", 0.023, "GB-month", API,
     ("AmazonS3", "EarlyDelete-INT", None, "0")),
    ("s3_put_per_req", "S3 PUT/COPY/POST/LIST request", 0.000005, "request", API,
     ("AmazonS3", "Requests-Tier1", None, "0")),
    ("s3_get_per_req", "S3 GET/HEAD and other request", 0.0000004, "request", API,
     ("AmazonS3", "Requests-Tier2", None, "0")),
    ("s3_egress_internet_gb", "S3 data transfer out to internet, first 10 TB", 0.09, "GB", API,
     ("AWSDataTransfer", "DataTransfer-Out-Bytes", None, "0")),
    ("s3_to_cloudfront_gb", "S3 -> CloudFront origin fetch", 0.0, "GB", API,
     ("AWSDataTransfer", "USE1-CloudFront-Out-Bytes", None, "0")),
    # --- CloudFront (global offer file, US/Canada price class) ---
    ("cf_egress_us_gb", "CloudFront data transfer out to internet, US, first 10 TB", 0.085, "GB",
     "AWS Price List Bulk API, AmazonCloudFront global offer file, fetched " + PRICE_LIST_DATE, None),
    ("cf_https_per_req", "CloudFront HTTPS request, US", 0.000001, "request",
     "AWS Price List Bulk API, AmazonCloudFront global offer file, fetched " + PRICE_LIST_DATE, None),
    # --- Lambda (x86) ---
    ("lambda_gbs", "Lambda compute, x86, tier 1", 0.0000166667, "GB-second", API,
     ("AWSLambda", "Lambda-GB-Second", None, "0")),
    ("lambda_req", "Lambda request", 0.0000002, "request", API,
     ("AWSLambda", "Request", None, "0")),
    ("lambda_ephemeral_gbs", "Lambda ephemeral storage above 512 MB", 0.0000000309, "GB-second",
     "list price as of knowledge, verify", None),
    # --- DynamoDB on-demand ---
    ("ddb_wru", "DynamoDB on-demand write request unit", 0.000000625, "WRU", API,
     ("AmazonDynamoDB", "WriteRequestUnits", "PayPerRequestThroughput", "0")),
    ("ddb_rru", "DynamoDB on-demand read request unit", 0.000000125, "RRU", API,
     ("AmazonDynamoDB", "ReadRequestUnits", "PayPerRequestThroughput", "0")),
    ("ddb_storage_gbmo", "DynamoDB storage beyond 25 GB free", 0.25, "GB-month", API,
     ("AmazonDynamoDB", "TimedStorage-ByteHrs", None, "25")),
    ("ddb_stream_req", "DynamoDB Streams read request unit beyond free tier", 0.0000002, "request", API,
     ("AmazonDynamoDB", "USE1-Streams-Requests", "GetRecords", "2500000")),
    # --- AppSync ---
    ("appsync_op", "AppSync query/mutation", 0.000004, "operation", API,
     ("AWSAppSync", "USE1-GraphQLInvocation", None, "0")),
    ("appsync_rt_msg", "AppSync real-time update delivered", 0.000002, "message", API,
     ("AWSAppSync", "USE1-GraphQLNotification", None, "0")),
    ("appsync_conn_min", "AppSync subscription connection minute", 0.00000008, "minute", API,
     ("AWSAppSync", "USE1-ConnectionDuration", None, "0")),
    # --- MediaConvert ---
    ("mc_720p_min", "MediaConvert HD (720p) H.264 <=30fps single-pass, Basic tier, legacy per-minute SKU", 0.015, "output minute", API,
     ("AWSElementalMediaConvert", "IAD-B-AVC-HD-S-30", None, "0")),
    ("mc_ntm_basic_min", "MediaConvert Normalized Transcoding Minute, Basic tier, first 100k (newer SKU; multiplier per output resolution not modelled)", 0.0075, "NTM", API,
     ("AWSElementalMediaConvert", "IAD-Normalized-Transcode-Minute-Basic", None, "0")),
    # --- OpenSearch Serverless ---
    ("aoss_ocu_hr", "OpenSearch Serverless OCU-hour (indexing or search)", 0.24, "OCU-hour", API,
     ("AmazonES", "USE1-SearchOCU", "SearchOCU", "0")),
    ("aoss_storage_gbmo", "OpenSearch Serverless managed storage (S3-backed)", 0.024, "GB-month", API,
     ("AmazonES", "USE1-StorageUsedInS3ByteHour", "StorageUsedInS3ByteHour", "0")),
    # --- Fargate / ALB / NAT ---
    ("fargate_vcpu_hr", "Fargate x86 vCPU-hour", 0.04048, "vCPU-hour", API,
     ("AmazonECS", "USE1-Fargate-vCPU-Hours:perCPU", None, "0")),
    ("fargate_gb_hr", "Fargate x86 memory GB-hour", 0.004445, "GB-hour", API,
     ("AmazonECS", "USE1-Fargate-GB-Hours", None, "0")),
    ("alb_hr", "Application Load Balancer hour", 0.0225, "hour", API,
     ("AWSELB", "LoadBalancerUsage", "LoadBalancing:Application", "0")),
    ("alb_lcu_hr", "ALB capacity unit hour", 0.008, "LCU-hour", API,
     ("AWSELB", "LCUUsage", "LoadBalancing:Application", "0")),
    ("nat_hr", "NAT Gateway hour", 0.045, "hour",
     "AWS Price List Bulk API, AmazonEC2 us-east-1 offer file (usageType NatGateway-Hours), fetched " + PRICE_LIST_DATE, None),
    ("nat_gb", "NAT Gateway data processed", 0.045, "GB",
     "AWS Price List Bulk API, AmazonEC2 us-east-1 offer file (usageType NatGateway-Bytes), fetched " + PRICE_LIST_DATE, None),
    # --- Cognito ---
    ("cognito_mau", "Cognito Essentials MAU (first 10,000 MAU/month free platform-wide, ignored here)", 0.015, "MAU", API,
     ("AmazonCognito", "USE1-CognitoEssentialsMAU", "CognitoEssentialsOperation", "0")),
    # --- SQS / EventBridge / misc ---
    ("sqs_req", "SQS standard request", 0.0000004, "request", API,
     ("AWSQueueService", "Requests-RBP", None, "0")),
    ("eventbridge_evt", "EventBridge custom/S3 event", 0.000001, "event", "list price as of knowledge, verify", None),
    ("misc_platform_fixed", "Route 53 zone, CloudWatch logs/alarms, Secrets Manager, Amplify hosting of the Next.js app", 25.0, "USD/month", "estimate", None),
]
P = {k: v for k, _, v, *_ in UNIT_PRICES}

HOURS_PER_MONTH = 730

# ----------------------------------------------------------------------------
# 2. Workload assumptions (everything not given in the brief is an estimate)
# ----------------------------------------------------------------------------
ASSUMPTIONS = [
    # (name, value, unit, source)
    ("working_days", 22, "days/month", "estimate"),
    ("designers", 8, "people", "brief (WORKFLOWS §13)"),
    ("psd_gb", 2.0, "GB per working file", "brief"),
    ("saves_per_day", 20, "saves/designer/day", "brief"),
    ("captured_per_day", 6, "auto-snapshots actually captured/designer/day (10-min quiet rule)", "brief"),
    ("squash_days", 30, "days before auto-snapshots are squashed and their blobs GC'd (DESIGN §11.3)", "DESIGN.md"),
    ("milestones_per_week", 2, "explicit snapshots/designer/week that survive squash", "estimate"),
    ("history_months", 6, "months of milestone history accumulated at the modelled month (mid year one)", "estimate"),
    ("eager_upload", True, "every stable save is hashed and uploaded before snapshot (DESIGN §8 uploadDraftsEagerly=on)", "DESIGN.md"),
    ("gc_mean_residence_days", 4.0, "mean days an unreferenced draft blob sits in S3 (weekly GC + 24 h minimum age, DESIGN §11.2)", "estimate"),
    ("sync_fanout", 1.0, "other members whose synced folder pulls each auto-snapshot (DESIGN §8 pull replaces clean files); range 0–2.7", "estimate"),
    ("psd_chunk_reduction", 0.60, "bytes saved on PSD versions with content-defined chunking", "brief"),
    ("video_chunk_reduction", 0.40, "bytes saved on video re-exports with chunking", "brief"),
    ("raw_chunk_reduction", 0.0, "bytes saved on RAW with chunking", "brief"),
    ("preview_fraction_of_live", 0.02, "preview variants as a fraction of live bytes (DESIGN §11)", "DESIGN.md"),
    ("preview_lambda_gb", 3.0, "Lambda memory for Sharp/ImageMagick preview render", "brief"),
    ("preview_lambda_s", 20.0, "seconds per image preview (2 GB PSD or 25 MB RAW)", "brief"),
    ("preview_on_put", True, "previews are triggered by S3 PUT (DESIGN §7), so eager-uploaded drafts are rendered too", "DESIGN.md"),
    ("int_long_lived_split", (0.5, 0.3, 0.2), "share of long-lived bytes in INT Frequent / Infrequent / Archive-Instant tiers", "estimate"),
    ("avg_object_mb_live", 20, "average live object size, for INT monitoring and request counts", "estimate"),
    ("multipart_part_mb", 64, "multipart part size (DESIGN §6)", "DESIGN.md"),
    ("ui_reads_per_user_day", 300, "DynamoDB reads per active web user per day", "estimate"),
    ("appsync_ops_per_user_day", 300, "AppSync operations per active user per day (web + desktop client)", "estimate"),
    ("active_users", 15, "team members using the app", "brief"),
    ("guest_mau", 10, "client guests signing in per month", "estimate"),
    ("desktop_online_hours_day", 8, "hours/day a desktop client holds an AppSync subscription", "estimate"),
    ("preview_cf_gb_light", 20, "GB/month of thumbnails/medium previews viewed via CloudFront, designers", "estimate"),
    ("release_dl_gb_light", 30, "GB/month of release bundles downloaded by clients via CloudFront (3 projects × 2 rounds × 1 GB × 5 downloads)", "estimate"),
    ("team_restore_gb_light", 50, "GB/month of originals pulled by the team outside sync (restores, new machine, compare)", "estimate"),
    # video (BASE)
    ("editors", 2, "video editors", "brief"),
    ("prproj_mb", 50, "MB per Premiere/AE project file auto-snapshot", "estimate"),
    ("renders_gb_month", 20, "GB/month of new renders (kept as milestones)", "brief"),
    ("project_sync_gb_month", 60, "GB/month of footage synced up once and pulled once by the second editor", "brief"),
    ("mc_source_min", 300, "minutes/month of new video source proxied to 720p", "brief"),
    ("proxy_mb_per_min", 15, "MB per minute of 720p proxy (~2 Mbps)", "estimate"),
    ("proxy_views", 5, "times each proxy is streamed in the month", "estimate"),
    ("release_dl_gb_video", 40, "GB/month extra release bundle egress for video (2 releases × 4 GB × 5 downloads)", "estimate"),
    # photography (HEAVY)
    ("shoots", 4, "shoots/month", "brief"),
    ("raw_per_shoot", 3000, "RAW files per shoot", "brief"),
    ("raw_mb", 25, "MB per RAW", "brief"),
    ("raw_select_fraction", 0.10, "share of RAWs pulled by a retoucher via presigned S3 GET", "estimate"),
    ("release_dl_gb_photo", 36, "GB/month extra delivery egress for photo finals (3 GB × 4 shoots × 3 downloads)", "estimate"),
    ("preview_cf_gb_photo", 6, "GB/month extra preview egress from browsing 12,000 RAW thumbnails", "estimate"),
    # platform
    ("aoss_ocus", 2, "OpenSearch Serverless OCUs billed 24×7 (1 indexing + 1 search, redundancy off); production redundancy = 4, dev/test = 1", "verify (AWS minimum OCU rules changed in 2024–25)"),
    ("bridge_vcpu", 0.5, "Fargate vCPU for the Git bridge task, 24×7", "estimate"),
    ("bridge_gb", 1.0, "Fargate memory GB for the Git bridge task", "estimate"),
    ("nat_gb_month", 50, "GB/month through NAT (S3 uses a free gateway endpoint; NAT only carries misc egress)", "estimate"),
    ("customers_for_amortisation", 20, "paying customers over which platform-fixed cost is amortised in the notes", "estimate"),
]
A = {k: v for k, v, *_ in ASSUMPTIONS}


# ----------------------------------------------------------------------------
# 3. Model
# ----------------------------------------------------------------------------
def gb(mb):
    return mb / 1024.0


def s3_int_long_lived_cost(gb_month):
    fa, ia, aia = A["int_long_lived_split"]
    return gb_month * (fa * P["s3_int_fa_gbmo"] + ia * P["s3_int_ia_gbmo"] + aia * P["s3_int_aia_gbmo"])


def scenario(name, live_gb, video=False, photo=False, chunk=False):
    wd = A["working_days"]
    d = A["designers"]
    psd = A["psd_gb"]
    r_psd = A["psd_chunk_reduction"] if chunk else 0.0
    r_vid = A["video_chunk_reduction"] if chunk else 0.0
    r_raw = A["raw_chunk_reduction"] if chunk else 0.0

    lines = []      # (label, usd)
    arith = []      # human-readable arithmetic
    st = {}         # storage pools in GB-month

    # ---- Designers: eager uploads, auto-snapshots, milestones -------------
    saves_month = d * A["saves_per_day"] * wd                      # files uploaded
    upload_psd_gb = saves_month * psd * (1 - r_psd)
    captured_month = d * A["captured_per_day"] * wd
    auto_retained_gb = captured_month * psd * (1 - r_psd)          # lives ~30 d, so steady state = one month's production
    milestones_month = d * A["milestones_per_week"] * (wd / 5.0)
    milestone_gb_month = milestones_month * psd * (1 - r_psd)
    milestone_hist_gb = milestone_gb_month * A["history_months"]
    uncaptured_month = saves_month - captured_month
    transient_gb_month = uncaptured_month * psd * (1 - r_psd) * (A["gc_mean_residence_days"] / 30.0) if A["eager_upload"] else 0.0
    arith += [
        f"saves: {d} designers × {A['saves_per_day']}/day × {wd} days = {saves_month:,} saves × {psd} GB × (1-{r_psd:.0%}) = {upload_psd_gb:,.0f} GB uploaded/month (eager)",
        f"captured auto-snapshots: {d} × {A['captured_per_day']}/day × {wd} = {captured_month:,} × {psd} GB × (1-{r_psd:.0%}) = {auto_retained_gb:,.0f} GB; squash at {A['squash_days']} d ⇒ steady-state retained ≈ {auto_retained_gb:,.0f} GB",
        f"milestones: {d} × {A['milestones_per_week']}/wk × {wd/5:.1f} wk = {milestones_month:.0f}/month × {psd} GB × (1-{r_psd:.0%}) = {milestone_gb_month:,.0f} GB/month permanent; at month {A['history_months']}: {milestone_hist_gb:,.0f} GB",
        f"uncaptured drafts: ({A['saves_per_day']}-{A['captured_per_day']}) × {d} × {wd} = {uncaptured_month:,} blobs × {psd} GB × (1-{r_psd:.0%}) × {A['gc_mean_residence_days']}/30 d residence = {transient_gb_month:,.0f} GB-month transient (S3 Standard; INT would bill 30 d each)",
    ]
    st["live"] = live_gb
    st["auto_snapshot_window"] = auto_retained_gb
    st["milestone_history"] = milestone_hist_gb
    st["transient_drafts"] = transient_gb_month
    st["previews"] = live_gb * A["preview_fraction_of_live"]

    upload_gb = upload_psd_gb
    egress_s3_gb = A["team_restore_gb_light"] + auto_retained_gb * A["sync_fanout"]
    arith.append(f"sync fan-out: {auto_retained_gb:,.0f} GB of snapshots × {A['sync_fanout']} pulling colleagues = {auto_retained_gb*A['sync_fanout']:,.0f} GB presigned-S3 egress")
    egress_cf_gb = A["preview_cf_gb_light"] + A["release_dl_gb_light"]
    put_files = saves_month
    put_parts = saves_month * (psd * 1024 / A["multipart_part_mb"] + 3)   # parts + initiate + complete + verify HEAD
    image_previews = saves_month if A["preview_on_put"] else captured_month + milestones_month
    commits = captured_month + milestones_month
    mc_minutes = 0

    # ---- Video (BASE) ------------------------------------------------------
    if video:
        e = A["editors"]
        prproj_gb = gb(A["prproj_mb"])
        prproj_auto = e * A["captured_per_day"] * wd * prproj_gb * (1 - r_psd)
        renders_hist = A["renders_gb_month"] * (1 - r_vid) * A["history_months"]
        st["auto_snapshot_window"] += prproj_auto
        st["milestone_history"] += renders_hist
        st["video_proxies"] = A["mc_source_min"] * gb(A["proxy_mb_per_min"]) * A["history_months"]
        upload_gb += e * A["saves_per_day"] * wd * prproj_gb + A["renders_gb_month"] * (1 - r_vid) + A["project_sync_gb_month"]
        egress_s3_gb += A["project_sync_gb_month"] * 1.0 + prproj_auto * A["sync_fanout"]
        egress_cf_gb += A["release_dl_gb_video"] + A["mc_source_min"] * gb(A["proxy_mb_per_min"]) * A["proxy_views"]
        put_files += e * A["saves_per_day"] * wd
        put_parts += (A["renders_gb_month"] + A["project_sync_gb_month"]) * 1024 / A["multipart_part_mb"] + 200
        commits += e * A["captured_per_day"] * wd
        mc_minutes = A["mc_source_min"]
        arith += [
            f"video: project files {e} × {A['captured_per_day']}/day × {wd} × {A['prproj_mb']} MB = {prproj_auto:,.1f} GB in the 30-day window; renders {A['renders_gb_month']} GB × (1-{r_vid:.0%}) × {A['history_months']} months = {renders_hist:,.0f} GB history; sync {A['project_sync_gb_month']} GB up + {A['project_sync_gb_month']} GB down; MediaConvert {mc_minutes} min",
        ]

    # ---- Photography (HEAVY) ----------------------------------------------
    if photo:
        raws = A["shoots"] * A["raw_per_shoot"]
        raw_gb = raws * gb(A["raw_mb"]) * (1 - r_raw)
        # RAWs never change, so they are in the head tree and therefore inside the given live figure;
        # the live figure grows by raw_gb every month (reported, not double counted).
        upload_gb += raw_gb
        egress_s3_gb += raw_gb * A["raw_select_fraction"]
        egress_cf_gb += A["release_dl_gb_photo"] + A["preview_cf_gb_photo"]
        put_files += raws
        put_parts += raws * 3   # single PUT + HEAD verify + batch bookkeeping
        image_previews += raws
        commits += A["shoots"] * 3
        arith.append(f"photo: {A['shoots']} shoots × {A['raw_per_shoot']} × {A['raw_mb']} MB = {raw_gb:,.0f} GB/month uploaded, 0% dedup; live grows {raw_gb:,.0f} GB/month (inside the {live_gb:,.0f} GB live figure at the modelled month)")

    # ---- Storage cost -----------------------------------------------------
    long_lived = st["live"] + st["milestone_history"] + st["previews"] + st.get("video_proxies", 0.0)
    churn = st["auto_snapshot_window"]           # gone in 30 d: always Frequent Access, INT saves nothing
    transient = st["transient_drafts"]           # must stay Standard: INT early-delete would bill 30 d
    stored_gb = long_lived + churn + transient
    s3_std_all = stored_gb * P["s3_std_gbmo"]
    s3_int = s3_int_long_lived_cost(long_lived) + churn * P["s3_int_fa_gbmo"] + transient * P["s3_std_gbmo"]
    objects = long_lived * 1024 / A["avg_object_mb_live"]
    s3_int += objects * P["s3_int_monitor_per_obj"]
    int_trap = (uncaptured_month * psd * (1 - r_psd)) * P["s3_int_early_delete_gbmo"]   # if drafts were PUT straight into INT
    lines.append(("S3 storage (Intelligent-Tiering on long-lived, Standard on churn/transient)", s3_int))
    arith.append(f"storage: long-lived {long_lived:,.0f} + 30-day window {churn:,.0f} + transient {transient:,.0f} = {stored_gb:,.0f} GB-month; all-Standard ${s3_std_all:,.2f}, with INT ${s3_int:,.2f}; if drafts were PUT straight into INT the early-delete charge alone would be ${int_trap:,.2f}")

    # ---- Requests ---------------------------------------------------------
    s3_put_cost = put_parts * P["s3_put_per_req"]
    s3_get_reqs = (egress_s3_gb * 1024 / A["multipart_part_mb"]) + put_files * 2 + A["active_users"] * 500 * wd
    s3_get_cost = s3_get_reqs * P["s3_get_per_req"]
    lines.append(("S3 PUT/multipart requests", s3_put_cost))
    lines.append(("S3 GET/HEAD requests", s3_get_cost))

    # ---- Egress -----------------------------------------------------------
    lines.append(("S3 egress to internet (presigned originals: sync pulls, restores, selects)", egress_s3_gb * P["s3_egress_internet_gb"]))
    cf_reqs = A["active_users"] * 2000 * wd + (A["guest_mau"] * 300)
    # origin fetch S3 -> CloudFront is $0 (s3_to_cloudfront_gb), so only the edge egress is billed
    lines.append(("CloudFront data transfer (previews, proxies, release bundles)", egress_cf_gb * (P["cf_egress_us_gb"] + P["s3_to_cloudfront_gb"])))
    lines.append(("CloudFront HTTPS requests", cf_reqs * P["cf_https_per_req"]))

    # ---- Lambda -----------------------------------------------------------
    prev_gbs = image_previews * A["preview_lambda_s"] * A["preview_lambda_gb"]
    # ephemeral disk to hold the source + flattened composite: ~2× file size above the free 512 MB (negligible)
    prev_eph = image_previews * A["preview_lambda_s"] * max(0.0, psd * 2 - 0.5) * P["lambda_ephemeral_gbs"]
    lines.append(("Lambda previews (Sharp/ImageMagick, 3 GB, 20 s)", prev_gbs * P["lambda_gbs"] + image_previews * P["lambda_req"] + prev_eph))
    api_invocations = commits + put_files * 2 + A["active_users"] * A["appsync_ops_per_user_day"] * wd
    api_gbs = api_invocations * 0.3 * 0.5
    lines.append(("Lambda API (commit, batchObjects, verify, authorize)", api_gbs * P["lambda_gbs"] + api_invocations * P["lambda_req"]))
    arith.append(f"previews: {image_previews:,.0f} renders × {A['preview_lambda_s']:.0f} s × {A['preview_lambda_gb']:.0f} GB = {prev_gbs:,.0f} GB-s")

    # ---- DynamoDB ---------------------------------------------------------
    wru = commits * 15 + put_files * 3 + A["active_users"] * 8 * wd + commits * 5  # trees/commit/ref + blob rows + lock refresh + AssetIndex/Activity via stream
    if photo:
        wru += A["shoots"] * 3 * 300   # 3,000-entry directory tree items are ~300 KB each
    rru = commits * 30 + put_files * 2 + A["active_users"] * A["ui_reads_per_user_day"] * wd
    lines.append(("DynamoDB on-demand reads/writes", wru * P["ddb_wru"] + rru * P["ddb_rru"]))

    # ---- AppSync ----------------------------------------------------------
    ops = A["active_users"] * A["appsync_ops_per_user_day"] * wd + commits + put_files * 2
    rt = (commits + put_files) * A["active_users"]
    conn = A["active_users"] * A["desktop_online_hours_day"] * 60 * wd
    lines.append(("AppSync operations, real-time updates, connections", ops * P["appsync_op"] + rt * P["appsync_rt_msg"] + conn * P["appsync_conn_min"]))

    # ---- SQS / EventBridge for the preview pipeline -----------------------
    lines.append(("EventBridge + SQS (preview pipeline)", image_previews * (P["eventbridge_evt"] + 3 * P["sqs_req"])))

    # ---- MediaConvert -----------------------------------------------------
    lines.append(("MediaConvert 720p H.264 proxies", mc_minutes * P["mc_720p_min"]))

    # ---- Cognito ----------------------------------------------------------
    lines.append(("Cognito MAU (team + guests)", (A["active_users"] + A["guest_mau"]) * P["cognito_mau"]))

    total = sum(v for _, v in lines)
    return {
        "scenario": name,
        "dedup": "chunk" if chunk else "whole-file",
        "storedGB": round(stored_gb, 1),
        "uploadGB": round(upload_gb, 1),
        "egressGB": round(egress_s3_gb + egress_cf_gb, 1),
        "egress_s3_gb": round(egress_s3_gb, 1),
        "egress_cf_gb": round(egress_cf_gb, 1),
        "totalUSD": round(total, 2),
        "lines": [(l, round(v, 2)) for l, v in lines],
        "pools": {k: round(v, 1) for k, v in st.items()},
        "s3_all_standard_usd": round(s3_std_all, 2),
        "int_early_delete_trap_usd": round(int_trap, 2),
        "arith": arith,
    }


def platform_fixed():
    items = [
        ("OpenSearch Serverless, %d OCU × 730 h × $%.2f" % (A["aoss_ocus"], P["aoss_ocu_hr"]), A["aoss_ocus"] * HOURS_PER_MONTH * P["aoss_ocu_hr"]),
        ("OpenSearch Serverless index storage (10 GB)", 10 * P["aoss_storage_gbmo"]),
        ("NAT Gateway, 1 AZ, 730 h + %d GB" % A["nat_gb_month"], HOURS_PER_MONTH * P["nat_hr"] + A["nat_gb_month"] * P["nat_gb"]),
        ("Fargate Git bridge, %.1f vCPU / %.0f GB, 24×7" % (A["bridge_vcpu"], A["bridge_gb"]),
         HOURS_PER_MONTH * (A["bridge_vcpu"] * P["fargate_vcpu_hr"] + A["bridge_gb"] * P["fargate_gb_hr"])),
        ("ALB for the bridge, 730 h + ~1 LCU", HOURS_PER_MONTH * (P["alb_hr"] + P["alb_lcu_hr"])),
        ("CloudFront distribution minimum", 0.0),
        ("Cognito user pool minimum (Essentials free tier covers 10k MAU)", 0.0),
        ("Misc: Route 53, CloudWatch, Secrets Manager, Amplify hosting (estimate)", P["misc_platform_fixed"]),
    ]
    return items, sum(v for _, v in items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-prices", action="store_true", help="re-fetch live SKUs from the AWS Price List API and diff")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fanout", type=float, default=None, help="override sync_fanout")
    args = ap.parse_args()
    if args.fanout is not None:
        A["sync_fanout"] = args.fanout

    if args.verify_prices:
        verify_prices()
        return

    results = []
    for chunk in (False, True):
        results.append(scenario("LIGHT", 200, chunk=chunk))
        results.append(scenario("BASE", 500, video=True, chunk=chunk))
        results.append(scenario("HEAVY", 1536, video=True, photo=True, chunk=chunk))
    fixed_items, fixed_total = platform_fixed()

    if args.json:
        print(json.dumps({"scenarios": results, "platform_fixed": fixed_items, "platform_fixed_total": fixed_total,
                          "unit_prices": [(k, d, p, u, s) for k, d, p, u, s, *_ in UNIT_PRICES],
                          "assumptions": [(k, str(v), u, s) for k, v, u, s in ASSUMPTIONS]}, indent=1))
        return

    print("GitDAM per-customer monthly AWS cost model (USD, us-east-1, on-demand, no free tiers)")
    print("Prices: AWS Price List Bulk API fetched", PRICE_LIST_DATE, "unless marked estimate/verify\n")
    print("== Unit prices ==")
    for k, d, p, u, s, *_ in UNIT_PRICES:
        print(f"  {k:28s} {p:>14.10f} /{u:12s} {d}  [{s}]")
    print("\n== Assumptions ==")
    for k, v, u, s in ASSUMPTIONS:
        print(f"  {k:28s} {str(v):>12s}  {u}  [{s}]")

    print("\n== Per-customer monthly cost ==")
    print(f"  {'scenario':8s} {'dedup':10s} {'stored GB':>10s} {'upload GB':>10s} {'egress GB':>10s} {'S3 direct':>10s} {'CF':>8s} {'total $':>9s}")
    for r in results:
        print(f"  {r['scenario']:8s} {r['dedup']:10s} {r['storedGB']:>10,.0f} {r['uploadGB']:>10,.0f} {r['egressGB']:>10,.0f} {r['egress_s3_gb']:>10,.0f} {r['egress_cf_gb']:>8,.0f} {r['totalUSD']:>9,.2f}")

    for r in results:
        print(f"\n--- {r['scenario']} / {r['dedup']} : ${r['totalUSD']:,.2f}/month ---")
        for l, v in sorted(r["lines"], key=lambda x: -x[1]):
            print(f"  {v:>9,.2f}  {l}")
        print("  storage pools (GB-month):", r["pools"])
        for a in r["arith"]:
            print("   •", a)

    print("\n== Platform fixed (independent of customer count) ==")
    for l, v in fixed_items:
        print(f"  {v:>9,.2f}  {l}")
    print(f"  {fixed_total:>9,.2f}  TOTAL  (dev/test 1-OCU OpenSearch: ${fixed_total - HOURS_PER_MONTH*P['aoss_ocu_hr']*(A['aoss_ocus']-1):,.2f}; production 4-OCU: ${fixed_total + HOURS_PER_MONTH*P['aoss_ocu_hr']*(4-A['aoss_ocus']):,.2f}; before OpenSearch ships (Phase 1–2): ${fixed_total - HOURS_PER_MONTH*P['aoss_ocu_hr']*A['aoss_ocus'] - 10*P['aoss_storage_gbmo']:,.2f})")

    n = A["customers_for_amortisation"]
    print(f"\n== Price needed for 70% gross margin (ASSUMPTIONS.md T2 pass bar), fixed amortised over {n} customers ==")
    for r in results:
        cost = r["totalUSD"] + fixed_total / n
        print(f"  {r['scenario']:8s} {r['dedup']:10s} variable ${r['totalUSD']:,.2f} + fixed/{n} ${fixed_total/n:,.2f} = ${cost:,.2f}  ⇒ price ≥ ${cost/0.3:,.0f}/month  (≈ ${cost/0.3/r['pools']['live']:,.2f} per live GB)")

    print("\n== Sensitivity: sync fan-out (colleagues pulling every auto-snapshot) ==")
    for f in (0.0, 0.5, 1.0, 2.7):
        A["sync_fanout"] = f
        row = [scenario("LIGHT", 200, chunk=c)["totalUSD"] for c in (False, True)]
        print(f"  fan-out {f:3.1f}: LIGHT whole-file ${row[0]:,.2f}  chunk ${row[1]:,.2f}")
    A["sync_fanout"] = 1.0


def verify_prices():
    """Re-fetch the live SKUs and diff against the constants (needs egress to pricing.us-east-1.amazonaws.com)."""
    import csv
    import io
    import urllib.request
    cache = {}
    base = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{}/current/us-east-1/index.csv"
    for k, d, p, u, s, chk in UNIT_PRICES:
        if not chk:
            continue
        svc, ut, op, start = chk
        if svc not in cache:
            try:
                raw = urllib.request.urlopen(base.format(svc), timeout=60).read().decode()
            except Exception as e:  # noqa
                print(f"  {k}: fetch failed for {svc}: {e}")
                cache[svc] = None
                continue
            cache[svc] = list(csv.DictReader(io.StringIO("".join(raw.splitlines(True)[5:]))))
        rows = cache[svc]
        if rows is None:
            continue
        hit = [r for r in rows if r["TermType"] == "OnDemand" and r["usageType"] == ut
               and (op is None or r["operation"] == op) and r["StartingRange"] == start]
        if not hit:
            print(f"  {k}: NOT FOUND ({svc} {ut} {op} {start})")
            continue
        live = float(hit[0]["PricePerUnit"])
        flag = "OK" if abs(live - p) < 1e-12 else f"CHANGED (model {p} live {live})"
        print(f"  {k:28s} {flag}")


if __name__ == "__main__":
    main()
