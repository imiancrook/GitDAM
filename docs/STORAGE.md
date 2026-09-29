# Storage: managed tiers and bring-your-own

Decision record and design for how GitDAM stores bytes and charges for them. Supersedes the storage parts of VISION's pricing principles and DESIGN §2.1/§6/§11 where they differ. Numbers reference [FINAL_REVIEW.md](./FINAL_REVIEW.md) §4–5 and are hand-derived from its model components; the model scripts still need the provider switch (see §8).

## 1. The decision

Storage is a completely separate purchase from the service. Two lines on every invoice:

1. **The service.** One price per tier for the software: history, locks, explorations, releases, issues, the desktop client, unlimited guests. It includes **no storage at all**.
2. **Storage.** The customer picks one of:
   - **A managed storage size.** GitDAM-hosted, sold in sizes (250 GB, 1 TB, 2 TB, 5 TB, 10 TB, custom), bandwidth included, change size any time.
   - **Their own bucket.** S3, Cloudflare R2, Backblaze B2, Wasabi or Google Cloud Storage. Storage line is $0; the customer pays their provider. GitDAM keeps the metadata, history, locks, issues, releases and previews; the bucket keeps the bytes.

Nothing about the service depends on which storage is chosen, and the customer can switch storage without touching the service. The two are separate products that happen to appear on one bill.

Why: the service price stops carrying storage risk, so it can be published and stable; the storage line is transparent and the customer sizes it; and "connect your own" is the strongest answer to lock-in, because the bytes were never ours. Managed sizes are how a 12-person agency starts in thirty minutes; a connected bucket is how a studio, a brand's IT department or a regulated customer says yes.

## 2. Pricing structure

Prices are proposals consistent with FINAL_REVIEW's unit costs; the T1 interviews set the final numbers.

**Service** (per organization per month):

| | Solo | Studio | Plus |
|---|---|---|---|
| Service fee | $15 | $149 | $499 |
| Who | Lena | Rachel's agency | 30–60 person studios, brands |
| Includes | history, locks, explorations, releases, issues, desktop client, unlimited guests, 30-day auto-snapshot retention, milestones forever | same | same + SSO/SCIM, audit export, customer-managed keys, priority support, MSA |
| Editors included | 1 | 20, then $10/editor | 60, then $8/editor |
| Storage included | **none** | **none** | **none** |

**Storage** (per organization per month, chosen separately, any tier):

| Managed size | Price | Effective per TB | Notes |
|---|---|---|---|
| 250 GB | $6 | $24 | the Solo default |
| 1 TB | $20 | $20 | |
| 2 TB | $36 | $18 | the Studio default |
| 5 TB | $80 | $16 | |
| 10 TB | $150 | $15 | |
| Custom, 20 TB+ | quoted | ~$12–14 | |
| **Your own bucket** | **$0** | | any tier; self-serve on Solo, supported on Studio and Plus |

Bandwidth is included on managed sizes. Sizes can be changed at any time; going over a size for more than 7 days prompts a resize rather than billing overage silently.

What a managed size holds is **retained GB**: live files plus version history inside the retention window plus milestones. The usage view (WORKFLOWS 5.5) shows the split ("1.2 TB live, 0.6 TB of the last 30 days' saves, 0.3 TB of milestones") with the retention dial next to it, so the customer decides how much history to keep and what size to buy. On a connected bucket the same view shows the same split against their provider's bill.

The editor guard stays in the service tier, because the service's residual cost (previews, metadata, processing) scales with editors × saves, not with GB.

Illustration for the reference agency: Studio service $149 + 2 TB managed $36 = **$185/month**, or Studio service $149 + their own B2 bucket ≈ $149 + roughly $15 paid to Backblaze. Today's stack for the same agency is about $398 (FINAL_REVIEW §5).

## 3. Economics under each option

Managed storage runs on a zero-egress provider (R2 or B2; §5), not S3, because egress was 68% of the as-designed cost. Hand-derived from FINAL_REVIEW §4's LIGHT agency components (200 GB live, 3,818 GB retained as designed, 2,212 GB/month egress):

| Studio, LIGHT workload | COGS/month | Revenue/month (service + storage) | Gross margin |
|---|---|---|---|
| Managed on S3, as designed (FINAL_REVIEW config A; 3.8 TB retained → 5 TB size) | $286 | $149 + $80 = $229 | negative |
| Managed on B2, as designed (5 TB size) | ~$35 | $229 | ~85% |
| Managed on B2, config D (chunk dedup, pull-on-demand; 1.65 TB retained → 2 TB size) | ~$22 | $149 + $36 = $185 | ~88% |
| Managed on R2, config D | ~$35 | $185 | ~81% |
| **Own bucket**, any provider | ~$8–15 (previews compute and storage, metadata, requests) | $149 | ~90–95% |

The storage line on its own is a thin-margin product on purpose (B2 costs GitDAM ~$6/TB and sells at $15–24/TB; the gap pays for bandwidth, previews of what's stored, and operations). The service line is where the margin is, and it is the same whichever storage the customer picks.

Two things follow. First, moving managed storage off S3 makes the design as written profitable without the three configuration-D changes; those become margin improvements, and chunk dedup (2–3 EM) leaves the Phase 2 critical path. Second, BYO customers are the most profitable customers and the ones with the largest files, which is the opposite of the S3-only model where video customers were the least profitable.

Prices are list as of the model's date; verify. The retained-GB overage under "as designed" ($70) would be visible to the customer in the usage view with the retention dial next to it; most will shorten the window or accept it. Either is fine for GitDAM.

## 4. How BYO works

### 4.1 One abstraction, per project

```
StorageBackend
  id, orgId, kind: managed | s3 | r2 | b2 | wasabi | gcs
  bucket, region, prefix, endpoint
  auth: { roleArn, externalId } | { secretRef }      # S3: cross-account role; others: scoped API key in Secrets Manager
  previewsIn: managed | same-bucket
  status: ok | degraded | unreachable, lastCheckedAt, lastError
  createdBy, createdAt

Project.storageBackendId                            # every project has exactly one
Blob (backendId, oid) PK                            # dedup is per backend, never across
```

Every blob operation already goes through GitDAM's Lambdas, which presign URLs (DESIGN §6). The adapter changes what they sign with and where. Clients and the Git bridge never know which backend they're talking to; they get a URL.

### 4.2 Connecting a bucket

Project settings → Storage → **Use your own bucket**. The wizard:

1. Pick a provider. For S3: download a CloudFormation template that creates a bucket policy and a cross-account IAM role with an external ID; paste the role ARN. No long-lived keys. For R2, B2, Wasabi, GCS: create an API key scoped to one bucket, paste it; it is stored in Secrets Manager under the org's KMS key and never displayed again.
2. GitDAM writes and reads a canary object, checks multipart, checksums, lifecycle permissions, and CORS for browser uploads; reports each with a fix-it hint.
3. Shows an **estimated monthly cost at the provider** from the project's current usage profile (retained GB × their storage price, plus their egress price × observed download volume), so an S3 customer sees that egress is now their bill before they commit.
4. Choose where previews live (§4.4). Done. New projects can be created on a connected backend; existing projects migrate (§4.6).

### 4.3 Uploads, downloads, integrity

Same batch protocol. Presigned PUT/GET against the customer's endpoint; multipart via the same flow. Integrity: the server-side stream-and-hash pass required by FINAL_REVIEW A3 runs for every backend, because checksum semantics differ between providers (S3 composite checksums, B2 SHA-1, R2 partial support). That pass reads the object once from the customer's bucket; on S3 that is customer egress at ~$0.09/GB, disclosed in the wizard estimate; on zero-egress providers it is free.

### 4.4 Previews and processing

The preview pipeline (DESIGN §7) pulls the original from the backend, renders, and writes derivatives. Default: derivatives go to **GitDAM's managed store** so the CDN, signed cookies and release pages work identically for every customer; the customer's bucket holds only originals. Plus-tier option: derivatives in the customer's bucket under `previews/`, served through their CDN or through GitDAM's edge with origin fetch. Processing compute stays GitDAM's cost (in the ~$8–15 BYO COGS).

### 4.5 What stays per-backend

- **Dedup** is per backend. No cross-tenant dedup anywhere, which also resolves the existence-oracle and takedown findings (FINAL_REVIEW A4) at the root.
- **GC** runs per backend with the same mark/sweep and `lastReferencedAt` rule; on BYO it deletes from the customer's bucket, so the trash-prefix window is kept and the wizard asks for a lifecycle rule rather than hard deletes.
- **Quota** is not enforced on BYO; usage is still shown.
- **Cross-org delivery** between different backends is a server-side copy where provider and account allow (`CopyObject` within S3, B2 copy) and a Fargate stream otherwise; the wizard's estimate includes it if the org receives deliveries.
- **Org export** for BYO is metadata only; the customer already has the bytes. This is a selling point: "export" is a JSON file and a Git bundle, and there is nothing to download.

### 4.6 Moving between managed and BYO

A background job copies blobs (verifying each hash on arrival), writes `Blob` rows for the new backend, flips `Project.storageBackendId`, and leaves the old blobs in place for 30 days before GC. Snapshots continue during the copy: new blobs are written to both backends until the flip. Content addressing makes the migration verifiable and restartable. Going back is the same job in reverse.

### 4.7 Failure modes

- Credentials revoked or bucket deleted: `status: unreachable`, the desktop client queues snapshots locally with a banner, uploads resume when fixed, and no history is lost because blobs are content-addressed and can be re-sent.
- Customer edits or deletes objects in their bucket directly: the weekly Blob-rows-vs-inventory reconciliation (FINAL_REVIEW A6) flags missing oids, the affected snapshots show as "content missing", and the customer is told which files. GitDAM never claims durability for BYO; the MSA says so.
- Provider outage: same as above, transient.

## 5. Which provider for managed storage

| | S3 | Cloudflare R2 | Backblaze B2 |
|---|---|---|---|
| Storage | $0.023/GB | $0.015/GB | $0.006/GB |
| Egress | $0.09/GB | free | free up to 3× average stored, then $0.01/GB |
| Regions | everywhere | US/EU/APAC hints, EU jurisdiction restriction available | US West, US East, EU Central |
| Lifecycle, multipart, event notifications | yes | yes | yes |
| SSE with customer keys | yes | limited | server-side only |
| Fit | residency anywhere, CMK, AWS-native previews | zero egress, near S3 | cheapest, zero egress in practice |

Recommendation: **B2 as the default managed store** (US and EU), **R2 where a customer needs a jurisdiction B2 doesn't cover**, and **S3 only for Plus customers who require customer-managed keys or a specific AWS region**. All three sit behind the same adapter, so the choice per org is configuration. Prices are list as of my knowledge; verify before publishing.

## 6. Who gets what, by persona

| Persona | Default | Why |
|---|---|---|
| Maya, Rachel (Studio) | Service + a managed size (2 TB) | Thirty-minute onboarding; the storage line is one number they chose |
| Lena (Solo) | Service + 250 GB managed; own bucket allowed but self-serve only | Support on a connected bucket would exceed the $15 fee, so no wizard hand-holding on Solo |
| Priya's post house | Managed; BYO if they already own a Wasabi/B2 bucket for footage | Many post houses already do |
| Sam's studio | BYO on their existing S3, or managed | They have an AWS account and a build pipeline |
| Marcus, Devon (Plus) | BYO on the company's S3 with CMK, or managed on S3 in their region | Ownership, residency, audit; SOC 2 questionnaire answers get shorter |

## 7. What changes in the plan

- **Phase 1:** build `StorageBackend` and the adapter with two implementations (managed-on-B2, S3) from the start. About +1 EM now; retrofitting after data exists would be several. Managed default on B2 means the S3-specific cost findings mostly dissolve.
- **Phase 2:** chunk-level dedup and pull-on-demand move from "required for survival" to "margin improvements"; keep pull-on-demand (it is also better for laptops on hotel Wi-Fi), defer chunk dedup until a video customer's bill shows the need.
- **Phase 3:** the BYO wizard, the retention dial and the storage split in the usage view ship together; they are the same feature seen from three sides.
- **Phase 5:** BYO previews-in-bucket, GCS and Wasabi adapters, cross-backend delivery copies.
- **ASSUMPTIONS:** T2's pass bar becomes "managed on B2/R2 ≥ 80% at Studio; BYO ≥ 90%"; T12 (egress) is retired for managed storage and becomes a BYO-wizard disclosure.
- **Pricing principles (VISION):** the service includes no storage; storage is a separate purchase, a managed size or a connected bucket; "bandwidth included" holds for managed sizes; on a connected bucket it is the customer's provider's business.
- **P&L model:** revenue becomes two lines (service by tier; storage by size or $0), and tier mix gains a managed/own-bucket split. Storage revenue is low-margin and should be reported separately so service margin is not diluted in the headline.

## 8. Open items

1. Add a `--provider s3|r2|b2` switch and a BYO scenario to `docs/financials/infra_model.py`, then re-run `reconciled_model.py`; §3's table is hand-derived from the model's components and should be replaced by the model's output. Expect base-case breakeven to move in by several months, mostly from the S3→B2 change.
2. Verify current R2 and B2 prices, B2's 3× egress rule, and R2's checksum support for `x-amz-checksum-sha256`.
3. Decide whether Solo can ever have BYO (probably as a self-serve, no-support option later).
4. Decide the managed-storage durability and RPO promise per provider for the MSA.
