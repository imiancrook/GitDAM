# GitDAM Vision: Git-Style Asset Management for Creative Teams

## The idea in one paragraph

Software teams have had version control for decades. They can try an idea on a branch, throw it away without consequence, see exactly who changed what and when, roll back a bad change in seconds, review each other's work before it lands, and ship from a tagged, reproducible state. Creative teams get none of this. They get `logo_final_v3_FINAL_revised.psd`, Dropbox conflicts, "which one is the approved one?", and a Slack thread as the only record of why a change was made. GitDAM gives designers, illustrators, video editors, photographers and motion artists the benefits of Git without asking them to learn Git. It looks like a DAM. It behaves like a repository.

## Who it's for

| Persona | Pain today | What GitDAM gives them |
|---|---|---|
| **Brand / graphic designer** | Dozens of "final" files; no idea which one the client approved | One asset, one history, one approved version per release |
| **Illustrator / concept artist** | Wants to explore a direction without wrecking the main file | Branch ("explore"), compare visually, keep or discard |
| **Video / motion editor** | 40 GB project folders, no history, no safe rollback | Large-file storage that scales, snapshot before every risky edit |
| **Art director / creative lead** | Reviews happen in email and screenshots; approvals are untracked | Review requests with annotations, explicit approve/merge, audit trail |
| **Marketing ops** | "Send me the current assets" turns into a scavenger hunt | Releases: a tagged, immutable bundle of what shipped |
| **Technical artist / developer** | Wants assets in the same pipeline as code | Real Git LFS and Git protocol compatibility on the same repository |

The first three are the users. The fourth and fifth are the buyers.

## The core translation: Git concepts, creative vocabulary

The product principle: **every Git concept is present, none of the Git vocabulary is required.** Power users can use the Git terms and even a real `git` client; everyone else sees the creative-native words.

| Git concept | What the user sees | Why creatives want it |
|---|---|---|
| Repository | **Project** | A brand, a campaign, a film, a game |
| Commit | **Snapshot** (with a message) | "Save a version I can always come back to" |
| Working tree / staging | **Drafts** (unsaved-to-history changes) | Work locally, snapshot when it's a meaningful state |
| Branch | **Variation** / **Exploration** | Try a direction without touching the main line |
| Default branch (`main`) | **Main line** | The single source of truth |
| Merge | **Bring in** / **Adopt** | Accept an exploration into the main line |
| Merge conflict | **Choose a version** | Binaries don't 3-way merge; the user picks per file |
| Diff | **Visual compare** (side-by-side, wipe, onion-skin, difference blend) | See what actually changed in an image or frame |
| Blame / log | **History** ("who changed this and why") | Accountability and context |
| Revert / checkout old version | **Restore** | Undo a bad change in one click, non-destructively |
| Tag | **Release** / **Deliverable** | "This is exactly what shipped to the client on the 14th" |
| Pull request | **Review request** | Structured approval with annotations, instead of email |
| LFS lock | **Check out for editing** | Prevent two people from editing an un-mergeable file at once |
| `.gitignore` / `.gitattributes` | Project settings | Which file types are previewed, locked-by-default, etc. |
| Clone / pull / push | **Sync** (desktop app) or **Open in Photoshop** | Files live where the tools expect them: on disk |

Two things a code-centric Git model gets wrong for creatives, and GitDAM must get right:

1. **Binary files don't merge.** Text merges line by line; a PSD does not. Every "merge" of a binary is really a *choice*: ours, theirs, or a new file the human produced by hand. The conflict UI is therefore simple (pick one) and locking is the primary collaboration tool, not merging.
2. **The file is not the artifact; the picture is.** Nobody reviews a hex dump. Previews, thumbnails, video proxies and visual diffs are core infrastructure, not polish.

## Architectural decision: Git's data model, not Git's binaries

The current codebase has a Git-*shaped* data model (`Repository`, `Asset`, `AssetVersion`, `LFSObject`) but no actual commit graph: `branch` and `commitSha` are free-text fields on an asset, and nothing produces or validates them. There are three ways forward.

| Option | Description | Verdict |
|---|---|---|
| **A. Real Git on the server** | Run libgit2 / `git` in Lambda or a container with a repo on EFS per project | Faithful, but heavy: cold starts, EFS cost, packfile management, and Git's tree model isn't needed since every real file is an LFS pointer anyway |
| **B. Flat versioning (current)** | Per-asset version list, branch as a label | Simple, but can't express "the project as it was on Tuesday", can't branch a project, can't tag a release atomically |
| **C. Git's object model, implemented natively** | Blobs in S3 (content-addressed, already done), commits/trees/refs as records in DynamoDB via AppSync | **Recommended.** Gets branches, history, tags, merges and atomic snapshots cheaply; exposes Git LFS and Git smart-HTTP later as a *compatibility layer* over the same data |

Option C is what large-binary version control systems (Perforce, Plastic SCM, Diversion) converge on: content-addressed blobs, a commit graph, and refs. Trees are cheap because they only hold pointers; a snapshot of a 40 GB project costs a few kilobytes of metadata when only one file changed. The S3 layout already in place (`lfs-objects/ab/cd/<oid>`) is exactly a Git LFS object store, so the blob layer is done.

### Data model (target)

Everything below the line is what exists today, reshaped; above the line is new.

```
Project (was Repository)
  id, name, description, defaultBranch, settings (json), orgId

Ref                          # branches and tags
  projectId, name, kind: branch|tag, commitId, protected: bool
  # e.g. ("main", branch), ("release/2025-09-spring-campaign", tag)

Commit                       # a snapshot
  id, projectId, treeId, parentIds[], authorId, message, createdAt
  # parentIds has two entries for a merge commit

Tree                         # a folder listing at one point in time
  id (hash of entries), projectId
  entries: [{ path, kind: file|dir, oid | treeId, size, mode }]
  # stored as one JSON document per tree; large trees can be split by directory

Blob (was LFSObject)         # the bytes
  oid (sha256), size, storageKey, verified, uploadedBy, createdAt
  # shared across projects: identical files are stored once

Asset (view over Tree entries, was Asset)
  projectId, path, latestBlobOid, mimeType, tags[], metadata (json),
  previewKeys (json: thumb, medium, proxyVideo, pages[])
  # denormalized "current state of main" for fast browsing and search;
  # rebuilt from Tree whenever main moves

Lock
  projectId, path, ownerId, createdAt, expiresAt
  # maps 1:1 to the Git LFS File Locking API

Comment
  projectId, target: { commitId | reviewId | path@commitId }, region (json: x,y,w,h or timecode),
  authorId, body, resolved, createdAt

ReviewRequest (pull request)
  projectId, sourceRef, targetRef, title, description, state: open|approved|merged|closed,
  reviewers[], mergeCommitId

Release (a tag with metadata)
  projectId, refName, commitId, title, notes, publishedAt, bundleKey (zip in S3)
```

### How the core operations work

- **Upload / save a snapshot.** Client hashes the file (SHA-256, already implemented in `lib/api/asset-api.ts`), asks the batch API for an upload URL, PUTs to S3, then calls `createCommit(branch, [{path, oid, size}], message)`. The server loads the branch head's tree, applies the change, writes the new tree, writes the commit, advances the ref with an optimistic-concurrency check (`expectedCommitId`), and enqueues preview generation.
- **Branch / explore.** `createRef(name, kind=branch, commitId=head of main)`. Zero copy.
- **Restore.** Create a new commit on the branch whose tree points the path back at the old oid. History is never rewritten.
- **Compare.** Two commits → two trees → diff of entries (added / removed / changed by oid). For changed images, the UI fetches both previews and renders wipe / onion-skin / pixel-difference client-side. Video: side-by-side proxies with linked scrub.
- **Review & merge.** Open a review request from an exploration to main. Compute the 3-way diff (merge base via lowest common ancestor on `parentIds`). Paths changed on only one side merge automatically; paths changed on both are conflicts and the UI asks the reviewer to choose. Approval writes a merge commit with two parents and moves `main`.
- **Lock / check out.** `Lock` records with a TTL; the UI shows who holds each file; the desktop client sets files read-only when locked by someone else. Same semantics as the Git LFS lock API, so `git lfs lock` works against it too.
- **Release.** Tag ref + a background job that zips the tree into `releases/{projectId}/{tag}.zip` for one-click download by people who will never log in.

## Product surface

### 1. Web app (exists in skeleton form)
- Project browser with grid/list, folder navigation, previews, tag and metadata search.
- History panel per asset and per project, with restore.
- Visual compare.
- Review requests with pinned annotations (region on an image, timecode on video, page on a PDF).
- Locks, releases, project settings, team roles.

### 2. Desktop sync client (new, highest-leverage addition)
Creatives work in Photoshop, Illustrator, Premiere, Blender, Figma-exported files, on local disk. A tray app that:
- Syncs a project (or a subfolder) to a local folder, like Dropbox.
- Watches for changes and shows them as **drafts**; the user writes a message and snapshots (or auto-snapshots on a schedule if they prefer).
- Takes a lock automatically when a file is opened for writing, if the project requires it.
- Downloads only the files the user needs (sparse checkout), with the rest as placeholders, because a 200 GB project cannot live on every laptop.

This is what makes the "no Git vocabulary" promise real. Upload forms are a stopgap.

### 3. Creative-tool plugins (later)
- Adobe UXP panel (Photoshop, Illustrator, Premiere, After Effects): snapshot, history, lock, compare, from inside the app.
- Figma plugin: push exports as snapshots.
- Blender / Unity / Unreal: these ecosystems already speak Git LFS; the compatibility layer covers them.

### 4. Git compatibility layer (for technical users and pipelines)
- Git LFS Batch API and File Locking API with Cognito-issued tokens, on `https://<project>.gitdam.app/<org>/<project>.git/info/lfs`.
- Git smart-HTTP (`git clone`, `fetch`, `push`) served by translating packfiles to and from the native commit/tree model. Trees contain only LFS pointer files and small text (`.gitattributes`, READMEs), so packfiles stay small.
- This lets a game studio's build server `git clone` the art repo while the artists never see a terminal.

### 5. Previews and derived media (infrastructure)
- Images: Sharp in Lambda for JPEG/PNG/WebP/TIFF; ImageMagick layer for PSD/AI/EPS flattening; SVG rasterized.
- Video: MediaConvert to a low-bitrate proxy plus a poster frame; timecode-addressable.
- Documents: PDF page rasterization.
- 3D: glTF preview via a headless renderer, later.
- Everything keyed by blob oid, so previews are generated once regardless of how many projects, branches or paths reference the blob.

## Roadmap

### Phase 0: Make the current code work (weeks)
The prototype has good bones but isn't runnable end to end.
- Expose the three Lambdas through an HTTP API in `amplify/backend.ts` (API Gateway HTTP API with Cognito JWT authorizer). Right now `lib/git-lfs/lfs-client.ts` calls an endpoint that doesn't exist.
- Tighten authorization: `a.allow.authenticated().to(['read'])` on every model means every signed-in user can read every project. Replace with per-project membership (owner / editor / viewer) via groups or a `ProjectMember` table.
- Pin `aws-amplify` and `@aws-amplify/backend` to real versions instead of `latest` / `beta`, remove the `data-schema-types` webpack stub if the pinned versions no longer need it, and turn TypeScript and ESLint errors back on in `next.config.js`.
- Add a test harness (Vitest) and cover the LFS pointer parse/create and OID calculation that already exist.

### Phase 1: The commit graph (1–2 months)
- Add `Ref`, `Commit`, `Tree`, `Blob`, `Lock` models; migrate `Repository → Project`, `LFSObject → Blob`.
- `createCommit`, `createRef`, `getTree`, `diffCommits` as AppSync custom mutations/queries backed by Lambda (these need transactional ref updates, which the auto-generated CRUD can't do).
- Every upload becomes a commit. History and restore in the UI.
- Branch creation and switching in the UI ("Start an exploration").
- Locks in the UI.

### Phase 2: Seeing the work (1–2 months)
- Preview pipeline (S3 event → Lambda → previews keyed by oid).
- Grid view with real thumbnails; hover-scrub for video.
- Visual compare for images and video.
- Comments with regions and timecodes.

### Phase 3: Collaboration (1–2 months)
- Review requests, approvals, 3-way merge with pick-one conflict resolution.
- Releases with zip bundles and public share links (signed, expiring).
- Teams, roles, activity feed.
- Notifications (email, Slack).

### Phase 4: Living on the desktop (2–3 months)
- Desktop sync client (Tauri or Electron; Rust core is worth it for hashing and file watching at scale).
- Sparse sync, auto-lock on open, drafts → snapshot flow.
- Multipart upload for files over 5 GB; S3 Transfer Acceleration.

### Phase 5: Compatibility and scale
- Git LFS Batch + Locking API with proper auth (Phase 0 exposes it; this hardens it against the spec's conformance tests).
- Git smart-HTTP bridge.
- Adobe UXP panel.
- CloudFront in front of previews and release bundles.
- OpenSearch for full-text and metadata search; AI-generated tags and descriptions as a search aid.

## What we are explicitly not building

- **A general-purpose file sync product.** Dropbox exists. GitDAM's value is history, branching, review and releases; sync is a means to that.
- **Merge tools for binary formats.** Layer-level PSD merging is a research problem. Pick-one conflicts plus locking cover the real workflow.
- **A Git hosting service.** Git compatibility is a bridge for pipelines and technical users, not the product. If someone wants GitHub, they should use GitHub.

## Open questions

1. **Tenancy model.** Per-user projects (current) vs. organizations with teams. Organizations are the right answer for the buyer personas; decide before Phase 1 because it shapes every authorization rule.
2. **Snapshot granularity.** Should the desktop client auto-snapshot on every save (Google Docs style, with the user naming milestones), or only on explicit action (Git style)? Leaning toward auto-snapshot with explicit "milestones" surfaced in history; auto-snapshots can be squashed after 30 days.
3. **Storage economics.** Content-addressing deduplicates identical files, but creative workflows produce many *near*-identical large files. Versioned storage will be the dominant cost. Lifecycle to Glacier for blobs not referenced by any branch head or release after N days is the likely answer; the commit graph makes "is this reachable?" a cheap query.
4. **Where previews are rendered for proprietary formats.** Server-side PSD flattening is lossy for some features. The Adobe plugin could push a rendered preview at snapshot time instead. Probably both.
