# GitDAM: final review

Date: 2026-09-29. Written for the project owner. This document is meant to be read start to finish without having read the other planning documents; it links to them where detail lives. All dollar figures come from the three model scripts in `docs/financials/` (AWS prices fetched from the AWS Price List API on 2026-09-29; salaries are 2026 US-remote estimates) or from reviewer estimates that are labelled as such. See the appendix for every assumption and its source.

Documents referenced: [VISION.md](VISION.md) (product vision, roadmap, pricing principles), [PERSONAS.md](PERSONAS.md) (12 personas), [WORKFLOWS.md](WORKFLOWS.md) (persona-driven workflows and traceability), [DESIGN.md](DESIGN.md) (technical design), [RESEARCH.md](RESEARCH.md) (market research), [STRESS_TEST.md](STRESS_TEST.md) (adversarial critique), [ASSUMPTIONS.md](ASSUMPTIONS.md) (tests with pass bars). Older prototype docs: [ARCHITECTURE.md](ARCHITECTURE.md), [API.md](API.md), [EXAMPLES.md](EXAMPLES.md), [GIT_LFS_SPEC.md](GIT_LFS_SPEC.md).

---

## 1. Where the project stands

### What exists

**The product idea.** GitDAM is a digital asset management product for creative teams (designers, video editors, agencies and their clients) built on a Git-like model: content-addressed file blobs in S3, a commit graph in DynamoDB, check-out locks, "explorations" (branches) with pick-one merges, immutable releases with an approval record, and a Git-compatible export so a customer can always leave. Pricing is meant to be storage-based, with unlimited free guests and bandwidth included. The first paying customer is a 10 to 20 person agency; the first user it must win is "Maya", a designer working in Photoshop and Illustrator.

**Seven planning documents**, written in three rounds (vision and design; personas, workflows and research; stress test and assumptions). They agree on the core model and cite one another carefully. The last round's decisions (Maya first, chunk-level dedup decided by a cost test, vendor statistics quarantined, no sync-client code before a concierge test) were only partly propagated back into the earlier documents. Section 2 lists where.

**A prototype codebase** (Amplify Gen2 backend, Next.js 15 UI, three Lambdas, a Git LFS client). The code audit counts it at about 2,400 lines; the build model counts 2,745 across `amplify/`, `lib/`, `app/` and `components/`. The two counts were taken with different scopes and neither was reconciled; the difference does not affect any conclusion. The code audit found it does not run end to end and cannot as written:

- `lib/api/asset-api.ts` returns `undefined` from `getClient()` on every call after the first, so repository creation, asset listing and upload all throw after the first list.
- Browser uploads use the deprecated `uploadData({ key })` form, which writes under a `public/` prefix that no storage rule covers, so S3 rejects them.
- The three Lambdas are attached to nothing (no API Gateway, no function URL), so the LFS client calls an endpoint that does not exist.
- The lockfile pins a February 2024 Amplify backend beta (`0.13.0-beta.4`) against a 2025 runtime (`aws-amplify 6.15.8`); a webpack stub and `as any` casts paper over the mismatch.
- The storage rules (any signed-in user can read, overwrite or delete every blob) and the data schema (every signed-in user can read every row) are the holes that go live on any deployment. There is no evidence in the repository of a live deployment (no `amplify_outputs.json`, backend pinned to a beta tag), so the verify pass rated them latent-on-deploy rather than exploitable today (section 2E); "live today" is unsupported. The Lambda security problems are latent for a different reason: nothing reaches them.
- `next build` fails on a fresh clone because `app/page.tsx` statically imports the gitignored `amplify_outputs.json`. SETUP.md documents this as expected before a sandbox deploy.

Salvage verdict: roughly 100 to 150 lines are worth keeping (the LFS pointer helpers, the presign core of `lfs-batch`, `auth/`, `backend.ts`, `layout.tsx`). `asset-api.ts`, the storage rules, `next.config.js`, `amplify.yml` and the components need rewriting; `asset-upload` and `asset-download` should be deleted. Phase 0 ("make the prototype true") is 3 to 5 engineer-weeks by the code lens's estimate, not the 2 to 3 weeks DESIGN §14 states; the three verifiers put it at roughly 3 weeks, 2 to 4 weeks and 3 to 4 weeks. The build model's 0.6 to 1.0 EM (about 2.6 to 4.3 weeks) is what the burn in section 3 assumes, and it sits inside the verifier range.

**Four financial model scripts** in `docs/financials/`, committed alongside this document, produced during this review: an infrastructure cost model, a build cost model, a P&L model and a reconciled model that joins the three. They are the source of every number in sections 3 to 6.

### What has been decided

| Decision | Where recorded |
|---|---|
| Content-addressed blobs, per-directory trees, commit graph, refs by conditional update, Git as a bridge (not the store) | VISION "Architectural decision", DESIGN §2 |
| Maya (designers) first; video-specific surface in the second release | VISION Phase 0.5, ASSUMPTIONS decision 1 |
| Locks are the headline collaboration feature; explorations second | VISION Phase 1, RESEARCH §8.2 |
| Storage-based pricing, free unlimited guests, bandwidth included, no feature paywalls | VISION "Pricing principles" |
| Chunk-level dedup is "decided by T2" (the cost model), no longer deferred indefinitely | ASSUMPTIONS decision 4 |
| No sync-client code before the concierge test (T4) has numbers | ASSUMPTIONS decision 2 |
| Vendor statistics may illustrate but never justify a feature | ASSUMPTIONS decision 5 |
| Pricing not published until the cost model exists | VISION Phase 0.5 |

### What is unvalidated

- Zero primary interviews. Every persona frustration is a composite of forum posts and vendor blogs. Ten interviews (T1) and a two-week concierge run (T4) are planned but have not happened.
- No willingness-to-pay data and no baseline for what the target agency pays for its current stack.
- No observed save frequency or working-file sizes; the cost model runs on labelled estimates (2 GB PSD, 20 saves a day).
- No market sizing in any planning document.
- The desktop sync client (the load-bearing bet, STRESS_TEST A1/F1) has not been prototyped.
- Whether Amplify Gen2 can carry the authorization design (T9) has not been spiked, and one specific composition in DESIGN §1 is documented by AWS as unsupported.

### The stress-test verdict, and whether this review moves it

STRESS_TEST.md rates the plan at **5/10 confidence**, with the two largest concerns being unit economics under the auto-snapshot workload (F2) and whether the agency segment's ACV can fund the build (F3).

This review does not move the verdict up. It puts numbers on F2 and F3, and both are worse than the calm-case assumptions in DESIGN §11:

- As designed, the reference agency costs GitDAM $382 to $504 a month in AWS against a $299 price. Gross margin is negative in every scenario. Three product decisions (not price changes) fix it; see section 5.
- Cash to first revenue is $779k (US payroll) or $626k (50% EU/LatAm mix). Cash to breakeven is $3.6M (bull) to $5.3M (base); the bear case never breaks even. See section 6.

The architecture is sound and nothing in it is infeasible. The plan's problem is economic and evidential, not technical.

---

## 2. Findings that change decisions

Six review lenses were run (internal coherence, technical feasibility and effort, market and go-to-market, research validity, code audit, legal and operational risk), then each high-severity finding was independently checked by three verifiers. A finding is listed as confirmed when at least two verifiers upheld it. Verifiers frequently agreed with the facts but lowered the severity to medium because the docs already tracked the risk; those notes are included so the reader can weigh them.

### 2.1 Confirmed high-severity findings

#### A. Design contradictions that must be fixed before Phase 1 code is built on them

**A1. Auto-snapshot squashing rewrites parent ids on content-hashed commits** (coherence, technical, legal lenses; three independent reviewers found it; 3/3 verifiers upheld each time)

DESIGN §2.3 makes a commit's id the SHA-256 of its serialization, which (per §9's Git-SHA synthesis) includes `parentIds`. DESIGN §11.3 then folds auto-snapshots older than 30 days by "rewriting the child's parentIds to skip them." Either the stored id no longer matches its content, or every descendant must be re-hashed, which changes every ref head, release, review base, comment and issue attachment pinned to a commit, and every entry in the Git object map. It contradicts VISION's "history is never rewritten" and undermines the tamper-evidence the approval record relies on in a dispute.

*Change:* do not rewrite the graph. Keep auto-commit rows forever (well under 1 KB each), mark folded ones `pruned: true`, drop their `treeId`, and let GC reclaim only the blobs unique to them. Pruning must obey the same roots as §4.6 (attachments, releases, review bases). The 30-day blob-reclamation economics in the financial models are unchanged by this fix.

**A2. Amplify Gen2 cannot express the authorize-then-Lambda pipeline in DESIGN §1** (technical lens; 3/3 upheld, all three lowered to medium because DESIGN line 76 already says "verify the exact composition" and T9 already carries the CDK fallback)

DESIGN §1 chains `a.handler.custom()` (JS authorize step) with `a.handler.function()` in one pipeline. The Amplify docs state that all handlers in one `.handler()` must be the same type. Three workable shapes exist: all-JS pipelines for simple reads, locks and refs with an in-Lambda authorize module for everything complex; all-Lambda pipelines; or CDK-defined AppSync pipeline resolvers. JS resolvers also cannot do the recursive tree walks in §4, so every tree, diff, merge and history operation is a Lambda regardless. With generated CRUD disabled, what Amplify Data still contributes is table provisioning, the typed client and subscriptions.

*Change:* rewrite §1 to name a supported shape, change T9's pass bar to test that shape (including the three-table role lookup latency), and use the same spike to decide whether Amplify Data earns its place or the backend drops to plain CDK AppSync or an HTTP API.

**A3. S3 cannot enforce a full-object SHA-256 on multipart uploads; the cross-tenant integrity argument fails for exactly the large files it exists for** (technical lens; 2/3 upheld; one refutation on the ground that STRESS_TEST A9/F6 and T3's fallback already record it)

For single PUTs, a presigned URL with `ChecksumSHA256` makes S3 reject mismatched bytes. For multipart uploads (files over 100 MB, i.e. every PSB, render and clip that matters) S3 offers full-object checksums only for the CRC family; SHA-256 is composite-only (per the S3 documentation as known through 2025; the page is blocked here, re-verify). A buggy or malicious client can therefore store arbitrary bytes under any oid, and because blobs are global and deduplicated across tenants, that poisons every org that later uploads the real file. T3 as written cannot pass.

*Change:* §6 must say single-part uploads are S3-enforced and multipart uploads get per-part checksums plus a mandatory server-side stream-and-hash pass before `Blob.verified` flips (delete on mismatch; Lambda up to roughly 20 GB, a container task beyond). Rewrite T3 to test that path, update §12, and add one in-region GET plus compute per large upload to the infra model (cents per TB, not pricing-relevant).

**A4. Global content-addressed dedup is an existence oracle, the preview CDN cookie is not org-scoped, and there is no takedown or erasure path for a shared blob** (legal lens; three findings, each 3/3 upheld; the verifiers who gave a severity rated it medium, and for the takedown finding only one of the three did)

- `batchObjects(upload)` returns "already have it" for any verified oid anywhere on the platform, so anyone with an account can test whether a specific file has ever been uploaded by any tenant. DESIGN §12 accepts this by analogy to GitHub LFS, but GitHub scopes LFS storage per repository network, so the analogy is wrong.
- DESIGN §7 says preview cookies are "scoped to the org" but the cookie is for `previews/*` and previews live at `previews/{oid}/…` with no org component. The practical effect is that revoked members, expired share-link holders and ex-guests keep preview access for any oid they learned.
- When tenant B's copy of a file is the subject of a DMCA notice, a court order or is illegal content, the only primitive is "delete the S3 object", which also deletes tenant A's file. There is no `Blob.status`, no per-tenant reference record, no notice/counter-notice flow, no DMCA agent, no NCMEC reporting path.

*Change:* scope dedup to the org at the API layer (first reference from a new org uploads or passes a proof-of-possession challenge; storage still dedups server-side afterwards, so the cost argument survives), backed by an `OrgBlobRef (orgId, oid, …)` table that GC, quota accounting and takedown all need. Key previews per org or validate a per-org HMAC at the edge; guests get release-scoped access only. Add `Blob.status: ok | blocked | erased` with reason, actor and time; downloads, previews and the Git bridge refuse non-ok oids. Register a DMCA agent and write the notice, counter-notice and repeat-infringer policy before share links (Phase 3) ship. Consider the medium finding on org-scoped storage layout with per-org KMS keys, which resolves all three at once.

**A5. Personal data is baked into hashed, immutable commits; offboarding keeps it forever** (legal lens; 3/3 upheld, rated medium as "a cheap Phase 1 schema decision that gets expensive later")

Commits capture `authorName` and `authorEmail`, the id hashes over them (implied, since the serialization is never enumerated), offboarding leaves them in place, and the Git bridge is designed to emit the real email. No document defines an erasure procedure, so a GDPR Art. 17 request from an ex-employee cannot be honoured as designed. Verifiers dropped the original claim that cross-org delivery or the org export leaks emails to third parties: the import commit is authored as "<source org> via release", and the export goes to the controller itself.

*Change:* hash commits over `authorId` only; resolve display names at read time from a profile that erasure can pseudonymize; synthesize `<userId>@users.noreply.gitdam.app` in the Git bridge, as GitHub does; document erasure and the identity-plane residency exception in the DPA; decide where the global identity plane (Cognito) lives relative to the region-per-org promise.

**A6. GC has a mark/sweep race and no consistency check** (legal lens; 3/3 upheld, rated medium)

Marking snapshots ref heads at job start; a verified blob that becomes newly referenced between mark and sweep (a dedup hit, a restore, a delivery import) is swept, because the 24-hour age rule only protects new rows. There is no fsck, so a partial GC failure is invisible until a download 404s. Verifiers rejected the original claims that the root set is incomplete (§4.6 already covers release commits and delivery imports) and that the trash window is shorter than a PITR window (no document adopts PITR at all, which is itself the gap; see the medium finding on backup).

*Change:* record `lastReferencedAt` on the blob, bumped by any "already have it" hit and by `createCommit`; sweep only candidates untouched since mark start; add a weekly Blob-rows-vs-S3-inventory reconciliation with an alarm; write a backup and restore runbook (none exists).

**A7. Path-level protection of `/exports` has no design support; a protected `main` would block Maya's direct snapshots** (coherence lens; 3/3 upheld, rated medium)

WORKFLOWS 3.1 promises "/exports on the main line is protected" and §13 lists "protected folders" as a second-month feature; the P&L's Studio tier lists "protected folders". DESIGN §2.4 models protection only as a per-ref boolean. If `main` is protected, the core loop (auto-snapshots straight to `main`, restore, no-branch experiments) is refused; if it is not, nothing enforces the `/exports` guarantee. One verifier noted that even path protection does not enforce "nothing reaches the client without approval", since `publishRelease` needs only the editor role.

*Change:* add `protectedPaths: [prefix]` to Project settings, enforce it in the shared ref-advance step used by `createCommit`, restore, `mergeRefs` and the Git bridge push, allow changes under a protected prefix only via a review merge or owner override with reason, and either add a project-level "require approved review for release" gate or reword 3.1 so the guarantee comes from the approval record.

**A8. Release approval and the approval record are promised but not designed** (coherence lens; 3/3 upheld)

WORKFLOWS 3.3, 4.2, 5.2, 7.2 and VISION Phase 3 make the approval-record PDF the buyer's key artifact, and DESIGN §2.8a already assumes it exists. But DESIGN has no `approvals` field on Release, no `approveRelease` operation, no release-approval capability in the §1 table, and no generator (inputs, layout, storage, immutability). Verifiers narrowed the "without an account" part: Dana is an invited guest with a Cognito identity, so her flow only needs the capability and operation; the genuine anonymous case is Lena's link-visibility release (7.2), which contradicts §12's "share links serve previews and the bundle only".

*Change:* decide whether link visitors can approve (captured name and email, weaker non-repudiation) or whether approval requires a guest identity; add `approvals[]` to Release, an `approveRelease` operation, a capability-table row, and a short §2.8b defining the approval-record generator. For the record to stand as evidence, require a verified email and record IP, user agent, time and bundle hash.

#### B. The plan understates effort and cost

**B1. Effort estimates by phase** (technical lens; 2/3 upheld; one refutation on the ground that STRESS_TEST A10 already predicts the 2 to 3x overrun and the build model already re-baselines)

VISION's month counts (Phase 1 "1 to 2 months", Phase 2 "2 to 3 months", Phase 3 "1 to 2 months", Phase 4 "2 to 3 months") were never revised after STRESS_TEST rated them unsupported. The technical lens estimates 60 to 100 engineer-months for Phases 0 to 5 (39 to 63 to a sellable product at end of Phase 3); the build model in `docs/financials/` estimates 45 to 72. The two ranges overlap and both put the desktop client and its Phase 4 native extensions as the largest and least compressible block: 20 to 36 EM by the technical lens, 20.5 to 32 EM by the build model (Phase 2 at 10.5 to 16 plus Phase 4 at 10 to 16). It requires a Rust systems engineer plus native macOS and Windows skills the current TypeScript codebase does not imply. ASSUMPTIONS T11's pass bar (Phase 2 in 3 months for one engineer) is not met by either estimate even Maya-only.

*Change:* replace VISION's parentheticals with the engineer-month ranges and team composition in section 3; treat T11 as a confirmation of the longer figure rather than a test that could pass.

**B2. Phase 0 defects the plan does not list** (technical and code lenses; 3/3 upheld each, verifiers rated the plan amendment at 2 to 4 engineer-days and medium severity)

Beyond DESIGN §14's twelve items: the `getClient()` bug; `asset-upload` fabricates the oid from filename, size and timestamp and should be deleted rather than exposed; `asset-download` presigns any caller-supplied key and must be restricted to oid-derived keys with a membership check or folded into `lfs-batch`; the handlers read the REST-v1 event shape so the planned HTTP API must use payload format 1.0 or the handlers must be retyped; pinning to Amplify backend 1.x rewrites the four `.authorization([...])` blocks; `amplify.yml` runs Node 18 (end-of-life) and the pre-rename `amplify` CLI (now `ampx`); `@aws-sdk/s3-request-presigner` is absent from the lockfile; `lfs-batch` needs an `^[a-f0-9]{64}$` oid check and a size cap; all three handlers log the full event, which after a JWT authorizer is added writes every Authorization header to CloudWatch; CORS is `*`.

The code lens's separate review of the §14 table itself adds two points the list above does not cover: §14's "nothing new is built" is not quite true, since the API Gateway, the JWT authorizer, the `verify` route and the `LFSObject` writes in #3 and #9 are new code (roughly 300 to 400 lines plus CDK); and the removal of `apiKeyAuthorizationMode` belongs in #8 (tighten data authorization), where it is currently absent.

*Change:* add these rows to §14 and re-estimate Phase 0 at 3 to 5 weeks (the code lens; verifiers said roughly 3, 2 to 4 and 3 to 4 weeks) rather than 2 to 3. The build model's 0.6 to 1.0 EM is unchanged by this, since it already spans 2.6 to 4.3 weeks.

**B3. Dependencies resolve to a Feb-2024 backend beta paired with a 2025 runtime** (code lens; 3/3 upheld, rated medium because DESIGN §14 #1-2 already plan the pin)

`aws-amplify: latest` and `@aws-amplify/backend: beta` are held together only by the lockfile; a fresh install without it pulls an untested combination. The webpack stub and every `as any` cast exist because of this mismatch.

*Change:* pin exact versions (backend 1.x, runtime 6.22.x), delete the stub and per-function `package.json` files, add the presigner and S3 client to root devDependencies, move to Node 22 and `ampx`, regenerate the lockfile. Keep DESIGN's Phase 0 budget rather than the "one day" the lens suggested.

**B4. DESIGN §11's cost model contradicts the auto-snapshot workflow** (coherence lens; 2/3 upheld; one refutation on the ground that STRESS_TEST A2/Gap 1 and ASSUMPTIONS decision 4 already retire it)

DESIGN §11 still models "5 GB of new PSD versions a month" and "~$140/yr for 500 GB", and still says chunk dedup waits for "a customer whose bill demands it", a sentence ASSUMPTIONS decision 4 explicitly retired. WORKFLOWS 1.1 (eager upload, auto-snapshot after every quiet period) is a different workload; the infra model shows the true figure is roughly 25x higher. The lens's own dollar estimates ($25 to 45/month "moderate") were rejected by verifiers because they omit sync fan-out egress, the dominant cost in the repo's model.

*Change:* replace §11's rough model with a pointer to `docs/financials/` and its LIGHT/BASE/HEAVY scenarios; replace item 5's sentence with "decided by T2; the reconciled model puts chunk dedup in Phase 2"; take the T1 price ladder from the P&L tiers.

#### C. The market case is unsized and the research base is thinner than the documents read

**C1. Segment sizing** (market lens; 3/3 upheld)

No planning document states how many customers exist. The lens's estimate (Census, ONS and Eurostat size-band tables were blocked; figures combine reachable anchors with labelled estimates, September 2026): roughly 22,000 to 30,000 agencies and studios with 10 to 49 staff across the US, UK and EU, of which perhaps 5,500 to 8,500 are addressable (client work, Adobe-heavy, multi-GB files, English-first sales). At $2 to 5k ACV that is a $15 to 35M serviceable market for the wedge. Freelance designers and illustrators number 300 to 350k but at $19/month are a funnel, not a revenue base. One verifier noted the 5 to 9 employee band (PERSONAS puts Priya at a 5-person post house) would roughly double the count to 10 to 17k firms. The P&L has no saturation term; the base case's breakeven at month 60 needs roughly 600 to 1,200 paying customers, i.e. 10 to 20% of the addressable base.

*Change:* add a one-page Market section to VISION with this table and the sources to re-verify; add a market ceiling to `reconciled_model.py` so breakeven is reported alongside the implied share; decide whether the target is agencies alone or agencies plus brand-side orgs, since that changes the funding plan.

**C2. No channel plan; the adoption route is stated only as scenario inputs** (market lens; 3/3 upheld, rated medium)

The P&L assumes word of mouth, content, Adobe/Figma community, agency referrals and $6 to 10k/month paid marketing, and computes CAC from them, but no planning doc ties any of that to a channel, owner or metric. There is no free org tier. The release page and approval-record PDF carry no "create your own project" prompt, and recipient-to-org conversion is not instrumented. The Adobe UXP panel is a Phase 4 feature with no marketplace-listing decision attached. Verifiers flagged the lens's "Adobe announced UXP for flagship apps this month" as inaccurate (UXP has been in Photoshop since 2020).

*Change:* add a GTM section to VISION listing the channels the P&L already assumes, with owner and metric each; decide a free tier in Phase 1; instrument three events (release page viewed by unique recipient, org created from release, first paid from release); treat the Creative Cloud Marketplace listing as a Phase 2 channel decision because of lead time.

**C3. Competitive response: Adobe and Dropbox already cover more of the wedge than the docs say** (market lens; 3/3 upheld, rated medium/low because VISION, RESEARCH §7 and STRESS_TEST F4 already name the risk)

The genuine gap: PERSONAS Maya ("Dropbox for everything" yet "no way back", first-week win "restoring a ruined file") and RESEARCH §1.3 to 1.4 ignore that Dropbox Business ships file locking, 180-day to 1-year version history and folder Rewind (knowledge as of 2025-26, re-verify). Frame.io is bundled free with 100 GB in Creative Cloud. The defensible ground is cross-tool, cross-format history in one project; immutable releases with an approval record; org-to-org delivery; `git clone` as the exit; and storage-based pricing with free guests.

*Change:* add Dropbox Business, Adobe cloud documents and Frame.io to the RESEARCH §5 competitor table; restate Maya's first-week win around what Dropbox lacks (a named snapshot across many files, history that does not expire, locks that prevent the overwrite, approvals pinned to a version); add a tripwire list to STRESS_TEST F4 ("if Frame.io adds PSD version stacking, then …").

**C4. PERSONAS cites RESEARCH sections for eleven claims that do not exist there, and vendor statistics still do load-bearing work** (research and coherence lenses; 3/3 upheld each, rated medium because ASSUMPTIONS decision 5 already removes decision weight)

Rachel's "$60,000 to $180,000 per year in lost margin", "45 to 75 hours monthly" and "a 25-person team costs roughly 2x a 12-person team" are cited to RESEARCH sections that do not contain them. Jamal's "54% of office professionals waste time searching for files" belongs to the statistic family RESEARCH §6 marks "Don't use." The 67%, 82%, 37% and 83% figures trace correctly to RESEARCH §6 but carry no local caveat. WeTransfer's free-tier expiry is disputed between verifiers (3 vs 7 days); verify or drop.

*Change:* add the quarantine caveat to the PERSONAS preamble, delete or re-source the three phantom figures and the 54%, tag the remaining vendor figures inline, and rewrite Rachel's buying trigger and Theo's feedback rationale as hypotheses for T1.

**C5. No willingness-to-pay data and no baseline for the target stack's current cost** (research lens; 3/3 upheld, rated medium)

RESEARCH prices the version-control competitors but not the tools the agency actually pays for. ASSUMPTIONS T1 sets the price ladder from the T2 COGS model, which can make T1 pass at a price that does not address F3. The P&L's sanity check (list prices as of knowledge cutoff, verify): Dropbox Business Standard 12 seats $180 + Frame.io Pro 3 members $45 + a review tool ~$149 + WeTransfer Pro x2 $24 = about $398/month for the reference agency.

*Change:* add a dated stack-cost table to RESEARCH; set the T1 ladder at $149 / $299 / $499 (fractions of the replaced stack), corrected by interview question 7.

**C6. Dropbox version history may already deliver Maya's first-week win** (research lens; 3/3 upheld; one verifier rated it medium, one medium-high, one gave no rating)

Her persona says "saved over a file, no way back," but Dropbox retains versions and Rewind restores folders. The research contains no evidence on whether designers know about or use it, which is the question that decides whether single-file restore is a differentiator or parity.

*Change:* sharpen interview Q2 to "Did you try Dropbox/Drive/Creative Cloud version history? Did it work?"; count only losses the current tool could not recover toward T1's pass bar; reframe the first-week win as in C3.

**C7. No observed save frequency or file sizes** (research lens; 2/3 upheld; one refutation because the T2 model exists with labelled inputs and T1/T4 already schedule the measurement)

The model runs on 2 GB PSD x 20 saves/day x 6 captured. Re-running the recommended configuration at $299: 85% gross margin for 0.2 GB files, 76% at the modelled inputs, roughly 46% at 2 GB x 96 saves/day or 4 GB x 40. Plausible inputs straddle the 70% pass bar.

*Change:* add a saves/day x file-size sensitivity sweep to `infra_model.py`; pull the measurement earlier than T4 with a one-week mtime/size script at five designers.

#### D. Decisions not propagated through the documents

**D1. "Maya first" is not reflected in VISION Phase 2, WORKFLOWS §13-14 or PERSONAS** (coherence lens; 3/3 upheld; one verifier rated it medium, one medium-high, one gave no rating)

VISION Phase 2 still lists hover-scrub for video, video compare and timecode comments; WORKFLOWS §13 makes Priya on the desktop client a week-one milestone; §14 still tags her 2.5 at Phase 2; PERSONAS says "Maya and Priya (daily use)". No document maps "first release" and "second release" to phase numbers, which matters because the financial models key cohort mix and Phase 2 duration to a Maya-only Phase 2. Verifiers noted that multipart, path stability and locks are explicitly retained by decision 1 and should not move.

*Change:* split VISION Phase 2 into 2a (Maya) and 2b (video surface), retag only §14 row 2.5, add one sentence to PERSONAS, soften §13 item 2, make T11 confirm rather than re-decide.

#### E. Code findings confirmed as the reason the prototype does not run

Covered in section 1 and B2: `getClient()` returns undefined (3/3); uploads land under `public/` and in a layout the Lambdas do not use (3/3, already DESIGN §14 #5); Lambdas have no authorization or input validation (3/3, rated medium because unreachable today and mostly planned); storage rules give every signed-in user read/write/delete on every blob (2/3; one refutation because DESIGN §14 #7 already schedules the fix and there is no evidence of a live deployment). None of these change a decision; they confirm that Phase 0 is a rewrite of most files rather than a patch.

### 2.2 High findings refuted by the verify pass

Listed so the reader knows what was considered and set aside. "Refuted by" counts the verifiers (of three) who refuted the finding; where fewer than three did, the material records only the refutations. The residual column lists what the refuting verifiers themselves said still deserves a one-line edit; none of it changes a decision.

| Finding | Refuted by | Why it was refuted | Residual items the verifiers kept |
|---|---|---|---|
| WORKFLOWS §13 month timeline contradicts VISION phase durations | 3 of 3 | §13's "week one / second month" is the first customer's adoption clock after onboarding, not the build calendar; the pilot (T4) and the first paying customer are different milestones; VISION and WORKFLOWS §14 agree with each other on phases. | The PERSONAS "P2 second-month features" key is loose (Sam's workflows are Phase 5); §13's "third month: Git access" needs Phase 5 within about three months of a post-Phase-3 start; §13 week one puts Priya on the desktop client, which conflicts with Maya-first (see D1); T4 mentions release pages on the Phase 1 backend although releases are Phase 3. |
| Desktop client is 9 to 14 EM; placeholders and Endpoint Security are the hard parts | 2 of 3 | The build model already puts Phase 2 at 10.5 to 16 EM with a named Rust hire at M5 and a second desktop engineer at M19; DESIGN §8 already ships v1 without placeholders and hedges Endpoint Security as "when entitled"; T5 already covers Photoshop, Premiere autosave and After Effects. | VISION's "(2 to 3 months)" and T11's "3 months for one engineer" are stale against the build model; Phase 4's 10 to 16 EM may be tight if placeholders alone cost the 7 to 14 EM the lens estimates on top of the UXP panel; add Illustrator to T5; delete the Endpoint Security clause from §8. |
| Estimated financials (three-year sketch from the market lens: $19/$149/$449 tiers, ~$2.1M cumulative burn, $2.5M seed) | 2 of 3 | The repo's reconciled model contradicts it on every line: Studio COGS is $382 to 411 as designed, not $44; burn is $3.9 to 4.3M over 36 months, not $2.1M; base ARR at M36 is $559k, not $1.4M; a $2.5M seed runs out about a year before modelled breakeven. | `docs/financials/` is uncommitted and not linked from VISION, DESIGN §11, STRESS_TEST F3 or ASSUMPTIONS T2; no funding-path decision (bootstrap vs seed) is recorded in any planning doc. |
| Seven of ten spot-checked citations unreachable | 3 of 3 | A property of the review sandbox, not the evidence; RESEARCH line 5 already discloses excerpt-level sourcing and instructs re-verification; every reachable citation matched exactly; the Unity move is corroborating, not the sole anchor for storage-based pricing. | RESEARCH §5's Diversion pricing wording ("Pro $25 / Studio $35") may be stale against user-count bands; VISION's pricing paragraph repeats the Unity 2026 move without the "re-verify" qualifier RESEARCH carries; no per-source verification date or screenshot. |
| No primary research | 3 of 3 | Accurate, but the docs say so themselves (STRESS_TEST A12, ASSUMPTIONS T1/T8 with pass bars, decision 5) and gate the sync client and pricing on it; the lens's evidence characterization ("weighted toward enterprise DAM buyers") was overstated. | RESEARCH §7's "Confirmed" labels read stronger than the preamble's caveat; add a placeholder RESEARCH §10 for interview results; the quoted "no sync-client code before T4" line is from ASSUMPTIONS decision 2, not VISION. |
| Complaint-only sampling, no satisfied-user base rates | 3 of 3 | Already named in STRESS_TEST gap 2 and converted into T7; the decision it would affect (video first vs second) was already taken the way the finding argues; G2/Capterra aggregates would not answer "who would switch" any better than interviews. | PERSONAS §2 still labels Priya P1 and cites the Frame.io V4 marker bug without a staleness caveat; RESEARCH §7's "Confirmed, strongly" / "frequent" overclaims relative to excerpt-level evidence; RESEARCH records no review counts or dates. |
| Build fails without `amplify_outputs.json` | 3 of 3 | Stock Amplify Gen2 pattern; SETUP.md documents it as expected; `amplify.yml` generates the file before `next build`. | Dead try/catch around the static-string dynamic import in `asset-api.ts`; SETUP.md uses the outdated `npx amplify sandbox` (Gen2 CLI is `ampx`); no AWS-free local build or CI type-check exists. |
| The three Lambdas are unreachable | 2 of 3 | True, and VISION line 184 and DESIGN §14 #3-4 say exactly this and plan the HTTP API; the UI does not depend on them today (it goes through `asset-api.ts` and Amplify Storage directly). | Implementation notes for §14 #3: the handlers use the REST-v1 event shape; `cfnBucket`/`bucketName` in `backend.ts` are unused; whether to expose only `lfs-batch` plus `verify` (the lens) or all three routes (DESIGN) is a scoping choice. |

### 2.3 Medium findings, grouped by area

| Area | Finding | Recommended change |
|---|---|---|
| Design coherence | OpenSearch phase: DESIGN §10 says Phase 5; VISION, WORKFLOWS, RESEARCH say Phase 3 | Change §10 to "Phase 1-2 DynamoDB filtering; Phase 3 OpenSearch" |
| Design coherence | VISION's "target" data model and issue transitions disagree with DESIGN §2.7/§2.8/§5.1 | Replace VISION's model block with a sketch and a pointer to DESIGN §2 |
| Design coherence | Per-region org isolation cannot coexist with global dedup, global GC, zero-copy delivery and one login across orgs | State that dedup, GC, delivery and identity are per region |
| Design coherence | WORKFLOWS §14 phases disagree with VISION for the Activity feed, guest roles, templates, tree sharding, collections; collections have no model | Retag rows; add `Collection` record and operations; define templates |
| Design coherence | "Locks first" is not the order DESIGN §15 builds; Phase 1 still contains the merge engine T6 may remove | Reorder §15; mark step 7 gated on T6 |
| Design coherence | Release-on-snapshot default plus auto-snapshot silently releases Priya's lock; no `requestLock`/`handoverLock` operation | Release only on explicit snapshots; add the operations |
| Design coherence | CloudFront assumed by the Phase 2 preview pipeline but scheduled for Phase 5 | Move CloudFront for previews into Phase 2 |
| Design coherence | "Milestone" means an explicit snapshot in some docs and an issue-tracking deliverable in others | Rename the snapshot concept ("checkpoint") |
| Design coherence | PERSONAS says SSO/SCIM are "not in Phases 0-5"; VISION Phase 5 now includes them | Two-sentence fix |
| Design coherence | ASSUMPTIONS contradicts itself on when validation runs relative to Phase 1 | One sequencing sentence in VISION Phase 0.5 |
| Design coherence | Prototype docs (README, SETUP, ARCHITECTURE, API, EXAMPLES, GIT_LFS_SPEC) contradict the plan on model, storage layout, auth, thresholds, endpoints and oid format; nothing marks them superseded | Banner all four as superseded; rewrite README/SETUP status now; add a bare-hex oid test vector |
| Technical | Merge-base algorithm is not Git's and mis-handles criss-cross histories; `TransactWriteItems` caps at 100 items; `getTree` needs a cursor; GC mark-timestamp rule | Use Git's stale-marking algorithm; idempotent tree puts then a two-item transaction; property tests for canonicalization and diff |
| Technical | Git smart-HTTP bridge is feasible but has four SHA-1 synthesis traps; 3 to 5 EM | Store `mode` on tree entries now; store `.gitattributes` as a real blob; version the synthesis rules; use gitoxide or go-git |
| Technical | Sharp's prebuilt binaries do not cover PSD, RAW or HEIC; previews triggered from S3 PUT render every eager draft | Lambda container image; trigger previews from first commit reference; extract embedded JPEG for RAW |
| Technical | Build cost and infrastructure run-rate estimate (technical lens, from its own 60-100 EM table at $15 to 20k per EM): $105 to 230k for Phases 0-1, $360 to 770k through Phase 2, $570k to $1.2M through Phase 3, $0.9 to 2.0M for the full roadmap, plus 15 to 25% for design, QA and a paid founder; sandbox plus staging plus a bridge task plus MediaConvert testing $300 to 800/month; OpenSearch Serverless floor $350 to 700/month per collection; COGS $20 to 60/month for the design-agency profile and $60 to 200 for a video agency, clearing 70% for design teams and marginal for video | Superseded by sections 3 and 4. People cost: the build model prices by role and month, not by EM ($779k to first revenue, $2.31M to M24 US); the lens's EM-based range overlaps but is not used. COGS: the infra model gives $286 to 346 whole-file for the same agency, roughly 5 to 10x the lens's figure, because the lens omitted sync fan-out egress. Pre-customer AWS: the build model carries $1.5k/month dev/staging. Retained: gate OpenSearch behind a per-org asset-count threshold (the infra model fetches $350.40 for 2 OCU, matching the lens's low end) |
| Market | Proposed tiers from the market lens ($19/$149/$449) | Superseded by the reconciled tiers in section 5 |
| Market | Wedge: Maya and 10-20 person agencies is right only as the paying beachhead inside a two-sided funnel | Free tier and Solo live with Phase 1; ship release pages and the approval record before explorations and reviews |
| Market | Cross-org delivery is a delivery feature; the real loop is guest-led (release page recipients creating free orgs) | Rewrite §10.1's claim; add T13: recipient-to-org conversion of at least 2% within 90 days of the first 100 release pages |
| Research | Statistics used as feature reasons, with source ratings; decision 5 declared but not applied; Jamal uses a "Don't use" statistic; Abstract's death attributed to a mechanism without evidence; guest behaviour unresearched; no market-structure data on agencies with in-house video | Inline source tags; one editing pass; add interview questions on client approval behaviour and download counts |
| Code | Data schema lets every authenticated user read every row; API key mode enabled but unused; beta authorization syntax | Owner-only interim; drop API key mode; rewrite in 1.x syntax |
| Code | `calculateOID` reads the whole file into memory on the main thread and hashes after upload | Stream 8 MB chunks through an incremental SHA-256 in a Web Worker, before upload |
| Code | Webpack stub for `data-schema-types` hides the version conflict; TypeScript and ESLint disabled in build; `next lint` cannot run; versioning is simulated (`list().length + 1`, timestamp "commit sha") | Delete stub after pinning; turn checks on; add vitest; replace with the Phase 1 commit graph |
| Code | DESIGN §14 Phase 0 table, what is wrong or missing (code lens): rows #1-#12 are directionally right and the line references are accurate, but (a) #1 does not say that backend 1.x changes the schema authorization syntax and renames the CLI to `ampx`, so `amplify.yml` changes in #1 and Node 18 needs bumping; (b) the `getClient()` bug is unlisted; (c) #3 exposes `asset-upload`/`asset-download` as they are; (d) #3's JWT authorizer plus full-event logging puts the Authorization header in CloudWatch; (e) #2 says "re-enable checks" but eslint and a test runner are not installed; (f) per-function `package.json` files are inert and the presigner must move to root; (g) `uploadData({ key })` writes under `public/`, subsumed by #5 but worth stating so nobody adds a `public/` rule; (h) `apiKeyAuthorizationMode` removal belongs in #8; (i) Next.js and React patch levels belong in #1; (j) "nothing new is built" is not quite true: the API Gateway, authorizer, `verify` route and `LFSObject` writes in #3/#9 are roughly 300 to 400 lines plus CDK | Add rows for each; restate the estimate as 3 to 5 weeks with the CDK API as new work (verifiers: roughly 3, 2 to 4, 3 to 4 weeks; the build model's 0.6 to 1.0 EM already covers that range) |
| Code | Salvage: roughly 100 to 150 reusable lines of ~2,400 (code audit's count; the build model counts 2,745) | Start Phase 0 as a fresh branch keeping auth/, backend.ts, layout.tsx, pointer helpers and the presign core |
| Legal / ops | Backup, region loss and restore are undefined; blast radius is the whole org | Phase 0: PITR, deletion protection, S3 Versioning, `RemovalPolicy.RETAIN`; Phase 3: AWS Backup vault and CRR in a same-jurisdiction region; state RPO/RTO in the MSA |
| Legal / ops | Share links and guest surfaces need abuse controls, not just entropy (free anonymous 4 GB file host; weak approval evidence; tokens in logs) | Default 30-day expiry; enforced per-org egress cap; malware scan on bundles; verified-email approval; WAF rate rules; strip request logging |
| Legal / ops | Ghostscript (AGPL) is ImageMagick's default PDF/AI/EPS delegate | Route PDF-compatible formats through pdfium only; build the layer without `gs`; licence scanner in CI |
| Legal / ops | Amazon's MIT-0 licence, Amazon code of conduct and AWS security-reporting address inherited from the starter; "Git" trademark policy restricts "Git<Something>" names | Replace LICENSE/CONTRIBUTING, add SECURITY.md; request SFC permission or have a fallback name; clearance search $2 to 5k per jurisdiction (estimate) |
| Legal / ops | Desktop client leans on an Apple entitlement rarely granted; signing keys are key-person risk | Drop Endpoint Security; company-owned developer accounts with two admins; keys in a vault |
| Legal / ops | Customer-managed keys and per-org isolation are incompatible with global dedup | Org-scoped storage layout from Phase 1 with SSE-KMS; optional per-org CMK on a higher tier |
| Legal / ops | GDPR processor obligations not designed in (sub-processors, DPA, retention, logs with `userId` and no retention, AI tagging, CloudFront edge caching as a residency exception) | Privacy policy, ToS, DPA, sub-processor page before the first paying org; 90-day log retention; no-training term for AI tagging |
| Legal / ops | What an agency MSA will ask for vs what a startup on AWS can promise: composite availability about 99.5%, not 99.9 or 99.99; region-loss RTO days without CRR; 72-hour breach notice, not 24 | Draft the MSA to those numbers; ship a status page and security page before the first contract |
| Legal / ops | Compliance and risk budget: roughly $60 to 130k in year one and $40 to 80k a year after, plus $300 to 800/month fixed AWS security overhead (estimates, mid-2026) | Put these into the cost model as a fixed floor; a higher-priced tier carries SOC 2, CMK, CRR and the MSA terms |

### 2.4 Low findings (one line each)

Five broken cross-references from the WORKFLOWS renumbering; VISION open questions 3 to 5 are resolved but still listed open; the `rights` metadata key is claimed reserved in DESIGN §2.5 but is not; release bundles Phase 1 (RESEARCH) vs Phase 3 (VISION) and "Phase 0 exposes" a locking API that arrives in Phase 1; minor over-building (IssueLink `blocks`/`duplicates`, priority, label colours) and under-building (issue templates, org-wide activity, audit CSV, the Adobe panel has no DESIGN section); positioning leads with "Git" rather than the buyer's outcome; git-lfs #3733 is closed "not planned" (2019), so "open since 2024" overstates it; GitHub LFS per-GiB prices no longer appear on the cited page; "top grievance" rankings are unquantified; the Forrester claim is a vendor-commissioned study of enterprise buyers; frontend components are throwaway scaffolding typed as `any`; the code lens's AWS run-cost estimate (list prices as of knowledge, pages blocked) is under $20 to 50/month for the Phase 0 sandbox with one developer, $30 to 60/month at pilot scale (10 users, 500 GB stored, ~200 GB downloaded), and roughly $30 to 40 per 500 GB agency per month in storage plus egress at 100 agencies, all superseded by the infra model in section 4 for per-customer COGS; Next.js and React patch levels lag and Node 18 is end-of-life; several Phase 0 security items (event logging, wildcard CORS, API key mode, MFA commented out, no log retention) are missing from the file-by-file plan.

---

## 3. Effort and team

Source: `docs/financials/build_cost_model.py`, as adjusted by `reconciled_model.py`. Engineer-months (EM) are fully loaded senior-engineer months. Calendar assumes the named team working in parallel. The technical lens's independent estimate (60 to 100 EM total; 39 to 63 to a sellable product) is a wider envelope that overlaps this table and fits inside the plan's paid capacity.

### Phase-by-phase engineer-months

| Phase | Scope | EM low | EM high | Calendar | Team | Key assumption |
|---|---|---|---|---|---|---|
| 0 | Make the prototype run (DESIGN §14 plus the items in finding B2) | 0.6 | 1.0 | M1 | Backend #1 | 0.6-1.0 EM is about 2.6-4.3 weeks. DESIGN says 2-3 weeks; the code lens says 3-5; the verifiers said roughly 3, 2-4 and 3-4. This row is what the burn assumes (see the note below the table) |
| 0.5 | Validate: T1-T5, T9 (overlaps Phase 1) | 0.5 | 1.0 | M2 | Founder runs 10 interviews (~0.5 FTE for 3 weeks); backend does the T3, T5, T9 spikes and the folder-watcher script | T4 concierge run needs Phase 1's `createCommit`, so it lands at M5 |
| 1 | Commit graph: 10 models, authorize, ~20 operations, tree builder, diff, merge, AssetIndex, locks, subscriptions, onboarding UI | 5 | 8 | M2-M5 | Backend #1 (3-5 EM), Frontend #1 (2-3 EM) | Roadmap says 1-2 months; high end assumes T9 fails and the backend drops to CDK mid-phase |
| 2 | Desktop sync client v1 (Maya only, no placeholders, no proxies), preview pipeline, grid, compare, comments, multipart with server-side SHA-256 | 10.5 | 16 | M6-M11 | Rust #1 (5-8 EM), Backend #1 (2.5-4), Frontend #1 (3-4), designer joins M6 | Fails T11's 3-month bar even Maya-only; chunk-level dedup NOT included (+2-3 EM, +1 month if T2 forces it, which section 5 says it does) |
| 3 | Issues, reviews, releases, approval-record PDF, teams and guests, offboarding, usage view, cross-org delivery, notifications, OpenSearch | 9 | 13 | M12-M16 | Backend #1 + #2 (5-7 EM), Frontend #1 (4-6) | Roadmap says 1-2 months; nine bullets, each a feature; OpenSearch alone is 1-2 EM |
| 4 | Adobe UXP panel (4-6 EM), macOS File Provider (3-5), Windows Cloud Files (3-5), Transfer Acceleration | 10 | 16 | M17-M21 | Frontend #1 + Rust #1, Rust/desktop #2 joins M19 | Two new native skill sets; STRESS_TEST F1 warns placeholders "take a year"; After Effects has limited UXP support (verify) and may need a CEP panel as well |
| 5 | LFS conformance, Git smart-HTTP bridge (3-5 EM), CloudFront cookies, AI tags, SSO/SCIM (2-3), org export, rights metadata | 9.5 | 16.5 | M22+ | Backend #2, Backend #1 or Rust #1 | Only ~40% lands inside 24 months; SSO/SCIM gates >50-seat deals |
| **Total** | Phases 0-5 | **45** | **72** | | Peak 6.5 paid FTE | Paid engineering capacity through M24 is ~97 EM incl. founder at ~50%, leaving 25-50 EM for support, bugs, ops and re-estimation |

Reconciling the Phase 0 estimates: four figures appear in this document (DESIGN §14: 2 to 3 weeks; the code lens and finding B2: 3 to 5 weeks; the verifiers' corrections: roughly 3, 2 to 4 and 3 to 4 weeks; the build model: 0.6 to 1.0 EM, about 2.6 to 4.3 weeks). The burn table below uses the build model's figure, but Phase 0's duration does not change the burn directly, because backend #1 is on payroll from M1 whatever Phase 0 takes; a five-week Phase 0 delays the start of Phase 1 by one to two weeks and, if that slip propagates, moves first revenue by the same amount. The verifier range is the one to plan against.

Sellable product (end of Phase 3): 25.6 to 39 EM cumulative; first revenue is taken as M11, when Phase 2 ships to the concierge agency. The STRESS_TEST high case (Phase 2 at 8 months) pushes first revenue to M13 and adds roughly $186k to cash-to-first-revenue. If every phase lands at its high estimate, Phase 4 slips about two months and Phase 5 does not land inside 24 months at all (build model note); the 24-month plan is therefore a mid-estimate plan, not a worst case.

### 24-month team plan

| Quarter | Paid FTE | Hires | Milestone |
|---|---|---|---|
| Q1 (M1-3) | 2.0 | Backend #1 (M1), Frontend #1 (M2) | Phase 0, interviews, Phase 1 start |
| Q2 (M4-6) | 4.0 | Rust #1 (M5), Product designer (M6) | Phase 1 done, concierge run M5, Phase 2 start |
| Q3 (M7-9) | 4.5 | DevRel / founding sales 0.5 FTE (M9) | Sync client build |
| Q4 (M10-12) | 4.5 | (marketing-site contractor M9-10) | Phase 2 ships, first revenue M11 |
| Q5 (M13-15) | 5.5 | Backend #2 (M13) | Phase 3 |
| Q6 (M16-18) | 5.5 | | Phase 3 done, Phase 4 start |
| Q7 (M19-21) | 6.5 | Rust/desktop #2 (M19) | Phase 4 |
| Q8 (M22-24) | 6.5 | | Phase 5 partial |

Founder/CTO present all 24 months at $0 salary (deferred, excluded from burn), coding about 50%.

### Burn (reconciled; US-remote payroll and 50% EU/LatAm mix)

| Period | US avg/month | Mix avg/month | Cumulative (US) |
|---|---|---|---|
| Q1 M1-3 | $40,966 | $33,694 | $122,898 |
| Q2 M4-6 | $66,580 | $53,418 | $322,638 |
| Q3 M7-9 | $87,147 | $69,231 | $584,078 |
| Q4 M10-12 | $95,913 | $76,779 | $871,818 |
| Q5 M13-15 | $108,497 | $85,462 | $1,197,308 |
| Q6 M16-18 | $107,563 | $84,529 | $1,519,998 |
| Q7 M19-21 | $134,313 | $106,404 | $1,922,938 |
| Q8 M22-24 | $130,147 | $102,237 | $2,313,378 |
| M25-36 (held at M24 run-rate) | $130,455 | $102,546 | $3,878,838 |

Opex to first revenue (M11): **$779k US / $626k mix**. Opex to M24: **$2.31M US / $1.84M mix** (the build model's own figure was $2.33M before the reconciliation removed a $1k/month production-AWS step now carried in COGS). Payroll is 91% of the total; non-payroll is $201k over 24 months. Peak payroll M19-24 is $124k/month US, $96k/month mix.

### Assumptions and exclusions

Salaries (estimates, US remote, 2026; load factor 1.3 on base; no equity costed): backend #1 $185k base ($20,042/month loaded); frontend #1 $170k ($18,417); Rust #1 $200k ($21,667); product designer $155k ($16,792); devrel/sales $150k at 0.5 FTE ($8,125); backend #2 $160k ($17,333); Rust #2 $200k ($21,667). EU/LatAm seats at 0.55x US base, applied as a 50/50 blend (payroll factor 0.775).

Non-payroll (list prices as of knowledge, verify): AWS dev/staging $1.5k/month; tooling $400/month fixed plus $150/head/month plus two Adobe CC seats ~$180/month; Apple Developer $99/yr and Windows OV code-signing ~$500/yr; legal $1k formation plus ~$8k templates then $1k/month from M6; accounting $500/month plus $3k/yr; hardware $3.5k per hire plus $6k test rigs; marketing site $12k; conferences $10k year one, $12k year two; insurance $400/month from M12; interview incentives $1k.

Excluded: founder salary (at $120k base would add $312k over 24 months); equity; revenue offset; customer-driven AWS COGS (section 4); sales commission; paid marketing (added back in section 5); recruiting fees (~$35-40k per senior hire at 20% of base); office; severance; fundraising legal ($25-60k for a priced round); SOC 2 ($30-60k, needed for >50-seat deals); EV code-signing if OV proves insufficient.

Sensitivities: every month of slip at the M19-24 team costs ~$131k US / ~$103k mix; hiring Rust #1 two months later saves ~$43k but pushes first revenue to M13; dropping Rust #2 and deferring placeholders past M24 saves ~$130k; adding chunk-level dedup to Phase 2 adds 2-3 EM (~$45-65k) and one month; the EU/LatAm mix saves $478k over 24 months.

---

## 4. Infrastructure cost per customer

Source: `docs/financials/infra_model.py`. Region us-east-1, on-demand, no free tiers, no savings plans, month 6 of year one, 22 working days. Every SKU except Lambda ephemeral storage, EventBridge and the miscellaneous line was fetched from the AWS Price List Bulk API on 2026-09-29; `python3 infra_model.py --verify-prices` re-fetches and reports OK for all 29 checked SKUs. The reference customer is the 12-person agency in WORKFLOWS §13: 8 designers, three concurrent projects.

### The auto-snapshot arithmetic (LIGHT scenario, whole-file dedup)

This is the calculation DESIGN §11 did not do. The workflow in WORKFLOWS 1.1 uploads every save eagerly and takes an auto-snapshot after each quiet period; the 30-day squash in DESIGN §11.3 sets the retention window.

| Quantity | Arithmetic | Result |
|---|---|---|
| Saves uploaded per month | 8 designers x 20 saves/day x 22 days = 3,520 saves x 2 GB | **7,040 GB uploaded** |
| Auto-snapshots retained (30-day window) | 8 x 6 captured/day x 22 days = 1,056 snapshots x 2 GB | **2,112 GB stored at any time** |
| Milestones (kept forever) | 8 x 2 per week x 4.4 weeks = 70 x 2 GB | **141 GB/month permanent** (845 GB by month 6) |
| Transient drafts (uncaptured, GC'd weekly) | 2,464 drafts x 2 GB x 4/30 days residence | **657 GB-month** |
| Live project files | given | 200 GB |
| Previews | ~2% of live | 4 GB |
| **Stored** | 200 + 2,112 + 845 + 657 + 4 | **3,818 GB** |
| Storage cost | 3,818 GB x $0.023 = $87.81 all-Standard; $80.66 with Intelligent-Tiering on the long-lived pool | **$80.66** |
| Sync fan-out egress | each auto-snapshot pulled to one colleague's disk (DESIGN §8 "clean on disk, replace"): 2,112 GB + 50 GB restores = 2,162 GB x $0.09 | **$194.58** |

DESIGN §11's "~$140/yr for ~500 GB" is off by roughly 25x because it modelled a calm workload and omitted the retention window, the transient drafts, and the egress from colleagues' synced folders pulling every auto-snapshot.

### Six-scenario table (variable AWS cost per customer-month)

| Scenario | Dedup | Stored GB | Uploaded GB/mo | Egress GB/mo | Total $/mo | Biggest driver | Second |
|---|---|---|---|---|---|---|---|
| LIGHT (8 designers, 200 GB live) | whole-file | 3,818 | 7,040 | 2,212 | **$285.67** | S3 presigned egress from sync fan-out $194.58 (68%) | S3 storage $80.66 |
| BASE (LIGHT + 1 video editor, 500 GB live) | whole-file | 4,283 | 7,163 | 2,347 | **$309.67** | Egress $201.14 | Storage $88.27; CloudFront $9.52; MediaConvert $4.50 |
| HEAVY (BASE + photographer, 1.5 TB live, +293 GB/mo RAW) | whole-file | 5,340 | 7,456 | 2,418 | **$345.77** | Egress $203.78 | Storage $105.37; Lambda previews $15.56 (15,520 renders: 3,520 PSD + 12,000 RAW, x 20 s x 3 GB); CloudFront $13.09 |
| LIGHT | chunk (60% PSD reduction) | 1,650 | 2,816 | 945 | **$125.20** | Egress $80.53 | Storage $34.24 |
| BASE | chunk | 2,059 | 2,931 | 1,072 | **$147.55** | Egress $86.40 | Storage $40.90 |
| HEAVY | chunk | 3,116 | 3,224 | 1,143 | **$183.65** | Egress $89.03 | Storage $58.00; Lambda previews $15.56 |

Metadata (DynamoDB, AppSync, SQS, S3 requests, Lambda API) is under $1.10/month per customer in every scenario, confirming DESIGN §11's "rounding error" claim for that part.

What halves each scenario:

- **LIGHT and BASE:** do not push auto-snapshots to other members' disks; pull on demand (on open, on milestone). Sensitivity on fan-out: 0 gives $96, 0.5 gives $191, 1.0 gives $286, 2.7 (everyone syncing the whole folder) gives $609. At fan-out 0 the driver becomes the 30-day window ($49 of $96), halved again by chunk dedup, a 14-day squash, or a per-file daily cap on captured snapshots.
- **HEAVY:** the same, plus extract the embedded JPEG from RAW files (~1 s) instead of demosaicing (20 s), cutting RAW preview compute by ~95%; and trigger previews from the first commit reference rather than S3 PUT so the 2,464 uncaptured drafts a month are never rendered (70% of PSD preview compute; in the reconciled model this takes LIGHT under configuration D from $50 to $47 a month, small but free).

Intelligent-Tiering: saves only $7 to 17/month per customer, because the 30-day window never leaves the Frequent tier before GC. It is a trap for eager drafts: objects deleted before 30 days are billed for the full 30 days, adding $113/month per LIGHT customer if drafts are PUT straight into it. Recommendation for DESIGN §11.1: PUT into Standard, transition by lifecycle after 30 days.

### Platform fixed cost

**$451.03/month** with OpenSearch Serverless on: OpenSearch 2 OCU x 730 h x $0.24 = $350.40 (plus $0.24 for a 10 GB index); NAT Gateway $35.10; Fargate Git bridge (0.5 vCPU / 1 GB, 24x7) $18.02; ALB $22.27; miscellaneous (Route 53, CloudWatch, Secrets Manager, Amplify hosting) $25 estimate. Variants: 1 OCU dev/test $275.83; 4 OCU production redundancy $801.43; before OpenSearch ships (Phase 1-2, DynamoDB plus client-side filtering per DESIGN §10) **$100.39**. OpenSearch is 78% of fixed cost; the minimum-OCU rule is marked "verify". Keep DynamoDB filtering until a customer exceeds roughly 100k assets.

### Unit prices used

| Item | Price | Source |
|---|---|---|
| S3 Standard storage (first 50 TB) | $0.023/GB-month | Price List API, 2026-09-29 |
| S3 Intelligent-Tiering Frequent / Infrequent / Archive-Instant | $0.023 / $0.0125 / $0.004 per GB-month; monitoring $0.0025 per 1,000 objects; early delete billed as 30 d | Price List API |
| S3 PUT/COPY/POST/LIST; GET/HEAD | $0.005 / $0.0004 per 1,000 | Price List API |
| S3 data transfer out (first 10 TB) | $0.09/GB | Price List API |
| S3 to CloudFront origin fetch | $0.00/GB | Price List API |
| CloudFront out, US (first 10 TB); HTTPS request | $0.085/GB; $0.01 per 10,000 | Price List API |
| Lambda x86 compute; request | $0.0000166667 per GB-s; $0.20 per 1M | Price List API |
| Lambda ephemeral storage above 512 MB | $0.0000000309 per GB-s | list price as of knowledge, verify |
| DynamoDB on-demand write / read; storage | $0.625 / $0.125 per million; $0.25/GB-month beyond 25 GB | Price List API |
| AppSync query; real-time update; connection minute | $4 / $2 / $0.08 per million | Price List API |
| MediaConvert 720p H.264 Basic | $0.015 per output minute (newer Normalized Transcoding Minute SKU lists $0.0075/min; multiplier not modelled) | Price List API |
| OpenSearch Serverless OCU-hour; storage | $0.24 ($175.20 per OCU-month); $0.024/GB-month | Price List API; minimum OCU count marked verify |
| Fargate vCPU-hour / GB-hour | $0.04048 / $0.004445 | Price List API |
| ALB hour / LCU-hour | $0.0225 / $0.008 | Price List API |
| NAT Gateway hour / GB | $0.045 / $0.045 | Price List API |
| Cognito Essentials MAU | $0.015 | Price List API |
| SQS request; EventBridge event | $0.40 per million; $1.00 per million | Price List API; EventBridge as of knowledge, verify |
| Miscellaneous platform | $25/month | estimate |

---

## 5. Pricing and revenue

Source: `docs/financials/pnl_model.py` and `reconciled_model.py`.

### Which tiers, and why

Two tier sets were proposed during the review:

| | Market lens | P&L model (adopted here) |
|---|---|---|
| Free | $0, 10 GB, 3 members | not modelled |
| Solo | $19/mo, 250 GB | $19/mo, 250 GB, 750 GB egress |
| Studio / mid | $149/mo, 2 TB, 1x stored egress | $299/mo, 2 TB, 6 TB egress |
| Top | Agency $449/mo, 8 TB | Studio Plus $899/mo, 8 TB, 24 TB egress |
| Overage | $0.10 / $0.08 / $0.06 per GB-month by tier | $0.10/GB-month storage, $0.08/GB egress, all tiers |
| Retention | 30 d / 1 yr / 2 yr / configurable | 30 / 90 / 365 days |

**The P&L tiers are adopted, with two amendments.** Reasons: (1) The market lens's $149 rested on a Studio COGS of about $44 and 70% margin. The reconciled model, which re-runs the infra engine at cohort age 12 and adds the 90-day Studio retention adder, puts Studio COGS at $382 to 411 as designed and $50 to 76 under the recommended configuration (`infra_model.py`'s own headline for the same LIGHT and BASE workloads at month 6, without the retention adder, is $285.67 to $309.67 whole-file and $125.20 to $147.55 chunk, as the section 4 table states); at $149 even the recommended configuration yields roughly 49 to 66% gross margin before platform fixed cost, failing the T2 bar. (2) $299 is 75% of what the reference agency pays today for Dropbox plus Frame.io plus a review tool plus WeTransfer (~$398/month, list prices as of knowledge); it is a plausible "one bill instead of three" price. The P&L's sanity check cuts both ways, though: if the agency keeps Dropbox for its non-project files it pays $479 a month, $81 more than today; only if it drops Dropbox for project work does it pay $299, $99 less. The pitch has to be "replace", not "add". (3) The reconciled model, which produces every 36-month number below, runs on these tiers. Amendments from the reconciliation: auto-snapshot retention is **30 days on every tier** (the 90/365-day differentiator costs $39 to $218 per customer-month at chunk dedup, $97 to $546 whole-file, and is the whole difference between configuration C's 60.0 to 62.6% and configuration D's 73.5 to 79.4% blended gross margin at M36; differentiate by storage, support, and if wanted, by milestone or archived-exploration retention, which costs cents); and an **included-editor guard** (for example Studio up to 20 editors, then $10 per editor per month), because residual COGS scales with editors x saves (about $5 to 6 per designer-month at chunk dedup), not with live GB, so a 30-designer agency at 200 GB would sit near 40% margin. The market lens's free tier is a channel decision (finding C2) rather than a pricing one; it is not modelled and should be decided in Phase 1. The 3x-storage egress allowance never bills in any cohort, so lowering it to 1x (the market lens) is unnecessary.

Billable unit: live GB (main line, releases, pinned explorations). Version history inside the retention window is included. That is the only reading under which the tiers benefit the customer, and it means auto-snapshot volume is GitDAM's cost risk, not the customer's bill.

Suggested T1 price ladder: $149 / $299 / $499.

What the reconciliation changed in the tiers, and why:

- Prices and included storage (Solo $19 / 250 GB, Studio $299 / 2 TB, Plus $899 / 8 TB) are unchanged from the P&L model; they are anchored to Unity VCS $0.14/GB, Diversion $25/user and Anchorpoint EUR 20/user (RESEARCH §5, verify).
- Auto-snapshot retention changed from 30 / 90 / 365 days to 30 days on every tier, because the infra model costs only a 30-day window (DESIGN §11.3) and the reconciliation priced the longer windows at window GB x (retention/30 - 1) x $0.023: +$39 (Studio) and +$218 (Plus) per customer-month at chunk dedup, +$97 and +$546 whole-file.
- An included-editor guard was added (Studio up to 20 editors, then $10 per editor per month), because residual COGS under configuration D scales with editors x saves, about $5 to 6 per designer-month at chunk dedup, not with live GB.
- The 3x-storage egress allowance was left as proposed, because the infra egress figure (100 to 293 GB/month under pull-on-demand) never exceeds it in any cohort; the market lens's 1x allowance is unnecessary.
- The Solo COGS placeholder ($60, which made Solo negative-margin) was replaced by a LIGHT/8 workload run (1 designer, 1 user, 3 guests, fan-out 0): $13 whole-file, $8 chunk at age 12, so Solo at $19 is 30 to 60% gross margin.
- The Plus COGS placeholder ($140) was replaced by the HEAVY profile at 3 TB live plus 150 GB/month with team scale 1.0: $944 as designed, $161 under D; at team scale 2x and 3x, $243 and $327 under D.
- Plus's included storage is flagged for reconsideration (6 TB rather than 8 TB, or the editor guard), because a 45-person studio at 3x the reference team falls to 64% margin ex-fixed.
- The free tier stays unmodelled and becomes a Phase 1 channel decision (finding C2).

### COGS per customer-month by configuration (age 12; platform fixed added in total per month)

The answer depends on three product decisions, so four configurations are run:

- **A. As designed at Phase 2 ship**: whole-file dedup, sync fan-out 1.0, tier retention 30/90/365 days
- **B**: A + chunk-level dedup in Phase 2
- **C**: B + pull-on-demand sync (fan-out 0)
- **D (recommended)**: C + 30-day auto-snapshot window on every tier

| Tier / workload | Price | P&L placeholder | A | B | C | D | Egress % of price (A to D) |
|---|---|---|---|---|---|---|---|
| Solo (LIGHT/8, 1 person, 80 GB) | $19 | $60 | $13 | $8 | $8 | $8 | 6% |
| Studio / LIGHT (200 GB) | $299 | $90 | $382 | $164 | $88 | $50 | 66% to 3% |
| Studio / BASE (500 GB) | $299 | $90 | $411 | $191 | $115 | $76 | 70% to 6% |
| Studio / HEAVY (1.5 TB, +318 GB/mo; pays $631 with overage) | $299+ | $90 | $504 | $285 | $208 | $169 | 34% to 4% |
| Plus (HEAVY profile at 3 TB) | $899 | $140 | $944 | $455 | $379 | $161 | 24% to 3% |

COGS grows with cohort age because milestone history is kept forever: Studio/LIGHT under D is $44 at age 0, $50 at 12, $57 at 36. The $60 Solo placeholder was an artefact; Solo at $19 is fine.

### Gross margin at M36 and the T2 check

| Config | BEAR | BASE | BULL | T2 (>=70% at Studio age 12, fixed cost over 20 customers) |
|---|---|---|---|---|
| P&L placeholders | 63.3% | 69.1% | 72.0% | n/a |
| A (as designed) | -17.6% | -14.0% | -12.5% | FAIL (-45% to +16%: LIGHT -35%, BASE -45%, HEAVY +16%); T12 FAIL (egress 34-70% of price) |
| B | 41.8% | 45.4% | 46.6% | FAIL (28-51%) |
| C | 60.0% | 62.5% | 62.6% | FAIL (54-63%); T12 PASS |
| D | 73.5% | 78.0% | 79.4% | LIGHT 76% PASS, HEAVY 70%, BASE 67% (72% at fixed over 50); T12 PASS |

On the configuration A range: the reconciled model's own summary states it as -35% to +16%; the -45% BASE figure comes from a verifier's correction and is arithmetically consistent with $411 COGS plus $22.55 of fixed cost over 20 customers against $299. Both are shown.

**The same result as a required price.** The infra model can also be read backwards: to clear the T2 bar (70% gross margin, fixed cost over 20 customers) with the design as written, the Studio price would have to be **$1,027 to $1,228 a month** (whole-file dedup; about $5.14 per live GB for LIGHT), or **$493 to $687** with chunk-level dedup alone. With both pull-on-demand sync and chunk dedup, LIGHT's variable cost falls to about $49 a month and the bar is met at roughly **$240**. That is the most direct statement of why $299 is viable only under configuration D, and only just.

### Reconciled 36-month scenarios (configuration D, US payroll)

Scenario inputs: BEAR 1.5 new customers/month at M10 growing 4%/month, 3.0% monthly churn, mix Solo 50 / Studio 45 / Plus 5, paid marketing $6k/month; BASE 3/month growing 7%, 2.0% churn, 40/50/10, $8k; BULL 5/month growing 9%, 1.5% churn, 35/50/15, $10k. First revenue M11. One support hire per 150 customers. Burn is the build model month by month through M24, then held at the M24 run-rate.

| | BEAR | BASE | BULL |
|---|---|---|---|
| Customers M12 / M24 / M36 | 3 / 23 / 50 | 6 / 61 / 174 | 10 / 121 / 415 |
| ARR M12 / M24 / M36 | $6.8k / $55.6k / $125k | $18.2k / $189k / $559k | $36.2k / $438k / $1.55M |
| Gross margin M36 | 73.5% | 78.0% | 79.4% |
| 36-month burn (incl. marketing and support) | $4.03M | $4.11M | $4.30M |
| Net cash flow, M36 | -$130k/mo | -$115k/mo | -$61k/mo |
| Breakeven (growth continues / rate frozen at M36) | never / never | M60 / >M96 | M43 / M45 |
| Cumulative cash need to M36 | $3.95M | $3.75M | $3.37M |
| Cumulative cash need to breakeven | n/a | $5.29M | $3.57M |
| With 50% EU/LatAm mix: breakeven; cash to M36; cash to breakeven | never; $3.13M; n/a | M55 / M81; $2.93M; $3.78M | M40 / M40; $2.52M; $2.56M |

For comparison, as designed (configuration A) no scenario ever breaks even and cash need to M36 is $4.06M / $4.19M / $4.46M.

### Unit economics (configuration D, M36)

| Scenario | ARPA/mo | GM | CAC | Payback | LTV | LTV/CAC | Churn/mo |
|---|---|---|---|---|---|---|---|
| BEAR | $210 | 73.5% | $8,237 | 53 months | $5,148 | 0.62 | 3.0% |
| BASE | $268 | 78.0% | $2,910 | 14 months | $10,444 | 3.59 | 2.0% |
| BULL | $310 | 79.4% | $1,396 | 6 months | $16,419 | 11.76 | 1.5% |

CAC counts all sales and marketing lines (devrel/founding sales 0.5 FTE from M9, marketing site, conferences, paid marketing, $5k/month founder time), which is why it is higher than the P&L's own $4,205 / $1,571 / $789. ARPA sits between the Solo and Studio list prices because Solo is 35 to 50% of logos but 3 to 5% of revenue; Studio customers pay about $330/month once storage overage is included. Expansion from overage is 6 to 11% of MRR at M36, almost all from HEAVY-workload Studio customers whose RAW ingest crosses the 2 TB allowance and right-sizes them to Plus around month 22 (the P&L model's calendar figure; the reconciled model, which counts cohort age, puts it at age 20; the difference is the one-month first-revenue shift plus rounding).

### What the reconciliation moved: the P&L's own numbers before and after

The P&L model's placeholder run (Solo/Studio/Plus COGS $60/$90/$140; burn $95k/$140k/$180k per month by year, $4.98M over 36 months; first revenue M10) is shown against the reconciled run (per-cohort COGS from the infra engine, configuration D; build-model burn month by month, then the M24 run-rate plus support and marketing; first revenue M11). Customer counts and ARR fall 5 to 10% because first revenue moved one month right; cash need falls despite lower revenue because the $180k/month year-three placeholder is replaced by the build model's ~$130k run-rate; CAC roughly doubles because every sales and marketing line is now counted.

| | BEAR: P&L then reconciled | BASE: P&L then reconciled | BULL: P&L then reconciled |
|---|---|---|---|
| Customers M12 / M24 / M36 | 4.5 / 25 / 52.4 then 3 / 23 / 50 | 9.5 / 67.3 / 187.8 then 6 / 61 / 174 | 16.2 / 135.5 / 456.2 then 10 / 121 / 415 |
| ARR M12 / M24 / M36 | $10.3k / $60.6k / $133k then $6.8k / $55.6k / $125k | $28.1k / $210k / $606k then $18.2k / $189k / $559k | $56.5k / $494k / $1.70M then $36.2k / $438k / $1.55M |
| Gross margin M36 | 63.3% then 73.5% (D) or -17.6% (A) | 69.1% then 78.0% (D) or -14.0% (A) | 72.0% then 79.4% (D) or -12.5% (A) |
| 36-month burn | $4.98M then $4.03M | $4.98M then $4.11M | $4.98M then $4.30M |
| Cumulative cash need to M36 | $4.90M then $3.95M | $4.62M then $3.75M | $4.04M then $3.37M |
| Breakeven (growth continues / rate frozen at M36) | never / never then never / never | M59 / never then M60 / >M96 | M43 / M45 then M43 / M45 |
| Cumulative cash need to breakeven | n/a | $6.57M then $5.29M | $4.26M then $3.57M |
| ARPA M36 | $211 then $210 | $269 then $268 | $311 then $310 |
| CAC | $4,205 then $8,237 | $1,571 then $2,910 | $789 then $1,396 |
| LTV/CAC | 1.06 then 0.62 | 5.9 then 3.59 | 18.9 then 11.76 |

The P&L's headline conclusions survive the reconciliation unchanged: STRESS_TEST F3 is confirmed (no scenario breaks even inside 36 months; BEAR never does), expansion revenue is real but small, and egress overage never bills. What the reconciliation added is the configuration-A result, which the placeholder COGS hid: as designed, gross margin is negative and nothing breaks even in any scenario.

### The twenty discrepancies between the three models, and how each was resolved

| # | Item | Infra or build model | P&L model | Resolution |
|---|---|---|---|---|
| 1 | Studio COGS per customer-month | Infra: LIGHT $286 / BASE $310 / HEAVY $346 whole-file at fan-out 1.0, month 6 (chunk $125 / $148 / $184) | $90 placeholder; its own bottom-up $128 to 169 tiered, $206 to 508 Standard | Infra engine called per cohort workload and age; at age 12 with the proposed 90-day Studio retention the as-designed figure is $382 / $411 / $504, falling to $50 / $76 / $169 under D |
| 2 | Solo COGS | Not modelled; task maps Solo to LIGHT/8 | $60 placeholder (made Solo negative-margin); own estimate $5 to 12 | LIGHT re-run with 1 designer, 1 user, 3 guests, per-team GB / 8, fan-out 0: $13 whole-file, $8 chunk at age 12; the $60 was an artefact |
| 3 | Plus COGS | Not modelled; task maps Plus to HEAVY ($346 / $184) | $140 placeholder; sensitivity used $200 / $420 / $900 | HEAVY profile at Plus live GB (3 TB + 150/month), team scale 1.0: $944 A, $455 B, $379 C, $161 D at age 12; team scale 2x / 3x gives $243 / $327 under D |
| 4 | Burn | Build: $31k M1 rising to $133k M24; $779k to first revenue, $2.33M to M24 US ($626k / $1.85M mix) | $95k / $140k / $180k placeholders by year, $4.98M over 36 months | Build series used month by month M1-24; M25-36 held at the M24 run-rate plus support hires and paid marketing; 36-month burn $4.03 to 4.30M by scenario |
| 5 | First revenue month | Build: M11 (Phase 2 ships) | M10 | M11; cohorts start one month later, so customer counts are 5 to 10% below the P&L's |
| 6 | Paid marketing | Build: explicitly excluded | $6k / $8k / $10k per month "inside the burn placeholder" | Added to cash burn from M11 per scenario |
| 7 | Production AWS baseline vs platform fixed | Build: AWS opex steps $1.5k to $2.5k at M12; infra: platform fixed $100 (pre-OpenSearch) / $451 per month | No platform fixed line; $8/customer "other infra" inside its bottom-up COGS | The $1k/month step removed from opex; platform fixed carried in COGS as $100/month M11-16 and $451/month from M17, amortised over that month's customers |
| 8 | OpenSearch Serverless cost | Build: "~$700/month when it turns on in Phase 3, verify"; infra: $350/month for 2 OCU (fetched price), $701 for 4-OCU redundancy | Not modelled | $350 (2 OCU) from M17; 4-OCU production redundancy is a sensitivity (+$7 per customer-month at 50 customers) |
| 9 | Snapshot arithmetic | Infra: 22 working days, 6 captured snapshots per designer per day, 2 milestones per week | 21 days, 12 captured per day (60% of 20 saves), 1 milestone per day kept forever | Infra values, since they drive COGS; the P&L's snapshot block is superseded |
| 10 | Egress volume and price | Infra: 2,112 to 2,418 GB/month presigned S3 at $0.09 (sync fan-out of every auto-snapshot) plus 50 to 154 GB CloudFront | 0.4 to 0.5x live GB via CloudFront at $0.085 ($11 to 34/month) | Infra values; the gap is DESIGN §8 "clean on disk, replace". Configurations C and D assume pull-on-demand, which takes egress to 100 to 293 GB/month (3 to 6% of price) |
| 11 | Tier retention (auto-snapshot history) | Infra: costs a 30-day window only (DESIGN §11.3 squash) | Tiers promise 30 / 90 / 365 days as the differentiator | Costed as window GB x (retention/30 - 1) x $0.023: +$97 Studio / +$546 Plus whole-file, +$39 / +$218 chunk. Configuration D sets 30 days on every tier; this is the change that lifts margin from 60 to 63% to 73 to 79% |
| 12 | Milestone history and tiering split | Infra: 6 months of history, fixed 50/30/20 Frequent/Infrequent/Archive split | Milestones kept forever, 30/40/30 split | History grows with cohort age; split is age-aware (newest month Frequent, next two Infrequent, older Archive-Instant) |
| 13 | HEAVY live growth | Infra: 293 GB/month RAW (12,000 x 25 MB in binary GB) | 325 GB/month | 318 GB/month (293 RAW + 20 renders + 5 design); HEAVY right-sizes to Plus around age 20 |
| 14 | HEAVY starting live GB | Infra: 1,536 GB (1.5 TiB) | 1,500 GB | 1,500 (the task value); the tie-out uses 1,536 to reproduce the infra headline exactly |
| 15 | Chunk-level dedup timing and cost | Build: not in Phase 2; +2 to 3 EM and +1 month if T2 forces it | Sensitivity only | Configurations B to D assume it ships in Phase 2 (T2 fails without it); the ~$45 to 65k sits inside the build model's 25 to 50 EM slack and is not added to burn |
| 16 | Founder/CTO cost | Build: $0 salary, deferred, excluded | $5k/month founder growth time in the CAC numerator | Both kept: $0 in cash burn, $5k/month in CAC only |
| 17 | CAC definition | Build: devrel/founding sales 0.5 FTE ($8,125/month from M9), marketing site $12k, conferences $10k / $12k are opex lines | CAC = paid marketing plus founder time only ($4,205 / $1,571 / $789) | All S&M lines counted: CAC $8,237 / $2,910 / $1,396; BEAR LTV/CAC falls to 0.62 |
| 18 | Support / customer-success headcount | Build: none (devrel handles early support) | None | One support hire ($100k base, loaded x1.3) per 150 customers added; only BASE at M36 and BULL from M30 trigger it |
| 19 | Gross margin definition | Infra: the 70% test uses variable plus fixed/20 | Variable placeholder only | Scenario gross margin includes platform fixed in total; the T2 table shows both fixed/20 and fixed/50 |
| 20 | Free tiers | Infra: ignored (CloudFront 1 TB, S3 100 GB egress, Cognito 10k MAU) | Ignored | Ignored; would remove roughly $5 to 15 per customer-month for the first ~10 customers |

### Reconciliation verdict: do the pricing principles survive?

**Not as designed.** Under configuration A the reference agency costs $382 to 504 a month against a $299 price, gross margin is negative in every scenario, nothing ever breaks even, and both pass bars fail. The storage-based, bandwidth-included principle does survive, but only with three product decisions, none of which is a price change:

1. Chunk-level dedup in Phase 2 (ASSUMPTIONS decision 4 is triggered; on its own it reaches only 42 to 47% margin; +2 to 3 EM, +1 month in Phase 2).
2. The sync client must not push auto-snapshots to other members' disks. DESIGN §8's "clean on disk, replace" becomes pull on open or on milestone. This removes $80 to 195 per customer-month of presigned-S3 egress, takes egress to 3 to 6% of price, and makes "bandwidth included" cheap to keep.
3. Auto-snapshot retention stays at 30 days on every tier.

With all three, blended margin is 73.5 / 78.0 / 79.4% at M36: at the T2 bar, not comfortably above it. A per-seat price is not required, but an included-editor count per tier is the minimum guard, and if T4 measures more than about 6 captured snapshots per designer per day, a per-file daily cap on captured auto-snapshots. Plus is safe at 1 to 2x the reference team but a 45-person studio at 3x falls to 64%; consider 6 TB rather than 8 TB included, or the same editor guard.

Pricing cannot fix the funding problem: even under D only BULL breaks even inside four years, BASE needs $5.3M ($3.8M with the EU/LatAm mix) to reach breakeven at M60, and BEAR never does. STRESS_TEST F3 stands regardless of the pricing principle.

---

## 6. Financial summary

| | Amount (US payroll) | Amount (50% EU/LatAm mix) |
|---|---|---|
| Cash to first revenue (M11, Phase 2 ships) | $779k | $626k |
| Same, STRESS_TEST high case (Phase 2 at 8 months, first revenue M13) | ~$965k | ~$776k |
| Cash to M24 | $2.31M | $1.84M |
| Cash need to M36, config D, BEAR / BASE / BULL | $3.95M / $3.75M / $3.37M | $3.13M / $2.93M / $2.52M |
| Cash need to breakeven, config D, BEAR / BASE / BULL | never / $5.29M (M60) / $3.57M (M43) | never / $3.78M (M55) / $2.56M (M40) |
| Cash need to M36, config A (as designed) | $4.06M / $4.19M / $4.46M | not run |

(The high-case row adds the STRESS_TEST high-case sensitivity (Phase 2 at 8 months, first revenue M13) to the base figures. The two sources differ slightly on it: the reconciled model states "+~$186k to first revenue" and gives no mix figure; the build model states "~$190k US / ~$150k mix". The US cell uses the reconciled model's $186k, the mix cell uses the build model's $150k, and the $4k gap on the US figure is within the rounding of both.)

What this implies, directly:

- **Not bootstrappable.** $779k must be spent before the first dollar of revenue, and the first agencies at $299/month cannot offset a $96k/month burn. The plan excludes founder salary; adding it makes this worse.
- **Not a pre-seed.** A pre-seed of a few hundred thousand dollars covers Phase 0, the interviews, the concierge run and Phase 1 (the plan's cumulative burn is $123k at M3 and $323k at M6; the M6 figure already includes the Rust hire from M5, the designer from M6 and the $6k test rigs, so Phase 0 plus 0.5 plus Phase 1 alone is somewhat less), but not the desktop client that produces first revenue ($779k cumulative at M11).
- **Seed-sized, and then some.** Reaching breakeven needs $3.6M (bull) to $5.3M (base) with US payroll, or $2.6M to $3.8M with the mixed team, against a serviceable market the market lens estimates at $15 to 35M and a base-case ARR of $559k at month 36. That is a seed round followed by a second seed or a Series A, for a company whose base case has 174 customers at three years. A funder will ask why the segment is worth that; the current documents cannot answer, because there is no market sizing, no interviews and no willingness-to-pay data.
- **The burn, not the price, is the lever.** Cumulative cash need is dominated by payroll (91% of burn). A 30% lower burn moves BASE breakeven far more than a 30% higher price. The mixed team saves $478k over 24 months and pulls BASE breakeven from M60 to M55; dropping the second Rust hire and deferring placeholders saves $130k more.
- **The cheapest de-risking costs under $10k of non-payroll and about 1.5 EM.** Ten interviews, the observed save-frequency measurement and the concierge run decide whether the $779k is spent on a sync client at all.

---

## 7. Recommendation

**Go with changes, gated.** Proceed with Phase 0, Phase 0.5 and the design corrections, which settle the questions that decide everything after. Their cost is small: Phase 0 is $15 to 36k of labour (code lens); T1 to T4 cost under $10k of non-payroll and about 1.5 EM; the plan's Q1 burn of $123k (M1 to M3) covers Phase 0, the interviews and the start of Phase 1. The $323k cumulative at M6 is not the cost of this gated work: it already includes Phase 1 (M2 to M5), the Rust engineer from M5 (about $43k), the product designer from M6 ($16.8k), the $6k Mac and Windows test rigs and two laptops. Do not hire the Rust engineer (M5 in the plan) or start Phase 2 (the $779k-to-first-revenue commitment) until the gates below pass and a seed round sized to the base case (the reconciled cash need to breakeven is $5.29M with US payroll, or $3.78M with the 50% EU/LatAm mix; section 6) is realistically raisable. If the gates fail or the round is not available, the honest alternatives are a web-first product (Phases 0 to 1 plus release pages and the approval record, no desktop client) or stopping.

The verdict is not "go" because the segment is small, the cash need is large, the evidence is secondary, and the design as written loses money on every customer. It is not "pivot" or "stop" because the fixes are known, cheap to test, and the architecture is sound.

The changes that matter, in order:

1. **Adopt configuration D before any sync-client code is written** (section 5; findings B4, C7). Chunk-level dedup in Phase 2, pull-on-demand sync (no fan-out of auto-snapshots to colleagues' disks), and 30-day retention on every tier. Without these, gross margin is -12 to -18% and nothing ever breaks even; with them it is 73 to 79%. Update DESIGN §8, §11 and the P&L tiers, and add the included-editor guard.

2. **Decide the funding path before Phase 2, from the numbers in section 6** (finding C1). $779k to first revenue and $3.6 to 5.3M to breakeven on a $15 to 35M serviceable market is a seed-round bet. Add the market section to VISION, add a saturation term to the reconciled model, and choose between the US and mixed team. If the round is not raisable, cut to the web-first scope now rather than at M9.

3. **Run T1 to T4 now, before the Rust hire at M5** (findings C4, C5, C6, C7). Ten interviews with the stack-cost price ladder ($149 / $299 / $499), the Dropbox-history question, a one-week save-frequency script at five designers, and the two-week concierge run. Count only unrecoverable losses toward T1. Delete the phantom citations and quarantine the vendor statistics so the interview guide is not built on quotes nobody can locate.

4. **Fix the eight design findings before Phase 1 code is built on them** (findings A1 to A8). In order of cost if left: the squash rewrite (keep commits, prune blobs; A1); the Amplify pipeline shape and the T9 spike (A2); server-side SHA-256 verification for multipart uploads (A3); org-scoped dedup, preview keys and `Blob.status` (A4); commits hashed over `authorId` only (A5); the GC `lastReferencedAt` rule and a backup runbook (A6); `protectedPaths` (A7); `approveRelease` and the approval-record generator (A8). These are days each now and migrations later.

5. **Propagate the decisions through the documents and reposition** (findings D1, C2, C3; medium table). Split Phase 2 into 2a/2b; replace VISION's month counts with the engineer-month table; banner the four prototype docs as superseded; add GTM and market sections; correct the Dropbox framing; lead the public positioning with the release and approval record rather than "Git for creatives"; decide the free tier and instrument the guest-led loop.

---

## 8. Appendix

### A. Every assumption in the financial models

| Assumption | Value | Source |
|---|---|---|
| **Workload (infra model)** | | |
| Reference agency | 12 people, 8 designers, 3 projects | WORKFLOWS §13 |
| Working file size | 2 GB PSD | estimate, verify (T1/T4) |
| Saves per designer per day | 20 | estimate, verify (T1/T4) |
| Captured auto-snapshots per designer per day | 6 (10-minute quiet rule) | estimate, verify (T4) |
| Working days per month | 22 | estimate |
| Milestones per designer per week | 2 | estimate |
| Auto-snapshot retention (squash window) | 30 days | DESIGN §11.3 |
| Uncaptured draft residence before GC | 4 days (weekly GC) | DESIGN §11 |
| Chunk-level dedup reduction for PSD | 60% | estimate, verify |
| Chunk-level dedup reduction for renders / RAW | 40% / 0% | estimate |
| Sync fan-out (auto-snapshots pulled to colleagues' disks) | 1.0 as designed (range 0 to 2.7) | DESIGN §8; product decision |
| Live GB: LIGHT / BASE / HEAVY | 200 / 500 / 1,500 (infra tie-out uses 1,536) | task brief |
| HEAVY live growth | 318 GB/month (293 RAW + 20 renders + 5 design); 12,000 RAW x 25 MB | estimate |
| Previews | ~2% of live; PSD render 20 s x 3 GB Lambda; RAW 20 s x 3 GB | estimate |
| MediaConvert minutes (BASE/HEAVY) | 300/month | estimate |
| Release downloads via CloudFront | 50 / 112 / 154 GB per month | estimate |
| Intelligent-Tiering split | age-aware: newest month Frequent, next 2 Infrequent, older Archive-Instant | reconciled model |
| OpenSearch minimum | 2 OCU (indexing + search) | estimate, verify |
| Free tiers (CloudFront 1 TB, S3 100 GB egress, Cognito 10k MAU) | ignored | modelling choice; would remove ~$5-15/customer-month for the first ~10 customers |
| Solo workload | LIGHT / 8: 1 designer, 1 user, 3 guests, fan-out 0 | reconciled model |
| Plus workload | HEAVY profile at 3 TB live +150 GB/month, team scale 1.0 (2x, 3x as sensitivity) | reconciled model |
| Tier retention cost | window GB x (retention/30 - 1) x $0.023 | reconciled model |
| Platform fixed | $100/month M11-16; $451/month from M17 | infra model |
| AWS unit prices | see section 4 table | Price List API 2026-09-29 unless marked |
| **Build model** | | |
| Phase EM ranges | 0.6-1 / 0.5-1 / 5-8 / 10.5-16 / 9-13 / 10-16 / 9.5-16.5 | estimate (build model), overlapping the technical lens's 60-100 EM envelope |
| Phase calendar | P0 M1, P0.5 M2, P1 M2-5, P2 M6-11, P3 M12-16, P4 M17-21, P5 M22+ | estimate |
| First revenue | M11 (M13 in the STRESS_TEST high case) | build model |
| Base salaries (US remote) | backend #1 $185k; frontend #1 $170k; Rust #1 $200k; designer $155k; devrel/sales $150k at 0.5; backend #2 $160k; Rust #2 $200k | estimate, verify against levels.fyi / Pave / Carta |
| Load factor | 1.3 on base (payroll tax, benefits, HR SaaS) | estimate |
| EU/LatAm seat | 0.55x US base; 50/50 blend (factor 0.775) | estimate |
| Founder/CTO | $0 salary, deferred, excluded; ~50% coding | instruction |
| AWS dev/staging | $1.5k/month | given |
| Tooling | $400/month + $150/head/month + ~$180/month Adobe CC | list prices as of knowledge, verify |
| Developer programs | Apple $99/yr; Windows OV signing ~$500/yr; booked $700 M5 and M17 | list price as of knowledge, verify |
| Legal | ~$1k formation + ~$8k templates M1-3; $1k/month from M6 | estimate |
| Accounting | $500/month + $3k/yr | estimate |
| Hardware | $3.5k per hire; $6k test rigs M5 | estimate |
| Marketing site | $12k contractor M9-10 | estimate |
| Conferences / community | $10k year one (M10); $12k year two (M20) | estimate |
| Insurance | $400/month from M12 | estimate |
| Interview incentives | $1k | estimate |
| **P&L and reconciliation** | | |
| Tiers | Solo $19 / Studio $299 / Plus $899; 250 GB / 2 TB / 8 TB; egress 3x storage; overage $0.10/GB-month storage, $0.08/GB egress | P&L model; anchored to Unity VCS $0.14/GB, Diversion $25/user, Anchorpoint EUR 20/user (RESEARCH §5, verify) |
| Current-stack anchor | Dropbox Business Standard $15/user x 12 + Frame.io Pro $15 x 3 + review tool ~$149 + WeTransfer Pro $12 x 2 = ~$398/month | list prices as of knowledge cutoff, verify |
| New customers per month at M10 | BEAR 1.5, BASE 3, BULL 5 | estimate |
| New-customer growth | 4% / 7% / 9% per month compounding | estimate |
| Monthly logo churn | 3.0% / 2.0% / 1.5% (~31% / 22% / 17% annual), flat across tiers | estimate; SMB self-serve benchmark 3-5%/month for sub-$5k ACV |
| Tier mix (Solo/Studio/Plus) | BEAR 50/45/5; BASE 40/50/10; BULL 35/50/15 | estimate |
| Paid marketing | $6k / $8k / $10k per month from M11 | estimate |
| Founder growth time in CAC | $5k/month (CAC only, not cash) | estimate |
| Support hire | one per 150 customers, $100k base x 1.3 | estimate |
| Burn M25-36 | held at M24 run-rate ($124k payroll + $5.1k non-payroll) plus support and marketing | modelling choice |
| Gross margin | includes platform fixed in total; T2 test shows fixed over 20 and over 50 customers | reconciled model |
| Customer counts | cohort-based, fractional (expected value) | modelling choice |
| Not modelled | annual prepay, tier-specific churn, free tier, sales-assisted Plus deals, price increases, refunds, market saturation | flagged |
| **Market lens (not in the models)** | | |
| Agencies and studios, 10-49 staff, US+UK+EU | ~22,000-30,000; addressable ~5,500-8,500 | estimate, September 2026; primary tables (Census SUSB, ONS, Eurostat) blocked, verify |
| Freelance designers and illustrators | ~300-350k | estimate, verify |
| Achievable ACV | $2-5k | estimate |
| Serviceable market for the wedge | $15-35M | derived estimate |
| **Compliance lens (not in the models)** | | |
| Year-one compliance and risk budget | $60-130k; $40-80k/yr steady state; $300-800/month fixed AWS security overhead | estimate, mid-2026, verify |

### B. Model scripts

| Script | What it produces |
|---|---|
| `/home/user/GitDAM/docs/financials/infra_model.py` | Per-customer variable AWS cost for LIGHT/BASE/HEAVY with whole-file or chunk dedup; platform fixed cost; sensitivities; `--verify-prices` re-fetches every SKU |
| `/home/user/GitDAM/docs/financials/build_cost_model.py` | Role-by-role team plan and monthly burn M1-24, US and EU/LatAm mix; phase EM table |
| `/home/user/GitDAM/docs/financials/pnl_model.py` | Tiers, overage, BEAR/BASE/BULL cohort engine; `--csv` for monthly series; `pnl_summary.json`, `pnl_monthly_*.csv` |
| `/home/user/GitDAM/docs/financials/reconciled_model.py` | Joins the three: per-cohort COGS by workload and age, four configurations A-D, T2/T12 checks, breakeven and cash need; `reconciled_summary.json`, `reconciled_monthly_<scenario>_<config>.csv` |

The `docs/financials/` directory is committed with this document; each script runs with `python3` and no third-party dependencies. Nothing outside it was modified by the review.

### C. Caveat on prices and salaries

AWS unit prices are list prices for us-east-1, on-demand, fetched from the AWS Price List Bulk API on 2026-09-29 (offer files published 2026-09-11 to 2026-09-28); the aws.amazon.com pricing pages themselves were unreachable from the review environment. Three SKUs (Lambda ephemeral storage, EventBridge, the miscellaneous platform line) and the OpenSearch minimum-OCU rule are from knowledge and marked "verify". Salary figures are 2026 US-remote estimates with no live benchmark fetched. Vendor prices (Dropbox, Frame.io, Ziflow, Unity, Diversion, Anchorpoint) are list prices as of the reviewers' knowledge cutoff; every vendor page was blocked. Market-size figures are estimates from reachable anchors because the primary Census, ONS and Eurostat tables were blocked. Every figure in this document must be re-verified against current pricing pages, salary benchmarks and statistical sources before it is used in a pitch, a price page or a contract.
