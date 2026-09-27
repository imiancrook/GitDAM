# GitDAM Workflows

Derived from [PERSONAS.md](./PERSONAS.md): each persona's jobs come first, and every workflow exists because a job needs it. Where a job had no workflow, one was written; where that exposed something the product didn't have, it is flagged **NEW** and traced to the roadmap in §14. Screens are named so [DESIGN.md](./DESIGN.md) has something concrete to serve. Git terms appear in brackets once for orientation; users never see them.

Personas in priority order: Maya (designer), Priya (video editor), Theo (creative director), Dana (client guest), Rachel (agency owner), then Sam, Lena, Marcus, Ana, Devon, Jamal. Kim (DAM librarian) is not a target and has no workflows here.

---

## 1. Maya, brand designer (P1)

**Jobs:** work in Photoshop without changing habits · always be able to go back · try a direction safely · get feedback on the pixel, not in email · know which file the client saw.

### 1.1 Work, snapshot, move on
The loop the product lives or dies on. It must be less friction than "Save As… v3".

1. Maya opens `source/hero-poster.psd` in Photoshop and works for two hours, saving normally (Cmd-S) many times.
2. The desktop app notices each save. In the tray and the web app the file shows **Draft: changed 2 min ago** [modified in working tree]. The bytes have already uploaded in the background [blob pushed, no commit], so the eventual snapshot is instant.
3. After a quiet period the app takes an **auto-snapshot** ("Auto-snapshot 14:02"). At a stopping point she clicks the tray icon, sees **3 changed files** with thumbnails, types *"Hero poster: swapped to the teal palette, new headline"*, clicks **Snapshot** [commit]. That one is a **milestone**; history shows milestones by default and folds auto-snapshots under a "12 auto-snapshots" row.
4. Ten seconds later Theo's Activity feed shows before/after thumbnails.

She never named a file, picked a version number, uploaded anything, or decided where it goes. Offline works: snapshots queue and upload in order.

### 1.2 Going back
- **"I ruined the file."** Open **History** for `hero-poster.psd`: a filmstrip of every snapshot with thumbnails. Pick Tuesday's, **Restore this version**. It becomes a new snapshot on the main line [restore commit]; Wednesday's version is still there if she was wrong about being wrong.
- **"I deleted a folder."** Project **History**, the snapshot before the deletion, **Restore folder**.
- **"Photoshop crashed and the file won't open."** Same as the first case; the auto-snapshot from before the crash is one click away. This is the case Adobe's forums say is unrecoverable today (RESEARCH §1.3).

### 1.3 Trying a direction without breaking the main line
Theo asks for "a bolder version of the hero poster, but keep the current one alive for Thursday's call."

1. Project menu → **Start an exploration** [branch], named *bold-hero*, from *Main line, as of now*.
2. The desktop app asks *Switch this folder to the exploration?* Files that differ are swapped on disk (none yet). The folder badge reads **bold-hero**.
3. She works and snapshots as in 1.1; main is untouched.
4. Thursday: the client picks bold. **Bring into main line** [merge]. Only *bold-hero* changed the poster, so it merges cleanly and the exploration is archived.

If Theo had also changed the poster on main, the merge screen shows **Choose a version**: two thumbnails, *Keep main line* / *Use bold-hero* / *Upload a combined file*. No pixel merging. With check-out required on PSDs (1.4) this is rare because Theo would have been told Maya holds the file.

For a one-afternoon experiment she doesn't branch at all: work, snapshot, and **Restore** if it's wrong. Explorations are for work that must coexist with the main line for more than a day.

### 1.4 Being told before a collision
`hero-poster.psd` requires **check-out** [LFS lock] in this project's settings. When Maya first saves it, the desktop app takes the check-out for her and the web app shows a lock icon with her name. If Theo opens it meanwhile, Photoshop opens it read-only with a banner: *Checked out by Maya since 10:15. Ask for it?* Snapshotting releases the check-out (project default). If she forgets and goes on leave, Theo (owner) can **Take over** with a reason; she is notified.

### 1.5 Feedback on the pixel
Covered by Theo's review (3.1) and Dana's feedback (4.1) from Maya's side: a pin appears on the poster at the headline with *"kerning on 'Spring' is tight"*; she fixes it and snapshots; the pin shows *resolved in snapshot "Fix kerning"* with a before/after. From the desktop app, **Assigned to you: #23** opens the pinned asset at the pinned version and offers **Open source file**.

### 1.6 Which one did the client see?
Releases (3.3) answer it: the file in the release is the one the client saw, byte for byte, with the approval record attached. In the browser, any asset shows **In releases: Round 2, Round 3** so she can tell at a glance.

---

## 2. Priya, video editor (P1)

**Jobs:** never be overwritten by another editor · never lose a day to a corrupt project · get timecode notes on the right cut · keep media linked · move 60 GB without babysitting a browser.

### 2.1 Syncing a 60 GB project
**Choose folders**: `/footage` as *placeholders* (she has it on a RAID and points Premiere there), `/project-files` and `/exports` fully. Placeholders show in Finder with size and a cloud badge; double-click downloads. Until placeholders ship (Phase 4), the same dialog offers *Download on demand* from a list in the app.

**Path stability.** The client never renames or moves files, and the project root never changes (DESIGN §8). Premiere sees the same absolute paths forever; relinking, the top Premiere grievance (RESEARCH §4), does not happen because of GitDAM.

### 2.2 Nobody overwrites the project file
`.prproj` and `.aep` require check-out in the *Video* project template. On first save the app takes it; Theo's web app shows the lock with her name. A second editor opening the file gets it read-only with *Checked out by Priya since 10:15. Ask for it?* Priya sees the request in the tray and can **Hand over** without leaving Premiere; her last auto-snapshot is what the other editor gets.

### 2.3 Corrupt project, autosave also corrupt
Auto-snapshots run on every quiet period, and older ones are kept (squashed after 30 days but never to zero). **History** on `northwind-30s.prproj` → the snapshot from before the corruption → **Restore**. The known failure where "autosave was dutifully saving corrupted files" (RESEARCH §1.3) has a fix because there are twenty earlier saves, not one.

### 2.4 The render goes up while she keeps working
The 4 GB export to `/exports` uploads in parallel multipart chunks with progress in the tray; it resumes after sleep or a dropped connection. End of day: snapshot *"Rough cut v1, 30s."*

### 2.5 Notes that land on the timeline
Theo (3.1) or Dana (4.1) watches the server-generated 720p proxy and drops a comment at **00:12:04** *"cut is late here"*. The comment is pinned to that render's snapshot and that timecode. When Priya uploads *Rough cut v2*, the v1 comments stay on v1 and show as *placed on an older version* with a jump; they never silently move (the Frame.io V4 bug, RESEARCH §1.6). The Adobe panel (Phase 4) shows them as timeline markers.

### 2.6 Delivering the approved cut
Release (3.3) with the export; Dana approves from her phone; the approval record names the exact render.

---

## 3. Theo, creative director (P1)

**Jobs:** see what everyone is doing without asking · give feedback that lands · approve with a record · answer "what did we send in Round 2?" a year later · run the client round from one board.

### 3.1 Review and approve
Nothing in `/exports` goes to the client without Theo's approval; `/exports` on the main line is **protected** [protected branch].

1. Maya clicks **Request review** [pull request] from *bold-hero* to main, optionally *Resolves #17*.
2. Theo's **Review** screen: changed files, each with **Compare**. Images: side-by-side, wipe, onion-skin, *difference* (changed pixels highlighted) [diff]. Video: two proxies, linked scrubber. PDF: page by page.
3. He drops a pin and writes a note → **Request changes**. Maya fixes and snapshots; the review updates; the pin shows resolved with a before/after.
4. **Approve and bring into main line.** Issue #17 → *Done*. Activity shows the merge with both names.

Reviews are optional per project; a solo illustrator has none.

### 3.2 The board
Columns are issue states: *New → To do → In progress → In review → Done*. Cards show the pinned asset's thumbnail, so a board of creative work looks like creative work. Filters by milestone, assignee, label, kind. Theo plans a round by creating issues from a template (*Round 3: hero poster, three social crops, email header*) under milestone *Round 3*, triages Dana's feedback from *New*, and runs standup from it.

### 3.3 Shipping a release
1. Milestone *Round 3* shows *7 of 7 done*. **Close milestone and create release.**
2. Title, notes drafted from the closed issues (*"Enlarged ® on hero poster (#23)…"*), scope *client-visible folders only*, visibility *guests* or *link*.
3. **Publish.** The main line is stamped [tag], a zip is built, a share page is made, guests are notified.
4. The release carries an **approval record**: a generated PDF of what was approved, by whom, when, with thumbnails and the review thread. Rachel (5.2) is the reason it exists.

A year later: Releases → Round 3 → **Browse files** (read-only), **Download all**, or **Open as exploration** to work from it [checkout tag into a branch]. Immutable, byte for byte.

### 3.4 Seeing everything
The **Activity** feed per project and across the org: snapshots with thumbnails, reviews, releases, locks taken and released, issues moving. Subscriptions push it live. This replaces "what's everyone on?" in Slack, and it only works if Maya and Priya use the desktop client, which is why that client is Phase 2.

---

## 4. Dana, client stakeholder (P1, guest)

**Jobs:** see the current version · say what's wrong, precisely · approve · get the files. Not learn a tool; not install anything; do it on a phone at 9 pm.

### 4.1 Feedback becomes tracked work
1. Theo publishes **Release: Round 2**. Dana gets an email link. The page: title, notes, a gallery of exports, **Download all**. No history, no sources, no jargon.
2. She taps the hero poster, drops a pin on the logo, writes *"Legal says the ® has to be visible at this size."*, taps **Send feedback**. That creates issue #23, kind *Feedback*, pinned to `exports/hero-poster.png` at Release Round 2 with her region.
3. It appears in Theo's *New* column (3.2). Maya fixes it (1.5). Dana gets *Your feedback #23 was addressed in Release Round 3* with a before/after.

### 4.2 Approving
The release page has **Approve** (and *Request changes*). Approving records her name, the time, and the exact files; that is what the approval record (3.3) contains. She never learns what a snapshot is.

### 4.3 What Dana never sees
Source folders, explorations, the full board, other clients. Guest views are a separate projection (DESIGN §12), not a filtered version of the full UI. A guest who is also a GitDAM user elsewhere (Lena, 7.3) sees the same simple page.

---

## 5. Rachel, agency owner (P1, buyer)

**Jobs:** stop losing margin to unbilled rounds · win the dispute · keep the work when a designer leaves · fewer bills · know what it costs before the invoice.

### 5.1 Buying and setting up
Rachel signs up, names the org *Fieldwork Studio*, sees the published storage-based price, and invites Theo as admin. Theo creates projects from templates (*Brand & Print*, *Video*, *Blank*): each template sets preview handling, which file types require check-out, and a folder skeleton. He adds editors and, per project, client guests. Guests are free and unlimited. Target: under 30 minutes, no documentation.

### 5.2 The dispute
A client claims they never approved the cut that was delivered. Rachel opens Releases → *Round 3* → **Approval record**: Dana approved on the 14th at 21:40, these files, with the review thread and Dana's own pinned comments resolved. She sends the PDF. This is the single artifact that answers "implied approval" disputes (RESEARCH §1.7), and it is why the release model is strict about immutability.

### 5.3 Offboarding a designer — NEW
Maya leaves. Org settings → Members → **Remove Maya**. The dialog shows what she holds: 2 check-outs (released, or handed to a named person), 4 assigned issues (reassigned), 1 open review (reassigned or closed). Her snapshots, comments and approvals stay in history under her name; her access ends immediately; her PATs are revoked. Nothing she made was only on her laptop, because drafts uploaded eagerly and auto-snapshots ran.

### 5.4 Fewer tools
Release pages replace WeTransfer and the review tool; the desktop client replaces Dropbox for project files; issues replace the feedback spreadsheet. Rachel keeps Asana if she has it; GitDAM issues are the asset-level layer beneath it.

### 5.5 Knowing the cost — NEW
Org settings → **Usage**: stored GB per project, egress this month against the included allowance, what the next invoice will be. Overage is shown here before it happens, never first on the invoice. Archived explorations and GC-reclaimable data are listed with a **Clean up** button.

---

## 6. Sam, technical artist (P2)

**Jobs:** art in a system artists use, pulled by the build with `git` · budgets enforced automatically · locks that work from both sides.

### 6.1 Git access
Project settings → **Git access**: `https://git.gitdam.app/oakline/dungeon-art.git` and a personal access token. `git clone` yields LFS pointers and `.gitattributes`; `git lfs pull` fetches binaries from the same store the artists use. The build server clones with `GIT_LFS_SKIP_SMUDGE=1` and pulls only the paths it needs.

### 6.2 Both sides see the same lock
`git lfs lock Characters/Hero.blend` sets the lock the desktop app would; the artist's app shows Sam's name. A push from the terminal appears in Activity as a snapshot by Sam with a thumbnail.

### 6.3 CI files the issue
A webhook on `ref.updated` triggers CI; a texture over budget results in *#88 "Hero_diffuse.png is 8K, budget is 4K"*, pinned to the file at that snapshot, assigned to its author. Sam never has to be the person who says it.

---

## 7. Lena, illustrator and freelancer (P2)

**Jobs:** her own history without a team price · deliveries that don't expire · proof when an invoice is questioned · working inside clients' systems when they have one.

### 7.1 A one-person org
Lena signs up; the org is just her. Storage-based pricing means her three clients as guests cost nothing. Projects per client. The desktop client on her one machine; the daily loop is 1.1.

### 7.2 Delivering
Instead of a WeTransfer link that dies in three days (RESEARCH §4), she publishes a release (3.3) with visibility *link* and an expiry she chooses. The client opens it on a phone, downloads, approves (4.2).

### 7.3 Proof for the invoice
The approval record on the release (5.2), attached to the invoice. When the client says "we asked for two rounds, not four", the issues under each milestone show who asked for what and when.

### 7.4 Being a guest somewhere else
An agency client runs GitDAM. Lena is added as a *guest* (or *editor* on one folder) on their project; she sees the simple projection and delivers into it. Her own org and theirs stay separate; the same login works for both.

---

## 8. Marcus, IT, security and procurement (P2, gatekeeper)

**Jobs:** say yes without regret · access ends when people leave · prove who did what · get the data out.

### 8.1 Identity — NEW (SSO/SCIM)
Org settings → **Identity**: connect SAML or OIDC; users sign in with the company IdP; SCIM provisions and deprovisions members so offboarding (5.3) happens from HR, not from a GitDAM admin remembering. Not in Phases 0–3; added to Phase 5 (§14).

### 8.2 Audit
Org settings → **Audit**: every owner-level action (force unlock, protected-ref override, member removal, release deletion) with actor, time and reason; every release approval; PAT creation and use. Exportable as CSV. Backed by the append-only Activity and IssueEvent records (DESIGN §2.9, §2.7).

### 8.3 Leaving — NEW (org export)
Org settings → **Export**. Produces, per project: a Git bundle (the complete history via the bridge), a zip of the current main line, and a JSON export of issues, comments, reviews, releases and metadata. The Git bundle is the guarantee: the history is a repository any Git client can read. This is the answer to the EU Data Act "walled garden" critique (RESEARCH §2), and to Marcus's vendor-viability question.

### 8.4 Where the data lives
The org's region is chosen at creation and everything stays there (DESIGN §12). The security questionnaire answers come from DESIGN §12 verbatim.

---

## 9. Ana, photographer and retoucher (P2)

**Jobs:** ingest a shoot without a browser · mark selects · never corrupt the catalog · deliver finals.

### 9.1 Ingest — NEW at this volume
Ana copies 3,000 RAWs from cards into `footage/2026-09-24-northwind/` inside the synced folder. The desktop client hashes and uploads in the background at 4 parallel streams, dedups the ones already uploaded from the backup card, and auto-snapshots *"Ingest: 3,000 files"* when the folder is quiet. RAW previews render at low priority (DESIGN §7). This exercises tree sharding (DESIGN §2.2) and the preview backlog; it is why Ana is P2.

### 9.2 Selects
Selects are a **collection** (a saved set, §11.2), not a folder move, so paths stay stable for Lightroom. Theo browses the collection, stars his picks; stars are tags on the asset index, unversioned.

### 9.3 The catalog
`.lrcat` requires check-out. Ana's two machines can't both have it open; the second one gets read-only with the banner (2.2). This is the Dropbox failure mode ("conflicted copies of the same catalog… corrupted catalogs that cannot be repaired", RESEARCH §3) replaced by an explicit rule.

### 9.4 Delivering finals
Retouched exports to `/exports`; release (3.3); Dana or Devon approves.

---

## 10. Devon, marketing operations at the brand (P3)

**Jobs:** one library of approved assets that populates itself · agencies deliver into it, not to inboxes · usage rights attached · never pay for a DAM nobody uses.

### 10.1 Receiving a release — NEW (cross-org delivery)
Northwind runs its own GitDAM org. Fieldwork's project *Northwind Spring Campaign* has a **Deliver to** setting pointing at Northwind's project *Brand Library / Campaigns / Spring 2026*. When Theo publishes Release *Round 3 (final)*, the release's files are written into Northwind's project as a snapshot by *Fieldwork Studio via release Round 3* [import commit], with the approval record attached. Devon's library fills itself with approved work; nothing is uploaded by hand; the agency's sources never cross over.

This is the wedge into brands: they receive before they buy.

### 10.2 The approved library
Northwind's main line *is* the approved set. Jamal (11.1) searches it. Rights live in the reserved `rights` metadata (licence, expiry, territories, credit), edited by Devon on the asset index, and shown on the asset and on release pages. Expiring rights appear on the board as issues, automatically, 30 days ahead.

### 10.3 Why P3
Brand portals, templating and channel publishing are a different product. 10.1 and 10.2 are enough to make GitDAM the place agency work lands; the rest waits for demand.

---

## 11. Jamal, internal consumer (P3)

**Jobs:** the approved logo in thirty seconds · never use the old one by mistake.

### 11.1 Finding it
Search box: file names, paths, tags, automatic metadata (dimensions, colour mode, duration, dominant colours), issue and snapshot text. Results grouped *Assets · Issues · Snapshots · Releases*. Filters: type, tag, changed since, in release, has open issues. Search covers the main line by default; *include history* answers "the version with the orange headline", which no other DAM can.

### 11.2 Collections
Saved searches or hand-picked sets across projects (*All Northwind logos*). Also used for Ana's selects (9.2). A collection can be shared as a page like a release, read-only.

### 11.3 Never the old one
Anything Jamal can reach is on the main line of an approved library or in a release; superseded versions are only in history, which guests and consumers don't browse. If he downloads from a release, the file name is unchanged and the release name is in the download's folder name.

---

## 12. Setting up (shared)

Referenced by 5.1 and every persona's first day.

- **Org**: name, plan, region, admins.
- **Project from template**: *Brand & Print* (PSD/AI/INDD check-out, PNG/PDF client-visible), *Video* (`.prproj`/`.aep`/`.lrcat` check-out, proxies on), *Game Art* (locks on `.blend`/FBX, Git access on), *Blank*.
- **Members** per project: owner / editor / reviewer / guest. **Client-visible paths** default `exports/`.
- **Desktop client**: sign in, pick project, pick a folder, *Sync everything* or *Choose folders*. Ordinary files in an ordinary folder.

---

## 13. What "done" looks like for the first customer

A 10–20 person agency, three concurrent client projects, one video editor, one photographer on contract. Week one:

1. Rachel and Theo set up the org and projects in under 30 minutes (5.1, 12).
2. Maya and Priya are on the desktop client by day two; drafts and auto-snapshots appear in Activity (1.1, 3.4).
3. Priya's project file shows a lock with her name (2.2). This is the moment the editor relaxes.
4. The first client round goes out as a release and comes back as pinned feedback on the board (3.3, 4.1, 3.2).
5. Someone restores a ruined file from History (1.2). This is the moment they decide to keep paying.

Second month: explorations and reviews (1.3, 3.1), protected folders, an approval record used in anger (5.2). Third month: Git access for a studio client (6), cross-org delivery to a brand (10.1).

---

## 14. Traceability: jobs → workflows → roadmap

| Persona | Job | Workflow | Roadmap phase | Status |
|---|---|---|---|---|
| Maya | Work without changing habits | 1.1 | 2 (desktop client) | covered |
| Maya | Go back | 1.2 | 1 | covered |
| Maya | Try a direction safely | 1.3 | 1 | covered |
| Maya | Not collide | 1.4 | 1 | covered |
| Maya | Feedback on the pixel | 1.5, 3.1, 4.1 | 2–3 | covered |
| Maya | Which file did the client see | 1.6, 3.3 | 3 | covered; *"In releases"* badge on assets is a small addition |
| Priya | Never be overwritten | 2.2 | 1 | covered; **lock handoff** is a small addition |
| Priya | Survive a corrupt project | 2.3 | 1–2 | covered by auto-snapshot |
| Priya | Timecode notes on the right cut | 2.5 | 2 | covered |
| Priya | Keep media linked | 2.1 | 2 | covered by path-stability rule |
| Priya | Move 60 GB unattended | 2.4 | 2 | covered |
| Theo | See everything | 3.4 | 1–2 | covered |
| Theo | Approve with a record | 3.1, 3.3 | 3 | covered |
| Theo | Run the client round | 3.2 | 3 | covered |
| Dana | Feedback, approve, download, on a phone | 4.1, 4.2 | 3 | covered; **Approve button on release page** is explicit now |
| Rachel | Set up fast | 5.1, 12 | 1 | covered |
| Rachel | Win the dispute | 5.2 | 3 | covered (approval record PDF) |
| Rachel | Keep work when people leave | 5.3 | 3 | **NEW: member offboarding flow** (reassign locks/issues/reviews, revoke PATs) |
| Rachel | Fewer bills | 5.4 | — | positioning |
| Rachel | Know the cost first | 5.5 | 3 | **NEW: usage view with overage shown ahead** |
| Sam | `git clone`, locks, CI | 6.1–6.3 | 5 | covered |
| Lena | One-person org, free guests | 7.1 | 1 | covered by pricing principles |
| Lena | Deliveries that don't expire | 7.2 | 3 | covered (release with *link* visibility and chosen expiry) |
| Lena | Invoice proof | 7.3 | 3 | covered |
| Lena | Guest in another org with the same login | 7.4 | 1 | covered by tenancy model; confirm one identity across orgs |
| Marcus | SSO/SCIM | 8.1 | 5 | **NEW: not previously planned** |
| Marcus | Audit | 8.2 | 3 | covered by Activity/IssueEvent; **CSV export** is a small addition |
| Marcus | Get the data out | 8.3 | 5 | **NEW: org export (Git bundle + zip + JSON)** |
| Ana | Ingest thousands of files | 9.1 | 2 | covered in design; needs tree sharding built, not deferred |
| Ana | Selects | 9.2, 11.2 | 3 | covered by collections |
| Ana | Catalog single-writer | 9.3 | 1 | covered by locks |
| Devon | Receive agency work | 10.1 | 3 | **NEW: cross-org release delivery** |
| Devon | Rights on assets | 10.2 | 5 | reserved in model; **rights expiry → issue** is new |
| Jamal | Find the approved asset | 11.1 | 3 | covered (OpenSearch moved to Phase 3) |
| Jamal | Collections | 11.2 | 3 | covered |

Five things the personas needed that the product didn't have: **member offboarding**, **usage/cost view**, **SSO/SCIM**, **org export**, **cross-org release delivery**. All five are now in the roadmap (VISION.md) and the first and last have design notes in DESIGN.md.
