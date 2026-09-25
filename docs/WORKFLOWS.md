# GitDAM Workflows

End-to-end journeys through the product as described in [VISION.md](./VISION.md). Each one is written from the user's seat, naming the screens and what they see, so the technical design in [DESIGN.md](./DESIGN.md) has something concrete to serve. Git terms appear in brackets the first time for orientation; the user never sees them.

Cast, used throughout:

- **Maya**: brand designer at a 12-person agency. Photoshop and Illustrator. Has never used a terminal.
- **Theo**: creative director at the same agency. Reviews, approves, talks to clients.
- **Priya**: video editor. Premiere. 30–80 GB projects.
- **Dana**: marketing manager at the client, Northwind. Has a login but only for the Northwind project.
- **Sam**: technical artist at a game studio that also uses GitDAM. Lives in Git.

---

## 1. Setting up

**Theo creates the organization.** Signs up, names it "Fieldwork Studio", invites the team by email. Each invite carries an org role: *admin* (Theo), *member* (Maya, Priya), or nothing yet (client guests are added per project, not per org).

**Theo creates a project** [repository]: "Northwind Spring Campaign". Chooses a template: *Brand & Print*, *Video*, *Game Art*, *Blank*. The template sets project settings the user never needs to see as settings:

- Which file types get previews and how (PSD flattened server-side; MP4 proxied).
- Which file types require **check-out before editing** [LFS lock]. Video and PSD default to yes. PNG exports default to no.
- Folder skeleton (`/source`, `/exports`, `/references`) if wanted.

He adds Maya and Priya as *editors*, and Dana as a *guest*. Guests see the project's **Board**, **Releases**, and any folder marked *client-visible* (default: `/exports`). They never see `/source`.

**Maya installs the desktop app.** Signs in, picks "Northwind Spring Campaign", picks a local folder. The app offers *Sync everything (2.1 GB)* or *Choose folders*. She takes everything. A minute later there is a normal folder on her Mac with a small GitDAM badge on each file. Finder, Photoshop and Illustrator see ordinary files.

---

## 2. Maya's daily loop: work, snapshot, move on

This is the loop the product lives or dies on. It must be less friction than "Save As… v3".

1. Maya opens `source/hero-poster.psd` in Photoshop and works for two hours, saving normally (Cmd-S) many times.
2. The desktop app notices each save. In the tray and in the web app, `hero-poster.psd` shows as **Draft: changed 2 min ago** [modified in working tree]. Nothing has been uploaded to history yet, but the app has quietly uploaded the bytes in the background so the eventual snapshot is instant [blob pushed, no commit].
3. At a good stopping point she clicks the tray icon. It shows **3 changed files** with thumbnails. She types a message: *"Hero poster: swapped to the teal palette, new headline."* and clicks **Snapshot** [commit].
4. Ten seconds later Theo's web app shows the new snapshot in the project's **Activity** feed with before/after thumbnails.

What she never had to do: name a file, pick a version number, upload anything, or decide where it goes.

**Variations on the loop:**

- *Auto-snapshot.* Project setting. If on, the app snapshots every N minutes of quiet with the message "Auto-snapshot", and Maya's explicit snapshots become **milestones** that history shows by default (auto-snapshots collapse under a "12 auto-snapshots" row). See the open question in VISION.md; the design supports both.
- *"I forgot to snapshot for three days."* Fine. Drafts accumulate; one snapshot captures all of them. The **History** view will show one big snapshot, which is worse than several small ones but strictly better than nothing.
- *Working offline.* Everything above works with no network. Snapshots queue and upload when back online, in order.

---

## 3. Trying a direction without breaking the main line

Theo asks Maya for "a bolder version of the hero poster, but keep the current one alive for the client call Thursday."

1. In the desktop app or the web app, Maya opens the project menu and clicks **Start an exploration** [create branch]. Names it *"bold-hero"*. Chooses *Start from: Main line, as of now* [branch from HEAD of main].
2. The desktop app asks: *Switch this folder to the exploration?* She says yes. Files that differ between main and the exploration are swapped on disk (at this moment: none). Her folder's badge now reads **bold-hero**.
3. She works and snapshots as in §2. Snapshots go to *bold-hero*; main is untouched. Theo can still open the main-line poster for the client call.
4. Thursday: the client picks bold. Maya clicks **Bring into main line** [merge]. Since only *bold-hero* changed `hero-poster.psd`, it merges cleanly. Main now has the bold version, history shows both lines converging, and the exploration is archived.

**If both lines had changed the same file** (Theo tweaked the main-line poster on Wednesday), the merge screen shows the file with **Choose a version**: two thumbnails, *Keep main line* / *Use bold-hero* / *Upload a combined file*. There is no attempt to merge pixels. She picks one, adds a note, done. In practice, a project with **check-out required** for PSDs makes this rare: Theo would have been told Maya holds the file.

**Alternative for smaller decisions:** explorations are cheap, but for "try one thing" Maya can just work, snapshot, and if it's wrong, **Restore** (see §7). Explorations are for work that must coexist with the main line for more than a day.

---

## 4. Review and approval

Fieldwork's rule: nothing in `/exports` goes to the client without Theo's approval.

1. Maya finishes on *bold-hero* and clicks **Request review** [pull request]. Target: main line. Title auto-filled from the exploration name; she adds a description. She can attach it to a request from the Board (§5): *Resolves #17 "Bolder hero poster"*.
2. Theo gets a notification. The **Review** screen shows:
   - the list of changed files, each with a **Compare** button;
   - **Compare** for an image: side-by-side, wipe slider, onion-skin, and *difference* (pixels that changed, highlighted) [diff];
   - for a video: two proxies with a linked scrubber;
   - for a PDF: page by page.
3. Theo drops a pin on the poster at the headline and writes *"kerning on 'Spring' is tight"* [review comment on a region]. He clicks **Request changes**.
4. Maya fixes it, snapshots to *bold-hero*. The review updates automatically; the pinned comment shows *resolved in snapshot "Fix kerning"* with a before/after under the pin.
5. Theo clicks **Approve and bring into main line**. Issue #17 moves to *Done*. The merge appears in Activity with both names on it.

Reviews are optional per project. A solo illustrator's project has none. An agency's client-facing folders can be **protected**: changes to `/exports` on main line only arrive through an approved review [protected branch].

---

## 5. The client's feedback becomes tracked work

Dana at Northwind has a guest login.

1. Theo publishes **Release: Round 2** (§6). Dana gets an email with a link. She sees a clean page: the release title, notes, a gallery of the exported assets, and a **Download all** button. No history, no sources, no jargon.
2. She clicks the hero poster, drops a pin on the logo, and writes *"Legal says the ® has to be visible at this size."* She clicks **Send feedback**. That creates issue #23, kind *Feedback*, pinned to `exports/hero-poster.png` at Release Round 2, with the region she marked.
3. Theo sees #23 on the **Board** in the *New* column. He triages: adds the label *legal*, assigns Maya, drags it to *To do*, sets milestone *Round 3*.
4. Maya, in the desktop app, sees *Assigned to you: #23*. She clicks it, the app opens the pinned asset at the pinned version so she can see exactly what Dana meant, and offers **Open source file** (the PSD that produced this export, tracked by the app when she exported it, or matched by name).
5. She fixes it, exports, snapshots with message *"Enlarge ® on hero poster. Fixes #23"*. The issue moves to *In review* (because the project requires review for `/exports`) and then to *Done* when Theo approves.
6. Dana gets a notification: *Your feedback #23 was addressed in Release Round 3*, with a before/after. She never learned what a snapshot is.

**What the Board is.** Columns are issue states: *New → To do → In progress → In review → Done*. Cards show the thumbnail of the pinned asset, so a board full of creative work looks like creative work, not a spreadsheet. Filters: milestone, assignee, label, kind. Swimlanes optional by milestone. Guests see a simplified board (their own feedback and anything labeled *client-visible*).

**Other ways issues get created.**

- Theo plans a round: creates issues from a template (*Round 3: hero poster, three social crops, email header*), all under milestone *Round 3*.
- Priya, while editing, hits a problem with a source file and files a *Bug* against it from the desktop app, pinned to the file at the current snapshot.
- Email-in: `northwind-spring@fieldwork.gitdam.app` creates issues from client emails, attachments become pinned assets. (Later phase.)

---

## 6. Shipping: releases and deliverables

1. On the Board, milestone *Round 3* shows *7 of 7 done*. Theo clicks **Close milestone and create release**.
2. Release screen: title *Round 3*, notes drafted from the closed issues (*"Enlarged ® on hero poster (#23). Added Instagram story crop (#25)…"*), editable. Scope: *client-visible folders only* (default for a client release) or *whole project*.
3. **Publish.** GitDAM stamps the current main line [tag], builds a zip in the background, and makes a share page. Theo copies the link into an email or lets GitDAM notify the project's guests.
4. Six months later someone asks "what did we send in Round 3?" The release is immutable and still downloadable, byte-for-byte what shipped, no matter what happened to main line since.

Releases can be *internal* (visible to members only) for milestones like *Print-ready* or *Handoff to dev*.

---

## 7. Mistakes and recovery

The reason to have history at all. Each of these is one screen and a confirmation.

- **"I ruined the file."** Maya opens **History** for `hero-poster.psd`, sees a filmstrip of every snapshot with thumbnails, picks Tuesday's, clicks **Restore this version**. It becomes a new snapshot on main line (*"Restore hero-poster.psd to snapshot from Tue 14:02"*). Nothing is deleted; Wednesday's version is still in history if she was wrong about being wrong.
- **"I deleted a folder."** Project **History**, pick the snapshot before the deletion, **Restore folder**.
- **"Who changed the logo and why?"** Open the file, **History**: each entry has an author, a time, a message, and the linked issue or review if there was one [blame/log].
- **"We need the project as it was for the Round 2 release."** Releases → Round 2 → **Browse files** (read-only) or **Open as exploration** to work from it [checkout tag into a branch].
- **"Two people edited the same PSD."** With check-out required, impossible: the second person's Photoshop opens the file read-only with a banner *"Checked out by Priya since 10:15. Ask for it?"* (asks Priya to release the lock; she can hand it over without leaving Premiere via the tray). Without check-out required, both snapshot, and the second snapshot shows **Choose a version** exactly as in §3. Nothing is lost either way; the un-chosen version stays in history.

---

## 8. Priya and 60 GB of video

Video stresses everything: size, lock discipline, and what "preview" means.

1. Priya syncs the project with **Choose folders**: `/footage` as *placeholders* (she has it on a RAID already and will point Premiere there), `/project-files` and `/exports` fully. Placeholders show in Finder with size and a cloud badge; double-clicking one downloads it.
2. She opens `project-files/northwind-30s.prproj`. The project requires check-out for `.prproj`, so the desktop app takes the lock automatically on first write. Theo's web app shows a lock icon with her name on the file.
3. She works for the day, saving normally. The app uploads the changed project file in the background (small). The 4 GB render she exports to `/exports` uploads in parallel multipart chunks; she sees progress in the tray and can keep working.
4. End of day: snapshot *"Rough cut v1, 30s."* The lock is released on snapshot by default (project setting; can be *keep until I release it*).
5. Theo reviews: the export gets a 720p proxy generated server-side, so his laptop on hotel Wi-Fi scrubs it fine. He drops a comment at **00:12:04** *"cut is late here"*. The comment is a pin in time, shown on the scrubber.
6. Dana approves Round 1 of the video from the release page on her phone, watching the proxy.

Storage note for Priya's project: the 4 GB render exists once, however many snapshots or releases reference it. Re-exporting a render with one changed frame does create a new 4 GB blob (no chunk-level dedup; see DESIGN.md for why that's a later optimization).

---

## 9. Sam and the build pipeline

Sam's studio keeps game art in GitDAM because the artists like it, but the build server wants Git.

1. Project settings → **Git access** shows a URL: `https://git.gitdam.app/oakline/dungeon-art.git`, and a button to mint a personal access token.
2. `git clone` works. The clone contains LFS pointer files and `.gitattributes`; `git lfs pull` fetches the binaries via the same content store the artists use. The build server clones with `GIT_LFS_SKIP_SMUDGE=1` and pulls only the paths it needs.
3. Sam pushes a commit from the terminal that adds a new material. It appears in the web app as a snapshot by Sam, with a thumbnail, in Activity. The artists never know it came from Git.
4. `git lfs lock Characters/Hero.blend` sets the same lock the desktop app would. Both sides see it.
5. The studio's CI runs on every snapshot to main line (webhook), validates texture sizes, and files an issue if something is over budget: *#88 "Hero_diffuse.png is 8K, budget is 4K"*, pinned to the file, assigned to the snapshot's author.

---

## 10. Search and finding things

The DAM part of "Git DAM".

- **Search box** everywhere: file names, paths, tags, metadata, issue titles and bodies, snapshot messages, comment text. Results grouped: *Assets · Issues · Snapshots · Releases*.
- **Filters** in the project browser: type, tag, last changed by, changed since, has open issues, checked out by.
- **Tags** are free-form on assets, plus automatic ones from the preview pipeline: dimensions, color mode, duration, codec, dominant colors, and (later) AI descriptions ("outdoor, two people, teal palette").
- **Collections**: saved searches or hand-picked sets that cross projects (*"All Northwind logos"*), for the marketing-ops persona.

Search covers the *current* main line by default. A toggle searches history (*"find the version of the poster that had the orange headline"*), which is the query no other DAM can answer.

---

## 11. What "done" looks like for the first customer

A 10–20 person agency, three concurrent client projects, one video editor. In week one they should be able to:

1. Create the org, projects and invite everyone (§1) in under 30 minutes without documentation.
2. Have every designer on the desktop app, working in their normal tools, with drafts showing up in the web app (§2) by day two.
3. Send a client a release page and receive pinned feedback as issues (§5, §6) in the first client round.
4. Recover at least one "I ruined the file" moment from History (§7). This is the moment they decide to keep paying.

Explorations, reviews, protected folders and Git access (§3, §4, §9) are the second-month features that stop them from leaving once they've grown into them.
