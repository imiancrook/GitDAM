# Riskiest Assumptions and How to Test Them

From [STRESS_TEST.md](./STRESS_TEST.md). Each assumption gets a test that can be run before or during Phase 1, a pass bar decided in advance, and what changes if it fails. Ordered by (severity × cheapness to test). The first four can be done in three weeks with no product code beyond Phase 0.

| # | Assumption (from STRESS_TEST) | Test | Pass bar | Cost | If it fails |
|---|---|---|---|---|---|
| T1 | **A3/F3** Agencies will pay | 10 interviews with P1 personas at 10–20 person agencies (guide below); end with a price ladder | ≥6 of 10 name a current loss (dispute, lost file, overwrite) in the last year unprompted; ≥5 say they'd pay ≥ $X/month at the storage-based price (X set from the cost model in T2) | 3 weeks, no code | Move upmarket (30–100 person studios, Sam's segment) or to freelancers at a lower price with self-serve only |
| T2 | **A2/F2** Economics under auto-snapshot | Spreadsheet model: designers × working-file size × saves/day × retention × dedup rate. Then measure the real numbers in T4 | Gross margin ≥ 70% at the published price with observed save frequency, with whole-file dedup only | 2 days | Chunk-level dedup moves to Phase 2 (before the client ships), or pricing becomes storage + per-editor, or auto-snapshot throttles to milestones-only for files over N GB |
| T3 | **A9/F6** Multipart uploads are hash-verified | Read the S3 checksum docs; upload a multipart object with `ChecksumAlgorithm: SHA256` and full-object checksum type; confirm S3 rejects a mismatched final hash | S3 rejects the mismatch | Half a day | Verify server-side after upload (stream the object, hash, delete on mismatch) before flipping `verified`; costs one read per large upload |
| T4 | **A1/F1** People will let a sync client own their project folder | Concierge: one friendly agency, two designers, two weeks. A folder-watcher script (Python, no UI) that uploads changed files to the Phase 1 backend and creates snapshots; History and release pages in the web app | Both designers still using it in week two without prompting; ≥1 restore or release page opened unprompted; observed save frequency and file sizes recorded for T2 | 2 weeks after Phase 1's `createCommit` exists | The wedge is not the folder; consider the Adobe panel (explicit snapshot from inside Photoshop) as the primary client instead of file-sync |
| T5 | **A6** Read-only locks are acceptable | Prototype: a script that flips a PSD and a `.prproj` to read-only; a designer and an editor try to save; observe what Photoshop, Premiere autosave and After Effects do | Neither app loses work or silently fails; the failure dialog is one the user understands | 1 day | Locks must be enforced by the Adobe panel (Phase 4 moves up) rather than by the file system |
| T6 | **A4** Explorations are wanted | In T1 interviews: "tell me about the last time you wanted to try a direction without touching the main file; what did you do?" | ≥5 of 10 describe a workaround (duplicated file, separate folder) in the last month | Free with T1 | Ship history, locks and releases first; explorations after the first ten customers ask |
| T7 | **A5** Video editors will move | In T1 include 3 editors; ask about Frame.io V4, Productions, and the last overwrite or corruption | ≥2 of 3 rank "nobody can overwrite my project" above "timecode comments" | Free with T1 | Video becomes second segment; Maya-first confirmed |
| T8 | **A12** Personas match reality | T1 "show me your folder": screen-share the current project folder and last three client emails | Naming chaos and scattered feedback visible in ≥7 of 10 | Free with T1 | Rewrite personas from observation |
| T9 | **A8/F5** Amplify Gen2 carries the auth design | Phase 1 step 2 spike: implement `authorize.js` + one custom mutation + one Lambda-backed pipeline exactly as DESIGN §1 describes | Works, deploys in sandbox, latency < 150 ms for the authorize step | 3 days | Drop to plain CDK + AppSync (same services, no Amplify abstractions) before more is built on it |
| T10 | **A7** Cross-org delivery is a loop | After 5 paying agencies: count brand-side orgs created via delivery that are still active 60 days later | ≥2 of first 10 delivered-to brands log in again after the campaign | Free once shipped | It is a feature, not a loop; drop the growth claim from the pitch |
| T11 | **A10** Phase estimates | Re-estimate Phase 2 after T4 with the sync client scoped to Maya only (no placeholders, no proxies) | ≤ 3 months for one engineer, otherwise the roadmap is rewritten before commitment | 1 day | Cut Priya's Phase 2 items to Phase 4 |
| T12 | **A11** Free guests and included bandwidth | In T2 model egress from link-visible releases at observed download counts (from T4) | Egress < 15% of revenue at the published price | Free with T2 | Bandwidth allowance per stored GB, overage shown ahead (already designed), or link downloads served via CloudFront only |

## Interview guide (T1, T6, T7, T8)

45 minutes, screen-share, one interviewer, one note-taker. Recruit through agency owners (Rachel) but interview the designer or editor alone. Do not show the product; do not say "version control".

1. **Show me.** "Open the folder for the project you worked on most recently. Walk me through what's in it." (Note file names, duplicates, how they find "the current one".)
2. **The last time it went wrong.** "Tell me about the last time you lost work, or sent the wrong version, or two people changed the same file." Ask when, what it cost, what they did afterwards. (T1 loss; T8.)
3. **Feedback.** "Show me the last three pieces of client feedback you received. Where did they arrive, and how did you get them into the file?" (Scattered feedback; pinned comments value.)
4. **Approval.** "When a client approves something, where does that live? Has a client ever said they didn't approve something you delivered?" (Approval record; dispute.)
5. **Trying things.** "Last time you wanted to try a different direction without wrecking the main file, what did you do?" (T6.)
6. **Video only.** "What happened with Frame.io V4? Have you ever had another editor overwrite your project? What do you do about it?" (T7.)
7. **Tools.** "What do you pay for today for storage, review and transfer? Which one would you drop first?" (Tool sprawl; budget.)
8. **Price ladder.** Describe, in one sentence, a folder that keeps every version, shows who changed what, and gives clients a page to approve on. "If that cost your studio $A / $B / $C a month for all of you and unlimited clients, which is the first number that feels too high?" (Willingness to pay; run the ladder from the T2 model.)
9. **Close.** "If this existed next month, what would stop you from installing it?" (Trust in a sync client; IT; habit.)

Record: loss events with dates, save frequency (ask "how often do you hit save on a big file?"), typical file sizes, and the first "too high" price. Ten interviews produce every number T1, T2, T6, T7 and T8 need.

## Decisions taken now, pending tests

These are changes to the plan made on the strength of the stress test alone; the tests above can reverse them.

1. **Maya first.** The first shippable release targets the designer persona. Priya's data model stays intact (locks, path stability, multipart) but proxies, placeholders and timecode review move to the second release. RESEARCH §5 shows design teams are the segment nobody serves; video has Frame.io.
2. **A validation phase (Phase 0.5) precedes Phase 2.** T1–T5 and T9, with the concierge test running on the Phase 1 backend. No sync-client code before T4's numbers exist.
3. **The cost model is a deliverable**, owned before pricing is published, revisited with T4's measurements.
4. **Chunk-level dedup is no longer "not before a customer demands it"**; it is "decided by T2". If the model says whole-file versioning of working files is underwater, chunking is Phase 2.
5. **Vendor statistics are quarantined.** PERSONAS and WORKFLOWS may cite them as illustration, never as the reason for a feature; the reasons are the interview findings once they exist.
