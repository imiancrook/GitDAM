# GitDAM Technical Design

Companion to [VISION.md](./VISION.md) (what and why) and [WORKFLOWS.md](./WORKFLOWS.md) (what it feels like). This document is the how. It is written against the codebase as it stands (Amplify Gen2, Next.js 15, three Lambdas, four models) and says what changes.

Sections:

1. [Tenancy and permissions](#1-tenancy-and-permissions)
2. [Object model](#2-object-model)
3. [API surface](#3-api-surface)
4. [Core algorithms](#4-core-algorithms)
5. [State machines](#5-state-machines)
6. [Upload pipeline](#6-upload-pipeline)
7. [Preview pipeline](#7-preview-pipeline)
8. [Desktop client](#8-desktop-client)
9. [Git compatibility bridge](#9-git-compatibility-bridge)
10. [Search](#10-search)
11. [Storage economics and garbage collection](#11-storage-economics-and-garbage-collection)
12. [Security](#12-security)
13. [Observability](#13-observability)
14. [Phase 0 plan, file by file](#14-phase-0-plan-file-by-file)
15. [Phase 1 plan](#15-phase-1-plan)

---

## 1. Tenancy and permissions

### Decision: organizations from day one

VISION.md left this open. Resolving it: **organizations are the tenant**. Every project belongs to exactly one org. Personal use is an org with one member. Retrofitting orgs onto per-user ownership later would mean rewriting every authorization rule, so it goes first.

```
Organization   id, name, slug, plan, createdAt
OrgMember      orgId, userId, role: admin|member, invitedBy, joinedAt
Project        id, orgId, slug, name, ..., visibility: private|org
ProjectMember  projectId, userId, role: owner|editor|reviewer|guest, addedBy, addedAt
```

Effective role on a project = max(org role mapping, project role):

| Org role | Implied project role | Notes |
|---|---|---|
| admin | owner on every project | Can also delete the org, manage billing |
| member | editor on `visibility: org` projects, none on `private` | Explicit `ProjectMember` rows override |
| (none) | none | Guests exist only as `ProjectMember` rows with role `guest` |

Project roles and what they may do:

| Capability | guest | reviewer | editor | owner |
|---|---|---|---|---|
| Browse client-visible paths, releases, board (own + client-visible issues) | ✓ | ✓ | ✓ | ✓ |
| Browse all paths, history, explorations | | ✓ | ✓ | ✓ |
| File issues, comment | ✓ | ✓ | ✓ | ✓ |
| Triage issues (labels, assignee, state) | | ✓ | ✓ | ✓ |
| Snapshot, create explorations, lock | | | ✓ | ✓ |
| Approve reviews, merge into protected refs | | ✓ | ✓ | ✓ |
| Publish releases | | | ✓ | ✓ |
| Project settings, members, delete | | | | ✓ |

*Client-visible paths* are a project setting: a list of path prefixes (default `["exports/"]`). Guests are filtered at the tree level: any API that returns tree entries strips non-visible prefixes for guests, and blob download URLs are only issued for visible paths.

### How this is enforced in Amplify Gen2

The generated CRUD on `a.model()` cannot express "user is a member of the project this row belongs to". Two options were considered:

- **`allow.ownersDefinedIn('members')`** on every row: a denormalized member list on each Commit, Tree, Issue, etc. Fan-out on every membership change over every row. Rejected.
- **Cognito groups per project** (`proj_<id>_editor`, …) with `allow.groupsDefinedIn()`: Cognito caps groups per user pool at 10,000 and groups per user token at a much smaller number; tokens must be refreshed when membership changes. Workable for a while, fragile later. Rejected.

**Chosen: every read and write goes through custom operations with a membership-check resolver step.** In Amplify Gen2 terms:

- Models stay defined with `a.model()` for the schema and DynamoDB tables, but their authorization is restricted to a service group nobody is in (`allow.group('service')`), so generated CRUD is unusable from clients.
- All client-facing operations are `a.query()` / `a.mutation()` with `a.handler.custom()` **pipeline resolvers** (AppSync JavaScript resolvers). The first function in every pipeline is the same `authorize.js`: it loads `ProjectMember` for `(projectId, identity.sub)` and `OrgMember` for the org, computes the effective role, and rejects or stashes it in `ctx.stash.role`. Subsequent functions do the work.
- Operations that need transactions, S3, or non-trivial logic (`createCommit`, `mergeRefs`, `publishRelease`) use a Lambda handler behind the same authorize step (`a.handler.function()` after `a.handler.custom()` in the pipeline).

This is more code up front than generated CRUD, but it is the only shape that gives real per-project authorization, and it is also what the Git bridge and desktop client need: an API that speaks in operations, not rows.

The Amplify Gen2 API for pipeline resolvers and custom handlers has moved during its beta; verify the exact `a.handler` composition against current docs at implementation time. The design does not depend on any one spelling of it.

### Identity for non-browser clients

- **Desktop client:** Cognito OAuth with PKCE, refresh token stored in the OS keychain.
- **Git / LFS clients:** personal access tokens (`PAT` table: `hash, userId, scopes, expiresAt, lastUsedAt`) sent as HTTP basic auth. The Git bridge exchanges a PAT for a short-lived signed JWT that AppSync's Lambda authorizer accepts. Cognito tokens are not usable by `git` directly.
- **CI / webhooks:** the same PAT mechanism, with a `bot` user type that cannot log in interactively.

---

## 2. Object model

### 2.1 Blobs

Already the right shape. Keep it:

```
Blob   oid (sha256 hex, PK), size, storageKey, verified, uploadedBy, createdAt, refCount?
S3    lfs-objects/{oid[0:2]}/{oid[2:4]}/{oid}
```

- `oid` is the SHA-256 of the bytes. Identical files across every project and org share one blob and one S3 object. Cross-tenant sharing of *bytes* is safe because a blob is only reachable by someone who already has its hash, and the hash of a file is not a secret you can guess. (An attacker who knows a file's hash and wants to test whether someone uploaded it can, in principle, probe the batch API. Mitigation: `download` in the batch API only issues URLs for oids referenced by a tree the caller can read; see §6.)
- `verified` flips to true when the upload is confirmed (§6). Unverified blobs are garbage-collected after 24h.
- `refCount` is *not* maintained; reachability is computed (§11). A counter would need to be transactionally correct across commits, merges, and GC, and would be wrong the first time a Lambda timed out.

### 2.2 Trees

One `Tree` record **per directory**, as in Git, not one per snapshot. Reasons: DynamoDB items cap at 400 KB; a 20,000-file project as a single JSON document would exceed it, and every snapshot that touched one file would rewrite the whole document. Per-directory trees mean a snapshot that changes `source/hero-poster.psd` writes three small items: the new `source/` tree, the new root tree, the commit.

```
Tree
  id          sha256 of canonical serialization (PK)
  entries     [{ name, kind: "blob"|"tree", id, size?, mode? }]   sorted by name, bytewise
  entryCount, byteSize (recursive totals, for UI and quotas)
```

Canonical serialization: `kind + "\0" + name + "\0" + id + "\0" + size + "\n"` per entry, entries sorted by name as UTF-8 bytes, hashed with SHA-256. Content-addressing gives free deduplication of unchanged subtrees across snapshots and explorations, and makes `diff` of two trees a matter of comparing ids at each level.

Directories with more than ~2,000 entries (a `/footage` folder with 10,000 clips) would still exceed 400 KB. Handle with **entry sharding**: a tree whose canonical form exceeds 300 KB is stored as a `Tree` with `sharded: true` and `shards: [id…]`, each shard a `TreeShard` holding a contiguous name range. Reads reassemble. Implement in Phase 1 only if a real project hits it; the hashing scheme does not change.

Trees are immutable and global (not scoped to a project) because they are content-addressed. Access control is on refs and commits; possession of a tree id without a readable commit that reaches it is not a leak of anything but structure, and tree ids are unguessable.

### 2.3 Commits

```
Commit
  id          sha256 of canonical serialization (PK)
  projectId   (GSI: projectId, createdAt) for activity feeds
  treeId
  parentIds   [] (0 for root, 1 normal, 2 merge)
  authorId, authorName, authorEmail  (captured at commit time; users can be renamed later)
  message
  createdAt   ISO-8601 with milliseconds
  kind        "snapshot" | "auto" | "restore" | "merge" | "import"
  generation  max(parent.generation) + 1   (for merge-base search, §4.2)
  meta        { issueRefs: [23], resolves: [23], fromReviewId?, restoredFrom? }
```

Hashing the commit gives a stable, tamper-evident id and matches how Git thinks, which the bridge (§9) needs. `generation` is Git's generation number trick: it makes merge-base search bounded without walking to the root.

### 2.4 Refs

```
Ref
  projectId, name             (PK: projectId, SK: name)   e.g. "heads/main", "heads/bold-hero", "tags/round-3"
  commitId
  kind        branch | tag
  protected   bool            (only via approved review; owners can override with a reason)
  archived    bool, archivedAt
  createdBy, createdAt, updatedAt
```

Ref updates are the only mutable, contended write in the whole model. They use a DynamoDB conditional update: `SET commitId = :new IF commitId = :expected`. Every mutation that moves a ref takes `expectedCommitId` from the client; on failure the client refetches and retries (for the desktop client, this means re-basing its pending snapshot onto the new head, which for binaries is a tree-level operation, not a content merge; see §4.3).

### 2.5 Asset index

The `Asset` model in the current schema becomes a **derived index**, not a source of truth:

```
AssetIndex
  projectId, path            (PK, SK)
  refName                    which ref this row reflects (main by default; explorations indexed lazily)
  blobOid, size, mimeType, lastCommitId, lastChangedAt, lastAuthorId
  tags [], metadata {}, previewState, previewKeys {}
  lockedBy?, openIssueCount
```

Rebuilt incrementally by a stream consumer on `Ref` updates: diff old tree vs. new tree (§4.1), upsert changed paths, delete removed ones. Tags and metadata edits *do* live here as the source of truth (they are not versioned; versioning "tags" would confuse users and match nothing in their mental model), keyed by `(projectId, path)` and surviving snapshots. This table backs browsing, filtering, and search projection.

### 2.6 Locks

```
Lock   projectId, path (PK, SK), ownerId, ownerName, createdAt, expiresAt, clientId, note?
```

Maps 1:1 onto the Git LFS File Locking API (§9). `expiresAt` defaults to 7 days, refreshed by the desktop client while the file is open. Owners can force-unlock with a reason (recorded as an activity event).

### 2.7 Issues

```
Issue
  projectId, number           (PK, SK)   number from an atomic counter on Project
  id                          (GSI) stable across renumbering, used in links
  title, body (markdown), kind: request|feedback|task|bug
  state: new|todo|in_progress|in_review|done|closed, stateReason?
  authorId, assigneeIds[], labels[], milestoneId?, priority: none|low|medium|high|urgent
  clientVisible bool          (auto-true for issues by guests; editable)
  attachments [{ path, commitId, region?: {x,y,w,h} | {t} | {page}, previewKey? }]
  linkCounts { references, resolves }
  createdAt, updatedAt, closedAt

Milestone  projectId, id, title, description, dueDate?, state: open|closed, releaseId?, counts {open, done}
Label      projectId, name, color
IssueLink  issueId, targetKind: commit|review|issue, targetId, relation: references|resolves|blocks|duplicates, createdBy, createdAt
IssueEvent projectId, issueId, seq, kind: created|state|assign|label|milestone|link|comment, actorId, data, createdAt
```

`IssueEvent` is the timeline and the audit trail; the `Issue` row is the current projection. Comments on issues are `Comment` rows (below) with `target.issueId`, and produce an `IssueEvent` of kind `comment` so the timeline is one sorted list.

Region attachments are keyed to a `commitId`, never to "latest", so a pin stays on the pixels it was placed on even after the file changes. The UI shows "this pin was placed on an older version" with a jump to current.

### 2.8 Reviews, comments, releases

```
ReviewRequest
  projectId, number, id, title, body, sourceRef, targetRef, baseCommitId (merge base at open),
  state: open|changes_requested|approved|merged|closed, authorId, reviewerIds[],
  approvals [{ userId, commitId, at }]   (approval is tied to a source commit; new pushes invalidate unless project says otherwise)
  mergeCommitId?, createdAt, updatedAt

Comment
  projectId, id, target: { issueId } | { reviewId, path?, commitId?, region? } | { path, commitId, region },
  authorId, body, resolved, resolvedBy?, resolvedInCommitId?, createdAt, editedAt

Release
  projectId, id, tagName, commitId, title, notes, scope: all|clientVisible, visibility: internal|guests|link,
  bundleKey?, bundleState: pending|ready|failed, publishedBy, publishedAt, milestoneId?
```

### 2.9 Activity

```
Activity  projectId, ts (PK, SK), actorId, kind, subject {…}, summary
```

Written by every mutation, read by the feed and by notification fan-out. Cheap, append-only, TTL 2 years.

---

## 3. API surface

All operations are AppSync custom queries/mutations behind the authorize pipeline (§1). Grouped by concern. Types abbreviated.

**Projects and membership**
```
createOrganization(name)                             → Organization
createProject(orgId, name, template, settings?)      → Project
updateProjectSettings(projectId, patch)              → Project
addProjectMember(projectId, email | userId, role)    → ProjectMember   (sends invite if no user)
listProjects()                                       → [Project]       (filtered by membership)
```

**Blobs and trees**
```
batchObjects(projectId, operation: upload|download, objects: [{oid, size}])
    → [{ oid, size, actions: { upload?: {href, header, expiresAt}, verify?: {...}, download?: {...} }, error? }]
    # Git LFS Batch API semantics; also used by the web and desktop clients
verifyObject(projectId, oid, size)                   → Blob            (HEAD in S3, flip verified)
getTree(projectId, treeId | {refName, path})          → Tree            (guest-filtered)
getBlobUrl(projectId, oid, path)                      → { href, expiresAt }   (path required for guest visibility check)
```

**Commits and refs**
```
createCommit(projectId, refName, expectedCommitId, changes: [{path, op: put|delete, oid?, size?}], message, kind?)
    → { commit, ref }                                # single request; server builds trees
listCommits(projectId, refName | commitId, path?, limit, cursor)   → page of Commit
getCommit(projectId, commitId)                        → Commit
diffCommits(projectId, fromCommitId, toCommitId, pathPrefix?)      → [{ path, change: added|removed|modified|renamed, from?, to? }]
listRefs(projectId, kind?)                            → [Ref]
createRef(projectId, name, kind, fromCommitId)        → Ref
updateRef(projectId, name, expectedCommitId, commitId, reason?)    → Ref    (owner override for protected)
archiveRef(projectId, name)                           → Ref
restore(projectId, refName, expectedCommitId, paths: [{path, fromCommitId}], message?)   → Commit   (sugar over createCommit)
```

**Merge and review**
```
previewMerge(projectId, sourceRef, targetRef)         → { base, clean: [...], conflicts: [{path, ours, theirs}] }
mergeRefs(projectId, sourceRef, targetRef, expectedTargetCommitId, resolutions: [{path, choose: ours|theirs|oid}], message)
    → Commit
openReview(projectId, sourceRef, targetRef, title, body, resolvesIssues?) → ReviewRequest
reviewAction(projectId, reviewId, action: approve|request_changes|comment|close|merge, body?, resolutions?) → ReviewRequest
```

**Locks**
```
listLocks(projectId, path?)                           → [Lock]
createLock(projectId, path, expectedCommitId?)        → Lock            (409 with holder if held)
releaseLock(projectId, path, force?, reason?)         → Lock
refreshLock(projectId, path)                          → Lock
```

**Issues**
```
createIssue(projectId, title, body, kind, attachments?, labels?, assigneeIds?, milestoneId?)   → Issue
updateIssue(projectId, number, patch)                 → Issue           (state transitions validated, §5.1)
listIssues(projectId, filter: {state?, assignee?, label?, milestone?, kind?, clientVisible?}, sort, cursor) → page
getIssue(projectId, number)                           → { issue, events: [IssueEvent], comments: [Comment] }
linkIssue(projectId, number, target, relation)        → IssueLink
createMilestone / updateMilestone / closeMilestone(projectId, id, createRelease?: {…}) → Milestone
```

**Comments, releases, activity, search**
```
createComment(projectId, target, body)                → Comment
resolveComment(projectId, commentId, resolvedInCommitId?) → Comment
publishRelease(projectId, refName | commitId, title, notes, scope, visibility, milestoneId?) → Release
getReleasePage(releaseId, shareToken?)                → public-safe projection
listActivity(projectId, cursor)                       → page of Activity
search(orgId, projectId?, q, kinds: [asset|issue|commit|release], filters, includeHistory?) → grouped results
```

**Subscriptions** (AppSync real-time): `onRefUpdated(projectId)`, `onIssueChanged(projectId)`, `onLockChanged(projectId)`, `onActivity(projectId)`. The desktop client subscribes to the first and third; the web app to all four.

Pagination is cursor-based everywhere. Errors are typed (`NOT_A_MEMBER`, `REF_MOVED` with current head, `LOCK_HELD` with holder, `PROTECTED_REF`, `INVALID_TRANSITION`) so clients can do the right thing without parsing strings.

---

## 4. Core algorithms

### 4.1 Tree diff

Given two root tree ids, walk both in parallel. At each directory:

- entries only in A → `removed` (recursively for subtrees), only in B → `added`;
- same name, same id → skip the entire subtree (this is where content addressing pays off);
- same name, both trees, different id → recurse;
- same name, both blobs, different oid → `modified`.

Rename detection: after the walk, pair `removed` and `added` blobs with identical oids as `renamed`. Exact-match only; similarity-based rename detection is pointless for binaries.

Cost is proportional to the changed region of the tree, not the project size. `AssetIndex` maintenance, `diffCommits`, review file lists and merge preview all use this one function.

### 4.2 Merge base

Lowest common ancestor on the commit DAG. With `generation` numbers: walk both frontiers with a max-heap by generation; when a commit is reached from both sides it is a candidate; stop when every commit in the heap has generation ≤ the best candidate's. Bounded by the distance since divergence, not history length. Implemented in the merge Lambda; commits are fetched in batches by id (`BatchGetItem`).

### 4.3 Three-way tree merge

Inputs: base tree B (from the merge base), ours O (target ref head), theirs T (source ref head). Per path, after a three-way diff:

| B→O | B→T | Result |
|---|---|---|
| unchanged | unchanged | keep |
| changed | unchanged | ours |
| unchanged | changed | theirs |
| changed | changed, same oid | either (identical) |
| changed | changed, different | **conflict** |
| deleted | unchanged | deleted |
| unchanged | deleted | deleted |
| deleted | changed (or vice versa) | **conflict** (modify/delete) |
| added | added, same oid | either |
| added | added, different | **conflict** |

Conflicts are returned by `previewMerge` and must be resolved by `resolutions` in `mergeRefs`: `ours`, `theirs`, or an explicit `oid` (the user uploaded a hand-combined file). Directory-level conflicts (file vs. directory at the same name) are rare and resolved the same way with `ours`/`theirs` at the directory. No content merging, ever, by design.

The merge commit has `parentIds: [ours, theirs]`, and the target ref is advanced with the usual conditional update. Fast-forward (base == ours) produces no merge commit; the ref just moves, unless the project setting `alwaysMergeCommit` is on (agencies like the explicit "brought in by Theo" record).

### 4.4 Desktop client rebase on `REF_MOVED`

The desktop client snapshots with `expectedCommitId` = the head it last synced. If someone else moved the ref, the server answers `REF_MOVED` with the new head. The client then:

1. Computes its change set C (paths it intended to put/delete).
2. Diffs its old base → new head to get remote changes R.
3. Paths in C ∩ R with different content are conflicts → the client shows **Choose a version** locally (same UI as merge), the user resolves, and the client resubmits against the new head with resolutions folded into `changes`.
4. Paths only in C are resubmitted unchanged. Paths only in R are pulled to disk after the commit succeeds.

Because the client uploads blobs before committing, resubmission is metadata-only and fast.

### 4.5 History for a path

`listCommits(path)` walks the ref's first-parent chain (merges included by first parent, with a toggle to follow both) and at each step compares the path's blob oid to the parent's; emits the commit when it differs. Bounded by a limit and a cursor (commitId). Memoize `(commitId, path) → oid` lookups in the Lambda for the duration of a request. For files that change rarely in long histories this is O(history); the `AssetIndex` row's `lastCommitId` gives the first hit for free, and a per-path change log (`PathHistory: projectId, path, commitId`) written by the same stream consumer that maintains `AssetIndex` makes it O(changes). Ship the walk first, add `PathHistory` when someone has a 5,000-snapshot project.

### 4.6 Reachability (for GC and quotas)

A blob is live if reachable from any non-archived ref head, any release commit, any commit newer than the retention window on an archived ref, or any issue/comment attachment `commitId`. Computed as a batch job (§11), never inline.

---

## 5. State machines

### 5.1 Issue

```
                 ┌──────────┐
   create ──────▶│   new    │──── triage ────▶ todo
                 └──────────┘                    │
   guest-created issues start here;              ▼
   member-created may start at todo         in_progress ◀──── assignee picks up / "fixes #n" on exploration
                                                 │
                                    "fixes #n" on protected ref via review
                                                 ▼
                                             in_review ──── review merged / "fixes #n" lands on main ───▶ done
                                                 │                                                        │
                                                 └────── review closed ───▶ todo                          │
   any state ── close (won't do / duplicate / invalid) ──▶ closed        reopen ◀────────────────────────┘
```

Transitions are validated in `updateIssue`; automatic transitions come from `createCommit` and `reviewAction` parsing `#n`, `fixes #n`, `resolves #n`, `closes #n` (case-insensitive) in messages and from `resolvesIssues` on `openReview`. Automatic transitions never move an issue *backward* and never override a manual `closed`.

### 5.2 Review request

```
open ──▶ changes_requested ──▶ (new commits on source) ──▶ open
open ──▶ approved ──▶ merged
approved ──▶ (new commits on source, if project.reapproveOnPush) ──▶ open
any ──▶ closed
```

Merge requires: state `approved` (or the project doesn't require approval), target ref's `expectedCommitId` still current, all conflicts resolved, and no open *blocking* comments (project setting: comments block by default; can be advisory).

### 5.3 Lock

```
free ──createLock──▶ held(owner, expiresAt)
held ──refreshLock (owner)──▶ held
held ──releaseLock (owner) | snapshot containing path (if project.releaseOnSnapshot) | expiresAt passed──▶ free
held ──releaseLock(force, reason) by owner-role──▶ free  (+ activity event + notification to previous holder)
held ──requestLock by other──▶ held (+ notification to holder with one-click handoff)
```

---

## 6. Upload pipeline

Same protocol for browser, desktop and Git LFS, because it *is* the Git LFS batch protocol with a few additions.

1. **Client hashes** the file (SHA-256, streaming; the desktop client hashes in Rust, the browser with `crypto.subtle.digest` on chunks via a Worker; the current `calculateOID` in `lib/api/asset-api.ts` reads the whole file into memory and must change).
2. **`batchObjects(upload)`** for all files in the pending snapshot at once. For each oid the server checks `Blob`: if `verified`, returns no `upload` action (already have it: instant dedup, the whole reason for hashing first). Otherwise it returns a presigned `PUT` with `ChecksumSHA256` set to the base64 of the oid, so **S3 itself rejects a corrupted or wrong upload**; the `verify` step then only has to `HEAD` the object.
3. **Large files (>100 MB)** get a multipart upload instead: `batchObjects` returns `actions.upload.href` pointing at the bridge's multipart endpoint (`/objects/{oid}/multipart` → `initiate`, `part` URLs, `complete`), following the Git LFS *multipart* transfer adapter draft so `git lfs` clients with that adapter also work. Parts are 64 MB, uploaded in parallel (desktop: 4 at a time; browser: 2). Resumable: the client persists the upload id and completed part numbers; on restart it lists parts and continues. S3 hard limit: 5 TB per object, 10,000 parts.
4. **`verifyObject`** flips `Blob.verified`. Unverified blobs older than 24 h are deleted by GC.
5. **`createCommit`** references the oids. The server refuses a commit that references an unverified oid (`BLOB_NOT_VERIFIED`), which prevents dangling pointers.

Download is symmetric: `batchObjects(download)` returns presigned `GET`s (1 hour), and for guests only after checking the path is client-visible in the referenced commit. For the web app, image and video previews come via CloudFront (§7); originals are always presigned S3, never public.

Storage bucket access rules in `amplify/storage/resource.ts` currently grant every authenticated user read/write/delete on `lfs-objects/*`. **Nobody but the Lambdas should touch the bucket directly.** Phase 0 removes the client-side grants; the browser goes through `batchObjects` like everyone else.

---

## 7. Preview pipeline

Previews are keyed by **blob oid**, not by path or project, so a file that appears in five projects and forty snapshots is rendered once.

```
S3 PUT lfs-objects/…  ──▶ EventBridge ──▶ SQS (preview-jobs) ──▶ Lambda (dispatcher)
                                                                     │
        ┌────────────────────────────────────────────────────────────┼─────────────────────────┐
        ▼                                 ▼                          ▼                         ▼
  image-render (Sharp + libvips)   video-proxy (MediaConvert)   doc-render (pdfium)     3d-render (later)
  jpg/png/webp/tiff/heic/svg       mp4/mov/mxf/webm             pdf/ai(pdf-compatible)  gltf/glb/obj/fbx
  psd (flatten via ImageMagick     ▶ 720p H.264 proxy,          ▶ page PNGs             ▶ turntable
    layer; falls back to           poster frame at 10%,
    embedded composite)            sprite sheet for scrub
```

Outputs to `previews/{oid}/{variant}` where variant ∈ `thumb-256.webp`, `medium-1024.webp`, `large-2048.webp`, `proxy-720.mp4`, `poster.jpg`, `scrub.jpg`, `page-{n}.webp`, `meta.json` (dimensions, duration, codec, color profile, dominant colors, EXIF subset). `AssetIndex.previewState` moves `pending → ready | unsupported | failed`, pushed to the UI via `onActivity`.

Served through **CloudFront with signed cookies** scoped to the org: the browser gets a cookie on login, and previews load as plain `<img>` tags without a Lambda in the path. Signed cookies for a *path prefix* (`previews/*`) mean the guest visibility check does not apply at the CDN; that is acceptable because a preview URL contains an oid, which is unguessable, and the app only renders previews for paths the user can see. Originals stay behind `getBlobUrl`.

Format notes that matter to the personas:

- **PSD/PSB:** ImageMagick reads layered PSDs but is lossy for adjustment layers and some blend modes; Photoshop writes an embedded flattened composite when "Maximize Compatibility" is on (the default). Use the composite when present, flatten only as a fallback, and let the Adobe plugin (later) push an authoritative render at snapshot time. Show a small "server preview" badge in the meantime so nobody signs off on a preview.
- **AI/EPS:** Illustrator files are PDF-compatible by default; treat as PDF. Pure PostScript EPS needs Ghostscript; support later or never.
- **RAW (CR3/ARW/DNG):** libraw via Sharp. Slow; run at lower priority.
- **Video:** MediaConvert is the pragmatic choice on AWS (no ffmpeg binary maintenance in Lambda, handles ProRes/MXF). ~$0.015/min for 720p. A 60-minute source costs about a dollar to proxy. Only proxy on first reference; re-referenced blobs are free.
- **Fonts, project files (`.prproj`, `.aep`, `.blend`, `.indd`):** `unsupported`, generic icon plus metadata; the DAM value is still the history.

Time limits: Lambda 15 minutes with 10 GB memory is enough for images and PDFs up to a few hundred MB. Anything larger, and all video, goes to MediaConvert or a Fargate task via the same queue.

---

## 8. Desktop client

The desktop client is the product for editors. It has to be boringly reliable with 100 GB folders and flaky Wi-Fi.

### Architecture

- **Core in Rust** (`gitdam-core`): file watching, hashing, local database, sync engine, transfer manager. Exposed to the UI over an in-process API and to CLI/tests directly. Rust because hashing 60 GB and watching 50,000 files is where Electron-in-JS clients fall over.
- **UI in Tauri** (web tech, small binary), or Electron if the team's skills demand it. The UI is small: tray menu, changes list, snapshot dialog, conflict resolver, settings.
- **Local state in SQLite**: `files(path, size, mtime, oid, state)`, `pending_uploads`, `locks_cache`, `base_tree` (the tree the folder was last synced to), `ref` (current ref and head commit).
- **Platform hooks:** FSEvents (macOS), ReadDirectoryChangesW (Windows), inotify (Linux, later).

### Sync model

- **Base tree** = the commit the folder was last brought up to date with. Every file on disk is either *clean* (matches base), *draft* (differs), *placeholder* (not downloaded), or *conflicted*.
- **Change detection:** watcher events mark paths dirty; a debounced scan compares `(size, mtime)` to the local db, then hashes only when those differ. Hashing is chunked and can be paused. Files still being written (size changing, or held open for write by another process where detectable) are deferred.
- **Background upload of drafts:** as soon as a draft is stable for a few seconds and the file is not excluded, hash and `batchObjects(upload)` it, so **Snapshot** is metadata-only. If the user edits again before snapshotting, the previous upload is simply an unreferenced blob that GC removes. This is a deliberate trade of bandwidth for the "snapshot is instant" experience; it is a per-project setting (`uploadDraftsEagerly`, default on, off on metered connections detected via the OS).
- **Pull:** `onRefUpdated` subscription (with polling fallback every 60 s). On a new head, diff base → head, and for each changed path: clean on disk → replace; draft on disk → mark *conflicted* and notify; placeholder → update the placeholder's metadata only.
- **Placeholders:** the "cloud files" model. macOS: File Provider extension (proper; Finder integration, on-demand download). Windows: Cloud Files API. Both are substantial work; **v1 ships without them** and offers *Choose folders* (full sync of selected subtrees) plus a *Download on demand* list in the app. Placeholders are the Phase 4 stretch goal.
- **Exclusions:** `.DS_Store`, `Thumbs.db`, `*.tmp`, `~$*`, Adobe autosave directories, and a per-project ignore list [`.gitignore`] editable in project settings.
- **Path stability, guaranteed.** The client never renames, moves or relocates files on disk on its own initiative, and a project's local root never changes once chosen. Premiere, Resolve and After Effects reference media by absolute path, and "relink" is the single most-cited Premiere grievance (RESEARCH.md §4); a sync client that shuffles paths would be worse than Dropbox. Restores and pulls write bytes into the existing path; "keep both" conflict resolution creates a new sibling file rather than renaming the user's. Placeholders, when they arrive, occupy the real path so a later download changes nothing the project file can see.

### Locks in the client

Reliable "lock on open" is not available on macOS or Windows without kernel-level hooks. What works in practice:

1. Files whose type requires check-out are set **read-only on disk** unless the current user holds the lock.
2. When an application tries to save to a read-only file it fails with the OS dialog; simultaneously the client (which sees the open attempt via the watcher's *attribute change* or, on macOS, the `open` event from Endpoint Security when entitled) pops a **Check out?** prompt. One click takes the lock and flips the file writable. For Adobe apps, the plugin (later) does this pre-emptively on document open, which is the clean path.
3. Locks are refreshed every hour while the client is running and released on snapshot if the project says so.

Editors are used to this model from Perforce and from Creative Cloud Libraries; it is not novel to them.

### Conflict resolver

Same three choices as the web merge UI: *Keep mine*, *Take theirs*, *Keep both* (renames mine to `name (Maya's version).psd` as a new path, so nothing is lost). Previews for both sides come from the server; the local one is rendered by the OS QuickLook/thumbnail API when the format allows.

---

## 9. Git compatibility bridge

A separate service (`gitdam-git`, a container on Fargate behind an ALB, not Lambda: Git's smart HTTP protocol wants streaming request and response bodies and long-lived connections) that presents each project as a Git repository.

### Git LFS (Phase 0 exposes, Phase 5 hardens)

- `POST /{org}/{project}.git/info/lfs/objects/batch` → `batchObjects`. The existing `lfs-batch` handler is nearly this; it needs auth, project scoping, the "already have it" short-circuit, `verify` actions, and the multipart adapter.
- `POST …/info/lfs/objects/{oid}/verify` → `verifyObject`.
- `POST …/info/lfs/locks`, `GET …/locks`, `POST …/locks/{id}/unlock`, `POST …/locks/verify` → the `Lock` table. The LFS spec's lock ids are our `(projectId, path)` hashed.
- Auth: HTTP basic with a PAT (§1), or the `git-lfs-authenticate` SSH flow later.

### Git smart HTTP (Phase 5)

The native model has commits, trees and blobs, but not *Git's* byte-exact objects (SHA-1 ids over Git's own serialization). The bridge synthesizes them on the fly:

- **Blob objects** are LFS pointer files (`version…\noid sha256:…\nsize …\n`), ~130 bytes each, plus small text files stored inline (`.gitattributes`, `README.md`). Deterministic from our `Blob` rows.
- **Tree objects** map 1:1 from our per-directory `Tree` rows (entries → Git tree entries, mode `100644`/`040000`), deterministic.
- **Commit objects** need author/committer with email and a timezone-stamped time. We capture `authorEmail` and `createdAt` for this reason. Message is ours. Parents map through the same synthesis.
- A `GitObjectMap (projectId, gitSha1) → (kind, nativeId)` table caches the mapping both ways so pushes can refer to existing objects and so ids are stable across bridge restarts.

`fetch`/`clone`: compute the set of native commits reachable from requested refs minus `have`s, synthesize objects, stream a packfile (no delta compression; the objects are tiny). `push`: parse the incoming pack, validate every blob is either a valid LFS pointer whose oid is a verified `Blob` (the LFS upload precedes the push in Git's flow) or a small text file (stored as a `Blob` too, under 1 MB), map trees and commits to native records, and advance the ref with the same conditional update and protected-ref rules everyone else obeys. A pushed commit becomes a native `Commit` with `kind: import` and `meta.gitSha1`.

Consequences to accept: Git history is exactly our history (good), but Git-side operations that rewrite history (`rebase`, `push --force`) are refused on protected refs and produce new native commits elsewhere; there is no way to "delete" a snapshot from Git, which matches the product's promise that nothing is lost.

### Webhooks

`ProjectWebhook (projectId, url, secret, events[])`. Delivered by a Lambda from the `Activity` stream with an HMAC signature. Events: `ref.updated`, `review.*`, `issue.*`, `release.published`. This is how Sam's CI (§9 in WORKFLOWS.md) files budget issues.

---

## 10. Search

Phase 1–3: **DynamoDB + client-side filtering** over `AssetIndex` and `Issue` per project. Enough for a few thousand assets per project.

Phase 5: **OpenSearch Serverless** index fed from the `AssetIndex`, `Issue`, `Commit` and `Release` table streams. Documents carry `orgId`, `projectId`, `clientVisible`, and `pathPrefix` fields so the authorize step can be a filter clause, not a post-filter. History search ("the version with the orange headline") indexes `Commit` messages and, once AI descriptions exist, per-blob descriptions joined to the commits that introduced the blob.

Automatic tags from `meta.json` (dimensions, duration, dominant colors) land in `AssetIndex.metadata` and are searchable from Phase 2 without OpenSearch.

---

## 11. Storage economics and garbage collection

**Where the money goes:** S3 for blobs, by a wide margin. DynamoDB metadata is a rounding error; MediaConvert is per-minute-of-video; Lambda is negligible.

**Rough model** for the first-customer agency (WORKFLOWS.md §11): three projects, 200 GB live, video editor produces 20 GB of new renders a month, designers 5 GB of new PSD versions a month. Year one: ~500 GB stored on average → ~$140/yr at S3 Standard, less with Intelligent-Tiering. Previews add ~2%. Egress is the risk: a client downloading a 4 GB release ten times is $3.60. Bundles and previews go via CloudFront (cheaper egress, and cacheable).

**What to do about it, in order:**

1. **S3 Intelligent-Tiering** on `lfs-objects/` from day one. Blobs untouched for 30/90 days move to cheaper tiers automatically with no retrieval penalty for the frequent/infrequent tiers.
2. **GC of unreferenced blobs.** Weekly job: mark phase walks every non-archived ref head, every release, every archived ref's head if archived < retention days ago, and every attachment commit (§4.6), collecting reachable tree ids then blob oids into a temporary DynamoDB set (or an S3 manifest for big orgs); sweep phase lists `Blob` rows not in the set and older than 24 h, deletes S3 objects and rows. Because trees are shared globally, marking is per-org but sweeping is global; a blob is deleted only if no org reaches it. Deleted blobs are moved to a `trash/` prefix with a 30-day lifecycle rule rather than deleted outright, so a GC bug is recoverable.
3. **Auto-snapshot squashing.** Auto-snapshots older than 30 days that are not milestones and have exactly one child are folded: the child's `parentIds` are rewritten to skip them. This is the one place history is rewritten, it is confined to `kind: auto`, and it is a project setting. The blobs they referenced become GC-eligible.
4. **Archived exploration retention.** Default 180 days after archive, then the ref is deleted and its unique blobs GC'd. Owners can pin an exploration to keep it forever.
5. **Chunk-level dedup** (content-defined chunking, e.g. FastCDC, so a re-exported render with one changed frame shares most chunks with the previous one): meaningful for video and PSD, and the desktop client is the natural place to do it. But it breaks Git LFS compatibility (LFS objects are whole files) unless the bridge reassembles on download, and it complicates every code path. **Not before there is a customer whose bill demands it.**

Quotas: `Organization.plan` sets storage and bandwidth limits; `Tree.byteSize` on each ref head gives live usage per project in O(1); the GC job records total stored bytes per org.

---

## 12. Security

- **Bucket is private, always.** No client-side S3 grants (Phase 0 removes them). All access is presigned URLs from Lambdas that have checked membership, or CloudFront signed cookies for previews.
- **Uploads are integrity-checked by S3** (`ChecksumSHA256`, §6) so a client cannot store bytes under the wrong oid, which would otherwise poison the global dedup for every tenant.
- **Content-addressed dedup across tenants** means a blob's existence is observable to anyone who knows its hash. `batchObjects(download)` only issues URLs for oids reachable from a commit the caller can read; `batchObjects(upload)` returns "already have it" for any verified oid, which does leak existence. Accept this (GitHub's LFS has the same property) and document it; an org-level `privateDedup` setting that salts the storage key with the org id for regulated customers is straightforward if ever needed.
- **Guests** are the untrusted-user story: every tree, blob URL, issue list and search result is filtered by `clientVisible` paths and flags in the authorize step, and release pages are a separate, minimal projection with no navigation to anything else.
- **Share links** for releases (`visibility: link`) carry a random 128-bit token, are revocable, and can expire. They serve previews and the bundle only.
- **PATs** are stored hashed, scoped (read / write / admin per project), and shown once.
- **Webhooks** are HMAC-signed with a per-hook secret; delivery retries with backoff; failing hooks are disabled after 24 h and the owner is notified.
- **Audit:** `Activity` plus `IssueEvent` are append-only with a 2-year TTL; owner-level actions (force unlock, protected-ref override, member removal, release deletion) are always recorded with a reason.
- **Data residency:** single-region per org at the start; the region is a property of the org, chosen at creation, and everything for that org lives in that region's stack. Cross-region replication is not a Phase 1–5 concern.

---

## 13. Observability

- **Structured logs** from every Lambda with `orgId`, `projectId`, `userId`, `operation`, `latencyMs`, `outcome`. CloudWatch Logs Insights queries saved for the usual questions.
- **Metrics:** commit rate, ref-update conflict rate (should be low; high means the desktop rebase path is exercised too much), preview backlog age (the number the video persona feels), multipart upload failure rate, GC bytes reclaimed, per-org storage.
- **Alarms:** preview backlog > 10 min, ref-update error rate > 1%, bridge 5xx > 0.5%, GC job failed.
- **Client telemetry** (opt-in): desktop sync errors, hash throughput, upload retry counts, with no file names or content.

---

## 14. Phase 0 plan, file by file

Goal: the current prototype runs end to end, safely, with tests, on pinned dependencies. Nothing new is built; what exists is made true.

| # | Change | Files | Notes |
|---|---|---|---|
| 1 | Pin dependencies | `package.json`, `package-lock.json` | `aws-amplify` to a real 6.x, `@aws-amplify/backend` and `-cli` to current stable 1.x. Rerun `npm install`; expect the `data-schema-types` stub to become unnecessary. |
| 2 | Remove the webpack stub and re-enable checks | `next.config.js`, `lib/data-schema-types-stub.js` (delete) | Turn `ignoreBuildErrors` and `ignoreDuringBuilds` off; fix whatever surfaces. |
| 3 | Expose the Lambdas | `amplify/backend.ts` | Add an API Gateway HTTP API (via CDK in `backend.ts`) with a Cognito JWT authorizer; routes `POST /lfs/objects/batch`, `POST /assets/upload`, `POST /assets/download`. Emit the API URL into `amplify_outputs.json` via `backend.addOutput`. |
| 4 | Point the clients at the API | `lib/git-lfs/lfs-client.ts`, `lib/api/asset-api.ts` | Read the URL from outputs; send the Cognito id token as `Authorization`. |
| 5 | Fix the storage layout mismatch | `lib/api/asset-api.ts:111–186` | Stop writing to `lfs-objects/{repositoryId}/{fileName}` via `uploadData`; route through `lfs-batch` so the key is `lfs-objects/ab/cd/<oid>` like the handler expects. Delete the `assets/…` path for now (everything is content-addressed; the ≥1 MB threshold becomes meaningless and goes away). |
| 6 | Stream the hash | `lib/api/asset-api.ts:309`, `lib/git-lfs/lfs-client.ts:203` | Hash in 8 MB chunks in a Web Worker instead of `file.arrayBuffer()`; a 4 GB file currently tries to allocate 4 GB. |
| 7 | Lock down the bucket | `amplify/storage/resource.ts` | Remove `allow.authenticated` grants; keep only the Lambda grants in `backend.ts`. |
| 8 | Tighten data authorization | `amplify/data/resource.ts` | Drop `allow.authenticated().to(['read'])` from all four models. Interim: `allow.owner()` only. Real per-project auth arrives with Phase 1's custom operations. |
| 9 | Verify uploads | `amplify/functions/lfs-batch/handler.ts` | Add `ChecksumSHA256` to the presigned PUT; add a `verify` action and route; write `LFSObject` rows from the Lambda (it is the only thing that knows the upload happened). |
| 10 | Tests | `vitest.config.ts`, `lib/**/*.test.ts`, `amplify/functions/**/*.test.ts` | Pointer parse/create, OID hashing against known vectors, batch handler request/response shapes with a mocked S3 client. |
| 11 | CI | `.github/workflows/ci.yml` | `npm ci`, typecheck, lint, test on every push. `amplify.yml` gets `npm test` in `preBuild`. |
| 12 | README/SETUP refresh | `README.md`, `SETUP.md` | Reflect the above; link the three design docs. |

Estimated: two to three weeks for one engineer, most of it in #1–#3 fighting Amplify version drift.

---

## 15. Phase 1 plan

Goal: the commit graph exists and every upload is a snapshot. Order matters; each step is deployable.

1. **Schema:** add `Organization`, `OrgMember`, `Project`, `ProjectMember`, `Blob`, `Tree`, `Commit`, `Ref`, `Lock`, `Activity`. Keep `Repository`/`Asset` tables until step 6, then drop.
2. **Authorize pipeline function** (`amplify/data/resolvers/authorize.js`) and the first custom operations: `createOrganization`, `createProject`, `addProjectMember`, `listProjects`. Web app onboarding screens.
3. **`batchObjects` / `verifyObject`** as custom operations wrapping the Phase 0 Lambda logic, now project-scoped. Retire the HTTP API routes for the web client (keep them for the LFS bridge).
4. **`createCommit`** Lambda: tree building (§2.2), commit hashing, conditional ref update, `Activity` write. **`getTree`, `listCommits`, `getCommit`, `diffCommits`.** Web upload flow becomes: hash → batch → verify → `createCommit`. History panel with restore (`restore` sugar).
5. **`AssetIndex`** stream consumer (`amplify/functions/index-maintainer`) and the project browser reading from it. Tags and metadata editing.
6. **Migration** of any existing `Asset`/`AssetVersion` rows into an initial commit per repository (`kind: import`), then drop the old models.
7. **Refs UI:** create exploration, switch, archive. `previewMerge` / `mergeRefs` with the conflict chooser. (Reviews wait for Phase 3; a bare merge is enough to make explorations useful.)
8. **Locks:** `createLock`/`releaseLock` and the lock indicator in the browser.
9. **Subscriptions:** `onRefUpdated`, `onLockChanged`; the browser live-updates.

10. **Duplicate detection and folder zip download:** `batchObjects(upload)` already knows when an oid exists; return the paths that reference it (from `AssetIndex`) so the UI can say "already in this project at `exports/hero.png`". Folder download is a Lambda that streams a zip of a tree.

At the end of Phase 1 the web app alone delivers WORKFLOWS.md §2 (minus the desktop app), §3 and §7. That is the point at which a friendly design team can start using it for real. The desktop client follows immediately in Phase 2 (moved forward from Phase 4 after the research in RESEARCH.md §8): the web flow validates the model, the client is what gets adopted.
