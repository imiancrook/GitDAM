# GitDAM Plan: Stress Test

An adversarial read of VISION.md, PERSONAS.md, WORKFLOWS.md, DESIGN.md and RESEARCH.md, done before any code is written. The aim is to find the claims that would sink the product if wrong, not to list everything that could be better. Companion: [ASSUMPTIONS.md](./ASSUMPTIONS.md) turns the findings into tests.

## What's Being Claimed

**Central claim.** Creative teams (agencies first) will adopt a Git-shaped asset system if it hides Git's vocabulary, lives inside their existing tools via a desktop sync client, and adds client review, issues and immutable releases; and they will pay for it on storage-based pricing with free guests.

**Sub-claims.**
1. The pain is real and unserved: naming chaos, overwrite loss, sync conflicts, untracked approvals, scattered feedback (RESEARCH §1).
2. A native commit graph (blobs/trees/commits/refs) is the right foundation, and pick-one merges plus locks are the right collaboration model (VISION, DESIGN §2–4).
3. A desktop sync client is the adoption mechanism and can be built reliably enough to displace Dropbox/Creative Cloud for project files (VISION Phase 2, DESIGN §8).
4. Releases with approval records, pinned feedback and issues are what buyers (Rachel) pay for (PERSONAS §6, WORKFLOWS §5).
5. Cross-org delivery creates a growth loop into brands (WORKFLOWS §10.1).
6. Storage-based pricing with free guests and included bandwidth is viable (VISION Pricing principles).

**Not claimed.** Layer-level merging; a brand portal; a general PM tool; parity with Perforce at AAA scale.

## What's Working

- **The problem framing is strong and multiply sourced.** "Last save wins", conflicted copies, "final_v3", version-pinned comments (the Frame.io V4 bug), and implied-approval disputes recur across four independent communities. RESEARCH §7's scorecard is honest about what was confirmed versus inferred.
- **Pick-one merges plus locks** is the correct model for binaries, and the evidence (every competitor leads with locks; Figma's frame-level merge is the cautionary tale) supports it.
- **The permission model was fixed before code.** Per-project roles with a guest projection, organizations as tenant, and the authorize-pipeline decision (DESIGN §1) are more careful than most early-stage designs.
- **Content addressing is well used**: dedup, cheap snapshots, preview keyed by hash, exact-duplicate detection as a UI feature, and S3 checksum enforcement for cross-tenant safety.
- **The persona-first pass caught real gaps** (offboarding, export, SSO, cross-org delivery, usage view) that a feature-first plan would have shipped without.
- **The vendor-absorption risk is named**, with a specific defence (cross-format, client layer, Git export), and the Abstract/Kactus/Pixelapse history backs it.

## Assumptions Under Fire

| # | Assumption | Stated? | Evidence | If wrong | Rating |
|---|---|---|---|---|---|
| A1 | A small team can build a desktop sync client creatives trust with multi-GB PSDs and 60 GB video projects | Implied by Phase 2 (2–3 months) | None. Dropbox, LucidLink and Creative Cloud sync all have years of engineering and still fail (RESEARCH §1.4, §4); the failures are the evidence that this is hard, not that it is easy | Adoption mechanism gone; product becomes a web upload DAM competing with Air/Dash | **Load-bearing risk** |
| A2 | Eager draft upload plus auto-snapshot is affordable | Stated (DESIGN §8, §11) | The cost model ($140/yr for 500 GB) ignores it. A 2 GB PSD saved every five minutes with whole-file dedup only is ~24 GB/hour of upload and, with 30-day squash, potentially terabytes of retained intermediate versions per designer per month. Chunk-level dedup is explicitly deferred (DESIGN §11.5) | Storage-based, bandwidth-included pricing is underwater; or auto-snapshot has to be throttled so far it stops solving the corruption-recovery case it was chosen for | **Load-bearing risk** |
| A3 | Agencies of 10–20 people will pay enough | Implied by first-customer choice | Rachel's "$60k–180k lost margin" and "82% of disputes" figures are vendor blog claims (RESEARCH §6 caveats). No willingness-to-pay data. Storage-based pricing with free guests on a 500 GB agency implies low ACV; the segment is price-sensitive and churny | Revenue does not fund the engineering A1 requires | **Unsupported** |
| A4 | Designers want explorations (branches) | Stated | Figma forum requests and Abstract's existence; but Devexperts wrote "Why Branching in Figma Didn't Work for Us", Abstract died, and VISION already ranks explorations "second-month". The commit graph is justified partly by branching | Phase 1 builds a merge engine few use; but the graph also gives atomic snapshots and releases, so the foundation survives even if branching is rarely used | **Questionable** |
| A5 | Video editors will leave Frame.io for a v1 | Implied by Priya as P1 | Frame.io v3 was praised as "the killer feature" and Adobe owns the editor. Our differentiation for Priya is project-file locks and history, which Adobe Productions and Team Projects partially cover, badly | Priya stays on Frame.io + Productions; GitDAM's video story is a nice-to-have | **Questionable** |
| A6 | Locks enforced by read-only file flags plus a prompt are acceptable UX | Stated (DESIGN §8) | Perforce/Creative Cloud precedent cited; no test. Premiere autosave into a read-only file, Photoshop "Save" failing with an OS dialog, and the timing of the "Check out?" prompt are all untested | Locks feel broken, which is the exact complaint about every competitor | **Questionable** |
| A7 | Cross-org delivery is a growth loop | Stated (WORKFLOWS §10.1) | None. Requires the brand to accept an org (Marcus's SSO/procurement gate sits exactly there) and to keep it after the agency relationship ends | It is a useful delivery feature, not a loop | **Unsupported** |
| A8 | Amplify Gen2 can carry the authorize-pipeline design and a commit graph | Stated with a caveat (DESIGN §1) | Phase 0 already exists because the Amplify beta drifted under the prototype. Pipeline resolver composition "has moved during its beta" | Rewrite of the backend layer mid-Phase 1 | **Questionable** |
| A9 | S3 `ChecksumSHA256` enforces the OID for every upload | Stated (DESIGN §6) | True for single PUT. For multipart, S3 computes a composite checksum over parts, not the full-object SHA-256, unless the full-object checksum mode is used; the design does not say which | Large files (the ones that matter) could be stored under an unverified hash, breaking the cross-tenant safety argument | **Questionable** (verifiable in an afternoon) |
| A10 | Phase estimates (1–3 months each) | Stated | None; single-engineer phrasing in Phase 0 only. Phase 2 alone contains a Rust sync engine, a preview pipeline and visual compare | Roadmap is 2× to 3× longer than written; A3 becomes acute | **Unsupported** |
| A11 | Guests free and unlimited with included bandwidth | Stated | Matches complaints; ignores egress abuse on link-visible releases with 4 GB bundles | Egress cost dominates for video customers | **Questionable** |
| A12 | The research reflects the target segment | Implied | Excerpt-level; no Reddit; heavily game-studio and enterprise-DAM weighted; zero primary interviews with a 10–20 person agency | Persona frustrations are plausible composites rather than observed | **Questionable** |

## Logic & Evidence Gaps

1. **The economics contradict the design.** VISION resolves auto-snapshot toward "auto with milestones" and DESIGN prescribes eager draft upload, while DESIGN §11 defers chunk-level dedup and prices on stored GB with bandwidth included. Whole-file versioning of multi-GB working files at save frequency is the one workload where whole-file dedup gets you nothing. The cost model in §11 was built for a different, calmer workload than the workflows describe. This is a direct internal contradiction, not a missing detail.

2. **Selection bias in the research toward "everything is broken."** The sweeps searched for complaints and found them. They did not search for satisfied users of Frame.io, Dropbox, Creative Cloud or Productions, so the size of the unhappy population is unknown. "Frame.io users complain about V4" does not establish that most editors would move.

3. **Vendor statistics doing load-bearing work.** The approval-record feature, Rachel's buying trigger and the "unbilled rounds" margin story rest on playpause.io, EnterpriseDNA and Ziflow numbers. RESEARCH §6 flags them; PERSONAS §6 and WORKFLOWS §5 then use them as if they were not flagged.

4. **The commit graph is justified by branching, but branching is demoted.** DESIGN §2 argues per-directory trees and a DAG are needed for explorations, releases and merges; VISION ranks explorations second-month and RESEARCH shows weak demand. The remaining justification (atomic snapshots, immutable releases, cheap history) is real but could be served by a simpler linear-history-per-project model with release manifests, at a fraction of the engineering. The docs never weigh that alternative; DESIGN §2's options table compares against "real Git" and "flat per-asset versions", omitting "linear project snapshots without branches".

5. **Two P1 personas, two different products.** Maya's needs (history, restore, pinned feedback, releases) and Priya's needs (locks on project files, proxies, timecode comments, 60 GB sync, path stability) share a data model but almost no surface. Building both to P1 quality in Phase 2 doubles the sync client's hard cases (large-file multipart, placeholders, proxies) at the moment the product is least able to afford it.

6. **"First-week win" and "done" criteria are not measurable as written.** WORKFLOWS §13 says restoring a file is "the moment they decide to keep paying"; nothing defines retention, activation or the number of agencies at which the plan is validated.

7. **Unfalsifiable positioning.** "Behaves like a repository, looks like a DAM" and "no Git vocabulary required" cannot be wrong; they need a usability test with a pass/fail bar (e.g. a designer completes snapshot → restore → exploration → merge without help in under N minutes).

## Fatal Risks

| Risk | What breaks | Condition | Consequence | Severity |
|---|---|---|---|---|
| **F1. The sync client is not good enough** | Adoption; every P1 workflow starts at "Cmd-S in Photoshop" | A small team cannot match Dropbox-grade reliability on macOS and Windows within the roadmap; or File Provider / Cloud Files integration takes a year | Product regresses to a web DAM with version history, a crowded category | **High** |
| **F2. Unit economics fail under the designed workload** | Pricing principles; storage-based, bandwidth-included plans | Auto-snapshot plus eager upload of multi-GB working files without chunk dedup | Either raise prices to per-seat (contradicting the research-driven principle) or throttle snapshots (contradicting the recovery promise) | **High** |
| **F3. The segment can't fund the build** | Everything after Phase 1 | Agencies pay Dropbox-like prices; ACV in the low thousands; sales cycle involves Rachel and sometimes Marcus | Runway ends before Phase 2 ships the client that A1 depends on | **High** |
| **F4. Adobe ships good-enough versioning and locks for Productions and cloud documents** | The video and design wedges simultaneously | Adobe already has cloud documents with history and Productions with locking; fixing them is cheaper for Adobe than GitDAM's entire roadmap | Same fate as Abstract, unless the cross-tool and client-layer defence has already produced customers who value those parts | **Medium** |
| **F5. Amplify Gen2 cannot express the authorization design cleanly** | DESIGN §1 and the whole API surface | Pipeline resolver composition or custom-operation limits force a move to plain CDK/AppSync or a container backend | Weeks lost mid-Phase 1; not fatal to the product, fatal to the schedule | **Medium** |
| **F6. Multipart uploads are not hash-verified** | Cross-tenant blob safety | A9 is wrong and nobody checks | A malicious tenant can poison a shared blob; single worst security outcome in the design | **Medium** (easy to fix once known) |

## Verdict

```
CONFIDENCE RATING: 5/10

STRONGEST ELEMENT: The problem is real, well-evidenced across four communities, and
the collaboration model (locks + pick-one merges + version-pinned comments + immutable
releases) is the correct answer to it.

BIGGEST VULNERABILITY: The plan depends on a desktop sync client that no small team has
shipped reliably, and the workflows it enables (eager upload, auto-snapshot of multi-GB
files) break the pricing model the research chose. The technical and economic bets are
in tension and neither has been tested.

WHAT WOULD MAKE THIS SOLID:
1. Ten primary interviews with P1 personas at 10–20 person agencies before Phase 1,
   with a willingness-to-pay question and a "show me your folder" exercise. Replace
   every vendor statistic in PERSONAS and WORKFLOWS with what they say.
2. Build the cost model for the actual workload: N designers × PSD size × saves per day
   × retention, with and without chunk-level dedup. Decide chunking in Phase 2 or change
   the pricing principle now. Then verify S3 full-object checksums for multipart.
3. Pick one P1 persona for the first release. Maya (design) is the more underserved
   segment (RESEARCH §5 "gaps nobody fills") and has the smaller sync problem; Priya
   has Frame.io and 60 GB. Ship for Maya, keep Priya's model intact, add video second.
4. Run a two-week "concierge" version before building the client: a folder-watcher
   script plus the Phase 1 web app for one friendly agency, to observe snapshot
   frequency, file sizes, and whether anyone opens History or a release page without
   being asked. That data resolves A1, A2 and A3 cheaply.
```
