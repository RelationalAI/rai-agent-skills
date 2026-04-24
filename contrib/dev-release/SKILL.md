---
name: dev-release
description: Bumps the plugin version across all manifest files, creates a git tag,
  and publishes a GitHub release for rai-agent-skills. Use when cutting a release.
---

# RAI Release: Version Bump → Tag → Release

Claude Code treats `plugin.json` `version` as the plugin cache key — if you ship
code changes without bumping, end users silently keep the cached copy. All four
manifests that carry the plugin version must stay in sync.

## Files carrying the plugin version

Exactly four. Keep them identical. Do NOT touch version fields elsewhere
(e.g. `plugins/rai/skills/rai-graph-analysis/examples/metadata.json` has its own
unrelated `version`).

- `plugins/rai/.claude-plugin/plugin.json`
- `plugins/rai/.codex-plugin/plugin.json`
- `plugins/rai/.cursor-plugin/plugin.json`
- `.cursor-plugin/marketplace.json` (inside the single plugin entry)

## 1. Decide the next version

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

## 2. Update the four manifests

Change `"version": "<OLD>"` to `"version": "<NEW>"` in each file. With `sed`:

```bash
OLD=1.0.9
NEW=1.0.10
for f in plugins/rai/.claude-plugin/plugin.json \
         plugins/rai/.codex-plugin/plugin.json \
         plugins/rai/.cursor-plugin/plugin.json \
         .cursor-plugin/marketplace.json; do
  sed -i '' "s/\"version\": \"$OLD\"/\"version\": \"$NEW\"/" "$f"
done
```

Verify every non-example occurrence is on the new version:

```bash
grep -rn '"version"' .claude-plugin .agents .cursor-plugin plugins | grep -v /examples/
```

All four lines should show `"$NEW"`.

## 3. Commit, tag, push

```bash
git add -u
git commit -m "Release v$NEW"
git tag -a "v$NEW" -m "v$NEW"
git push origin HEAD "v$NEW"
```

## 4. Publish the GitHub release

```bash
gh release create "v$NEW" --generate-notes
```

`--generate-notes` builds release notes from commit messages since the previous
tag. Edit the draft for clarity if the auto-generated summary is noisy — users
read the release page to understand what changed.

Confirm:

```bash
gh release view "v$NEW" --web
```

## When NOT to use

- Docs-only changes that don't ship to end users — a README typo doesn't need a
  plugin-cache bust.
- Edits to `plugins/rai/skills/*/examples/metadata.json` — example-specific, not
  plugin-level.
