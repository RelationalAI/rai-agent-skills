---
name: dev-release
description: Bumps the plugin version across manifest files, commits, and
  creates a local git tag for rai-agent-skills. Pushing and publishing the
  GitHub release happen separately, under human review. Use when cutting a
  release.
---

# RAI Release: Bump + Tag (local) → Push + Publish (human-gated)

Claude Code treats `plugin.json` `version` as the plugin cache key — if you ship
code changes without bumping, end users silently keep the cached copy. All three
manifests that carry the plugin version must stay in sync.

The helper script handles the mechanical, local parts (bump manifests, commit,
create the tag). It deliberately **does not** push or publish — those steps
happen under human review via the publishing procedure, so the releaser can
review repo state and shape release notes before anything user-visible lands
on origin.

## Assumptions

This workflow targets the canonical repo and assumes:

- You're on `main` in a clone of `RelationalAI/rai-agent-skills`, with `origin`
  pointing at it.
- You have push access to `main` and permission to create tags + releases on
  origin. Only RAI maintainers do — if `git push origin` prompts for
  credentials or `gh release create` 403s, stop.
- `gh` is installed and authenticated.
- Working tree has no uncommitted tracked changes (untracked files are fine).

Running against a fork or a feature branch will put the release on the wrong
branch/repo. Don't do it.

## Files carrying the plugin version

The plugin version lives in exactly three files — the official plugin metadata
for each supported host (Claude Code, Codex, Cursor). Keep them identical.
Any other `version` field in the repo is out of scope for this skill.

- `plugins/rai/.claude-plugin/plugin.json`
- `plugins/rai/.codex-plugin/plugin.json`
- `plugins/rai/.cursor-plugin/plugin.json`

> **Adding or removing a plugin host** (e.g. Gemini, a new marketplace) means
> this list changes. When that happens, update **both**:
> - This skill — the list above, the count in the intro, the `wc -l` expected
>   value in the Manual path verification step, and the `OLD/NEW` bump loop.
> - The script — the `FILES` array in `contrib/dev-release/scripts/release.sh`.
>
> A release run with an out-of-date `FILES` array will silently skip the new
> manifest.

## Recommended path — run the helper script

From the repo root:

```bash
# default: patch bump
contrib/dev-release/scripts/release.sh

# or pick a bump level
contrib/dev-release/scripts/release.sh minor
contrib/dev-release/scripts/release.sh major

# or specify an exact version
contrib/dev-release/scripts/release.sh 1.2.3

# preview without executing
contrib/dev-release/scripts/release.sh --dry-run minor
```

The script runs the preflight checks from **Assumptions** above, asserts that
`origin` points at `RelationalAI/rai-agent-skills` (no fork misrouting),
verifies HEAD is not already at the latest release tag (no double-bump after a
partial prior run), reads the current version from the manifests (and fails if
they've drifted), computes the next version, prints a plan, and prompts before
executing the bump → commit → tag sequence. **All three steps are local** —
nothing is pushed.

Pushing the bump commit and tag, and creating the GitHub release, happen in
the publishing procedure below, under human review. This keeps everything
user-visible — the commit on `main`, the public tag, and the release — behind
the same go-ahead gate.

### Publishing the GitHub release (agent-driven, human-gated)

After `release.sh` finishes, the bump commit and tag exist only locally —
nothing is on origin. The agent pushes both and creates the release, but only
after surfacing context, collecting any release-note commentary from the
user, and getting an explicit go-ahead.

**Agent steps:**

1. **Surface the context** so the user can decide what they want to say.
   Summarize:
   - The commit range since the previous tag
     (`git log <prev-tag>..v$NEW --oneline`).
   - User-visible changes the agent noticed (skill renames, new skills,
     breaking path changes, etc.).
   - Anything not obvious from commit subjects alone.

2. **Invite commentary with a single open question** — don't enumerate
   mechanisms. Something like:
   *"Want to add any commentary to the release notes, or should I publish with
   just the auto-generated commit log?"*

   Based on the user's response, pick the matching `gh release create`
   invocation from the reference table below. Do not ask the user to choose
   between mechanisms; the agent owns that mapping.

   | User intent                                                        | Invocation (append `-R RelationalAI/rai-agent-skills`) |
   |--------------------------------------------------------------------|--------------------------------------------------------|
   | Short paragraph, provided inline in chat                           | `gh release create v$NEW --generate-notes --notes "<text>"` — text becomes header, auto-notes appended |
   | Longer notes drafted (or to be drafted) in a file                  | `gh release create v$NEW --generate-notes --notes-file <path>` |
   | Wants to review/edit the full text before it goes live             | `gh release create v$NEW --generate-notes --draft`, then user edits via web UI or `gh release edit` and publishes |
   | No commentary — just ship the auto commit log                      | `gh release create v$NEW --generate-notes` |

3. **Wait for explicit go-ahead** before touching origin. Do not push the tag
   or publish on inferred consent — a "sounds good" about the commentary is
   not the same as approval to ship.

4. **On go-ahead, push the bump commit + tag together, then create the release:**
   ```bash
   git push origin HEAD v$NEW
   gh release create v$NEW ...   # the invocation picked in step 2
   ```
   Pair these so the commit, tag, and release all land together.

5. **After publishing**, spot-check:
   - `gh release view v$NEW -R RelationalAI/rai-agent-skills` to confirm body
     and assets. Add `--web` to open in the browser.
   - Flag anomalies (truncated notes, wrong tag target, unexpected assets)
     before closing the loop with the user.

**Never** push the tag or run `gh release create` without explicit go-ahead —
both are user-visible and hard to un-publish cleanly.

### Recovery: push succeeded but release not created

If `git push origin HEAD v<version>` succeeded but `gh release create` failed,
the tag is on origin with no release attached. Re-run the `gh release create`
variant chosen in step 2 whenever you're ready. Do NOT re-run `release.sh`;
its tag-at-HEAD preflight will correctly refuse.

### Recovery: script aborted mid-run, or publishing never happened

If the script created the bump commit + tag locally but the publishing
procedure never ran (or was deferred), HEAD will be at the new tag.
Re-running `release.sh` will refuse (the tag-at-HEAD preflight catches this).
Either:

- Pick up the publishing procedure from step 1 whenever you're ready —
  everything is still local, no rework needed.
- Or unwind: `git tag -d v<version>` and `git reset --hard HEAD^` to drop the
  local tag and bump commit, then retry the script.

## Manual path (reference)

Use these steps only if the script can't run — e.g. you need a one-off change
between bump and tag, or you're on a machine where the script's preflight is
too strict.

### 1. Decide the next version

Tags follow `vMAJOR.MINOR.PATCH`.

| Change                                         | Bump  |
|------------------------------------------------|-------|
| Bug fix, wording, small cleanup                | patch |
| New skill, new capability inside a skill       | minor |
| Breaking change, plugin rename, skill removal  | major |

Find the latest tag:

```bash
git tag --sort=-v:refname | head -1
```

### 2. Update the three manifests

```bash
OLD=1.0.10; NEW=2.0.0
for f in plugins/rai/.claude-plugin/plugin.json \
         plugins/rai/.codex-plugin/plugin.json \
         plugins/rai/.cursor-plugin/plugin.json; do
  sed -i.bak "s/\"version\": \"$OLD\"/\"version\": \"$NEW\"/" "$f" && rm "$f.bak"
done
```

Verify every non-example manifest is on the new version — expect exactly 3
matches. Any other count means drift or a missed manifest:

```bash
grep -rn "\"version\": \"$NEW\"" .claude-plugin .agents .cursor-plugin plugins | grep -v /examples/ | wc -l
# Expect: 3
```

### 3. Commit and tag (all local)

```bash
git add -u
git commit -m "Release v$NEW"
git tag -a "v$NEW" -m "v$NEW"
```

Nothing is pushed yet. Pushing the bump commit, pushing the tag, and creating
the GitHub release all happen together in the publishing procedure (step 4),
under human review.

### 4. Publish the GitHub release

Publishing follows the same agent-driven, human-gated flow as the scripted
path — see **Publishing the GitHub release** above. The agent surfaces
context, invites optional commentary, waits for go-ahead, and picks the
matching `gh release create` invocation.

## When NOT to use

- Docs-only changes that don't ship to end users — a README typo doesn't need a
  plugin-cache bust.
- Changes to `version` fields outside the three official plugin manifests
  listed above — this skill is scoped to the supported plugin hosts.
