---
name: dev-release
description: Bumps the plugin version across all manifest files, creates a git tag,
  and publishes a GitHub release for rai-agent-skills. Use when cutting a release.
---

# RAI Release: Version Bump → Tag → Release

Claude Code treats `plugin.json` `version` as the plugin cache key — if you ship
code changes without bumping, end users silently keep the cached copy. All four
manifests that carry the plugin version must stay in sync.

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

Exactly four. Keep them identical. Do NOT touch version fields elsewhere
(e.g. `plugins/rai/skills/rai-graph-analysis/examples/metadata.json` has its
own unrelated `version`).

- `plugins/rai/.claude-plugin/plugin.json`
- `plugins/rai/.codex-plugin/plugin.json`
- `plugins/rai/.cursor-plugin/plugin.json`
- `.cursor-plugin/marketplace.json` (inside the single plugin entry)

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

The script runs the preflight checks from **Assumptions** above, reads the
current version from the manifests (and fails if they've drifted from each
other), computes the next version, prints a plan, and prompts before executing
the bump → commit → tag → push → release sequence. It targets `origin` by URL
(not by `gh`'s default resolution) so a stray `gh` config can't redirect the
release.

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

### 2. Update the four manifests

```bash
OLD=1.0.9; NEW=1.0.10
for f in plugins/rai/.claude-plugin/plugin.json \
         plugins/rai/.codex-plugin/plugin.json \
         plugins/rai/.cursor-plugin/plugin.json \
         .cursor-plugin/marketplace.json; do
  sed -i.bak "s/\"version\": \"$OLD\"/\"version\": \"$NEW\"/" "$f" && rm "$f.bak"
done
```

Verify every non-example occurrence is on the new version:

```bash
grep -rn '"version"' .claude-plugin .agents .cursor-plugin plugins | grep -v /examples/
```

All four lines should show the new version.

### 3. Commit, tag, push

```bash
git add -u
git commit -m "Release v$NEW"
git tag -a "v$NEW" -m "v$NEW"
git push origin HEAD "v$NEW"
```

### 4. Publish the GitHub release

```bash
gh release create "v$NEW" --generate-notes -R RelationalAI/rai-agent-skills
gh release view   "v$NEW" --web -R RelationalAI/rai-agent-skills
```

`--generate-notes` builds release notes from commit messages since the previous
tag. Edit the draft for clarity if the auto-generated summary is noisy.

## When NOT to use

- Docs-only changes that don't ship to end users — a README typo doesn't need a
  plugin-cache bust.
- Edits to `plugins/rai/skills/*/examples/metadata.json` — example-specific,
  not plugin-level.
