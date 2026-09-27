# GitDAM Personas

Who interacts with a DAM, what each of them is trying to do, what breaks for them today, and how GitDAM fits. Twelve personas, grouped by relationship to the product: **core users** (the product is built for them), **buyers and gatekeepers** (they approve it), **consumers and guests** (they receive from it), and **adjacent** (they touch it but aren't the target). Frustrations cite [RESEARCH.md](./RESEARCH.md) sections; the named characters reappear in [WORKFLOWS.md](./WORKFLOWS.md).

Each persona has a **role** mapping to the permission model in [DESIGN.md §1](./DESIGN.md#1-tenancy-and-permissions), a **first-week win** (what makes them keep using it), and a **churn risk** (what makes them leave).

Priority key: **P1** build for them first · **P2** second-month features · **P3** later · **—** not a target.

---

## Core users

### 1. Maya, the brand and graphic designer — P1

| | |
|---|---|
| **Works at** | 12-person agency, three concurrent clients |
| **Tools** | Photoshop, Illustrator, InDesign, occasionally Figma; Dropbox for everything; Slack |
| **Files** | 50 MB–2 GB PSD/AI/INDD sources; PNG/PDF exports; fonts; stock |
| **Role in GitDAM** | editor |

**Trying to do.** Get a client-ready export out of a source file while keeping the source in a state she can return to. Try a bolder direction without losing the safe one. Know which of the eleven files on disk is the one the client saw.

**What breaks today.**
- `hero_final_v3_FINAL_revised.psd` is the version control system (RESEARCH §1.2).
- Saved over a file, no way back; Illustrator has no history panel at all (§3).
- Dropbox conflicted copies "every time" she moves between office and home; a colleague's sync made "thousands of conflicted copy files" (§1.4).
- Client feedback arrives as email screenshots she has to map back onto the file (§1.6).

**How GitDAM fits.** The desktop client sits under her normal folder; Cmd-S in Photoshop is enough. Snapshots with a message replace "Save As v4". Explorations for the bold direction. History with thumbnails and one-click restore. Pinned feedback lands on the pixel.

**First-week win.** Restoring a ruined file from Tuesday's snapshot. **Churn risk.** The sync client is flaky or slow, or asks her to learn Git words. She has already rejected tools for both reasons.

**Success metric.** She stops naming files with version suffixes within a month.

---

### 2. Priya, the video editor — P1

| | |
|---|---|
| **Works at** | Same agency, or a 5-person post house |
| **Tools** | Premiere, After Effects, sometimes Resolve; Frame.io for review; a RAID plus LucidLink or Dropbox |
| **Files** | 30–80 GB projects; `.prproj`/`.aep` project files that must not be opened by two people; multi-GB renders |
| **Role in GitDAM** | editor |

**Trying to do.** Cut, render, get notes, cut again, and keep the approved cut findable forever. Never lose a day to a corrupted project file. Never have another editor overwrite her project.

**What breaks today.**
- "Whoever clicks 'save' last will overwrite all the work done by another editor" (Frame.io's own guide, §1.3). Adobe Team Projects "quietly breaking saving" (§4).
- Project file corrupts and "autosave was dutifully saving corrupted files" (§1.3).
- Frame.io V4 comment markers "constantly revert to refer to the older version" (§1.6); pricing pushed toward Enterprise (§4).
- Relinking media "40+ minutes every time a project opens"; renaming a drive takes everything offline (§4).
- 86 GB browser download failing at 50 GB, four days running (§1.9).

**How GitDAM fits.** Check-out on project files is mandatory and automatic. Every save is an auto-snapshot; corruption means "restore the one from 14:02". Timecode comments pinned to the exact render. Stable local paths so Premiere never relinks. Resumable multipart uploads. 720p proxies for reviewers.

**First-week win.** The lock icon with her name on the project file, visible to everyone. **Churn risk.** Upload throughput on large renders; any path shuffling by the client.

**Success metric.** Zero "who overwrote my project" incidents; review notes addressed from the timeline, not from email.

---

### 3. Theo, the creative director — P1

| | |
|---|---|
| **Works at** | Runs the agency's creative output; 4–6 direct reports |
| **Tools** | Reviews on a laptop and phone; Slack, email, Keynote; rarely opens source files |
| **Role in GitDAM** | owner |

**Trying to do.** See what everyone is working on without asking. Give feedback that lands in the right place. Approve work with a record. Answer "what did we send the client in Round 2?" six months later.

**What breaks today.**
- "Implied approval is the source of more post-project disputes than almost anything else in agency work" (§1.7).
- Feedback wrangling costs one person's time; "67% of unplanned revision rounds come from vague, unstructured or late client feedback" (§1.6).
- Review tools where "clients can be put off by it because it can look a little overwhelming" (§3).
- Account managers "reconstruct timelines from memory and screenshots" (§3).

**How GitDAM fits.** Activity feed with before/after thumbnails. Pinned comments on regions. Review requests with an explicit approve. Releases that are immutable, with an approval-record PDF. A board that shows client feedback as tracked work.

**First-week win.** Publishing a release page to a client and getting pinned feedback back as issues. **Churn risk.** The team doesn't adopt the desktop client, so the feed is empty and he's back to asking in Slack.

**Success metric.** Every client deliverable in the last quarter has a release with an approval record.

---

### 4. Sam, the technical artist — P2

| | |
|---|---|
| **Works at** | 30-person game studio, or a VFX shop with a pipeline TD |
| **Tools** | Blender, Substance, Unreal/Unity, Git, Perforce, Python; a CI server |
| **Files** | `.blend`, FBX/USD, textures, thousands of small assets; needs partial checkout |
| **Role in GitDAM** | editor (plus a PAT for CI) |

**Trying to do.** Keep art in a system artists will actually use, while the build pipeline pulls it with `git`. Enforce budgets (texture sizes, poly counts) automatically.

**What breaks today.**
- Perforce: "administrative complexity and cost can be high", GUI "confusing, especially for non-engineers" (§5).
- Unity VCS: "why is it terrible?", hangs, corrupted prefabs (§5).
- Git LFS: locking bugs open since 2024; GitHub billing the owner for every CI clone (§1.5, §1.9).
- Anchorpoint and Diversion are Win/Mac only; the artists like them, the Linux build box doesn't (§5).

**How GitDAM fits.** `git clone` via the bridge; LFS locks that are the same locks the artists see; webhooks so CI files issues against over-budget assets; Rust core keeps a Linux client possible.

**First-week win.** A clean `git clone` and a CI job filing its first issue. **Churn risk.** Bridge performance on 100k-file trees; missing Linux client.

**Success metric.** Artists stop asking Sam how to use version control.

---

### 5. Lena, the illustrator or freelancer — P2

| | |
|---|---|
| **Works at** | Solo, or 2–3 people; several clients at once |
| **Tools** | Procreate, Photoshop, Clip Studio; WeTransfer and Google Drive for delivery |
| **Files** | Large layered PSDs; many exports per piece |
| **Role in GitDAM** | owner of a one-person org; guest in clients' projects when they use GitDAM |

**Trying to do.** Keep her own history without paying per-seat for a team tool. Send clients something better than a WeTransfer link that expires. Prove which version was approved when the invoice is disputed.

**What breaks today.**
- WeTransfer links expire in three days; free tier caps (§4).
- Adobe cloud documents delete unmarked versions after 30 days (§1.4).
- Every team tool prices per seat and charges for her clients as guests (§1.8).

**How GitDAM fits.** Storage-based pricing with free guests. Release pages instead of transfer links. Approval record on the release.

**First-week win.** A release page a client can open on their phone. **Churn risk.** Price above a Dropbox subscription; any onboarding friction, because nobody is making her use it.

**Success metric.** She sends her next three client deliverables as release pages.

---

## Buyers and gatekeepers

### 6. Rachel, the agency owner or operations lead — P1 (buyer)

| | |
|---|---|
| **Works at** | Owns or runs the 10–40 person agency |
| **Cares about** | Margin, disputes, key-person risk, tool sprawl, predictable costs |
| **Role in GitDAM** | admin |

**Trying to do.** Stop losing margin to unbilled revision rounds. Stop losing work when someone leaves. Reduce the Dropbox + Frame.io + Ziflow + Drive stack to fewer bills.

**What breaks today.**
- Coordination overhead estimated at "$60,000 to $180,000 per year in lost margin" for agencies; one extra unbilled round per month across 15 accounts is "45 to 75 hours monthly" (§3).
- "82% of agency overruns involving client disputes cite the absence of a formal approval record" (§1.7).
- Per-seat tools: "a 25-person creative team costs roughly 2× what a 12-person team costs" (§2); Markup.io's 350% increase with no grandfathering (§3).

**How GitDAM fits.** Approval records; releases as a contractual artifact; storage-based pricing that doesn't punish hiring; everything a departing designer did is in history.

**Buying trigger.** A dispute where the agency couldn't prove sign-off, or a departure that took the only copy of the source files. **Churn risk.** Team doesn't adopt (see Theo); pricing surprises.

**Success metric.** Fewer unbilled rounds; one fewer SaaS bill.

---

### 7. Devon, the marketing operations manager (mid-market brand) — P3

| | |
|---|---|
| **Works at** | 200–2,000 person company; marketing team of 10–30; agencies and freelancers outside |
| **Tools** | Bynder/Brandfolder/Canto-class DAM, or a shared drive that everyone hates; Asana or Monday; Workfront if unlucky |
| **Role in GitDAM** | owner of the brand org; admin over agency guests |

**Trying to do.** One place where approved assets live, findable by sales and regional teams, with usage rights attached. Stop paying for a DAM that's "technically successful, operationally inert" (§1.1).

**What breaks today.**
- Adoption: "the DAM was built for one type of user and tolerated by the rest" (§1.1); 37% of switchers cite low adoption (§2).
- Tagging is "a very manual process"; search "hit or miss", degrades past ~100k assets (§1.10).
- "No duplicate detection" (§2); 83% have recreated an asset they couldn't find (§6).
- Per-seat and guest pricing; "every single time you update your software, you charge for it" (§1.8).
- Lock-in: metadata "does not write back into the asset when downloaded"; bulk export gated (§2).

**How GitDAM fits.** Agencies deliver *into* the brand's GitDAM as releases, so the approved library populates itself. Exact-duplicate detection. Automatic metadata. Git-compatible export as the anti-lock-in guarantee.

**Why P3.** Devon wants brand portals, rights management, templating and channel integrations that are a different product. GitDAM reaches Devon through agencies (Rachel) who already deliver releases; Devon's org is the *receiving* side first. Rights metadata is reserved in the model (DESIGN §2.5) for this reason.

**Buying trigger.** Renewal of an underused DAM. **Churn risk.** Missing brand-portal features; sales team finds it too developer-ish.

---

### 8. Marcus, IT / security / procurement — P2 (gatekeeper)

| | |
|---|---|
| **Works at** | The same mid-market brand, or a studio big enough to have one |
| **Cares about** | SSO, data residency, audit logs, export, offboarding, vendor viability |
| **Role in GitDAM** | admin, rarely logs in |

**Trying to do.** Say yes without regret. Know that when someone leaves, their access ends and their work stays. Know the org can get its data out.

**What breaks today.**
- "Implementations stall when access controls don't map to HR identity systems" (§2).
- AEM: "surprisingly facile access controls only allow you to set permissions on folder" (§2).
- Vendor lock-in and the EU Data Act (§2). Post-acquisition stagnation and price changes (Brandfolder, Unity VCS, LucidLink Classic) (§2, §4, §5).

**How GitDAM fits.** Org/project roles, PATs with scopes, append-only activity and issue audit, region-per-org, and `git clone` as a complete export. Published pricing with grandfathering answers the vendor-viability question in part.

**Requirements before he signs.** SSO (SAML/OIDC) and SCIM, which are not in Phases 0–5 and should be added to Phase 5 when the first mid-market deal needs them. **Churn risk.** A security questionnaire the product can't answer.

---

## Consumers and guests

### 9. Dana, the client stakeholder — P1 (guest)

| | |
|---|---|
| **Works at** | Marketing manager at the agency's client; also legal, the CEO's assistant, a franchisee |
| **Tools** | Email, phone, PowerPoint; will not install anything; reviews on a phone at 9 pm |
| **Role in GitDAM** | guest |

**Trying to do.** See the current version, say what's wrong, approve, and get the files. Not learn a tool.

**What breaks today.**
- Review tools where clients are "confused on how to use it or leave their comments" (§3); "training clients can take some time" (§3).
- Frame.io pricing and interface "heavier" post-Adobe; Markup.io load times "almost a minute" (§3).
- WeTransfer links expired; "which version are we looking at?" (§3).

**How GitDAM fits.** A release page: title, notes, gallery, download-all, a pin-and-comment on any asset, an approve button. No history, no source folders, no jargon. Free and unlimited as a guest. Feedback becomes issue #23 and Dana gets told when it's done.

**First-week win.** Leaving feedback in under a minute without a login walkthrough. **Churn risk.** Not applicable to Dana directly, but if Dana complains, Theo churns.

**Success metric.** Client feedback arrives through release pages, not email, for the majority of rounds.

---

### 10. Jamal, the internal consumer (sales, regional, product) — P3

| | |
|---|---|
| **Works at** | The brand (Devon's company); needs the approved logo, the latest deck template, the product shots |
| **Role in GitDAM** | guest or reviewer on client-visible paths |

**Trying to do.** Find the approved asset in thirty seconds and use it. Never use an old one by mistake.

**What breaks today.** 54% of office professionals waste time searching for files; 83% have recreated an asset they couldn't find (§6). Old versions circulate because nobody knows which is current.

**How GitDAM fits.** Releases are the "approved" set by definition; search over the main line with automatic metadata; collections across projects.

**Why P3.** This is the brand-portal use case, downstream of Devon. Served once the brand-side org exists.

---

## Adjacent

### 11. Kim, the DAM librarian / digital asset manager — P3

| | |
|---|---|
| **Works at** | Larger brands, museums, publishers, universities |
| **Cares about** | Taxonomy, controlled vocabularies, rights, metadata standards (IPTC/XMP), archival integrity |
| **Role in GitDAM** | owner |

**Trying to do.** Govern a library over decades. Their frustrations are that "DAM vendors are not particularly attentive to metadata issues" and systems "may not read all metadata on ingest" (§1.10).

**How GitDAM fits, and doesn't.** Content addressing and immutable history are exactly what an archivist wants; the metadata model (a JSON bag with automatic fields) is not. Kim needs schema, vocabularies, XMP round-tripping and rights. Not a target until there is a governance layer. Worth talking to, because Kim knows what a *correct* metadata model looks like and will find the gaps in ours.

---

### 12. Ana, the photographer / retoucher — P2

| | |
|---|---|
| **Works at** | Solo or small studio; shoots for the agency and the brand |
| **Tools** | Lightroom, Capture One, Photoshop; card offload workflows |
| **Files** | RAW (CR3/ARW/DNG), 20–60 MB each, thousands per shoot; a Lightroom catalog that can't be synced safely |

**Trying to do.** Deliver selects and retouched finals, keep RAWs findable, never corrupt the catalog.

**What breaks today.** Dropbox-synced Lightroom catalogs produce "duplicate conflicted copies of the same catalog or corrupted catalogs that cannot be repaired" (§3). Delivery via expiring links.

**How GitDAM fits.** RAW previews (libraw), releases for delivery, history for retouching rounds. Catalogs are a single-writer file: check-out required. Thousands of files per shoot exercise the tree-sharding and preview backlog paths in DESIGN §2.2 and §7, which is why Ana is P2 rather than P1: the product needs to be hardened before her volumes.

---

## Reading the personas together

**Who has to love it:** Maya and Priya (daily use), Theo (sees the value), Dana (doesn't hate it). Rachel pays. Everything in Phases 0–3 serves these five.

**Who unlocks the next segment:** Sam brings studios and the Git bridge; Lena brings the long tail on storage-based pricing; Marcus is the gate to any deal over ~50 seats and needs SSO/SCIM added to the plan.

**Who we reach through others:** Devon and Jamal receive releases from agencies before they ever buy; that's the wedge into brands. Kim tells us what our metadata model is missing.

**The tensions to keep in view:**
- Maya wants no vocabulary; Sam wants Git. Two front doors to one model (VISION "concept translation"); never let Sam's needs leak into Maya's UI.
- Priya needs locks to be strict; Maya finds strict locks annoying on small exports. Check-out rules are per file type, per project (WORKFLOWS §1).
- Dana needs a page with almost nothing on it; Theo needs the board with everything. Guest views are a separate projection (DESIGN §12), not a filtered version of the full UI.
- Rachel wants storage-based pricing; Devon's procurement is used to seat-based quotes. Publish the storage price; offer an annual invoice for Marcus.
