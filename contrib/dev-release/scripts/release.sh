#!/usr/bin/env bash
# Release helper: bump plugin version across manifests, commit, and create the
# tag — all locally. Nothing touches origin.
#
# Pushing and publishing the GitHub release happen in the publishing procedure
# (see contrib/dev-release/SKILL.md), under human review, so release-note
# commentary and go-ahead come before anything user-visible lands on origin:
#   git push origin HEAD v<version>
#   gh release create v<version> ... -R RelationalAI/rai-agent-skills
#
# Usage:
#   scripts/release.sh [patch|minor|major|X.Y.Z]    # default: patch
#   scripts/release.sh --dry-run [patch|minor|major|X.Y.Z]
#   scripts/release.sh --help
#
# Assumes (see contrib/dev-release/SKILL.md for context):
#   * current branch is `main` in a clone of RelationalAI/rai-agent-skills
#   * `origin` remote points at the canonical repo
#   * you have push + tag + release permissions on origin
#   * `gh` is installed and authenticated
#   * working tree has no uncommitted tracked changes (untracked files OK)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# ---- parse args ----
DRY_RUN=0
BUMP=patch
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) BUMP="$arg" ;;
  esac
done

# ---- preflight ----
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] \
  || { echo "ERROR: must run on main, got '$BRANCH'" >&2; exit 1; }

[ -z "$(git status --porcelain --untracked-files=no)" ] \
  || { echo "ERROR: working tree has uncommitted changes" >&2; exit 1; }

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
[ -n "$ORIGIN_URL" ] \
  || { echo "ERROR: no 'origin' remote configured" >&2; exit 1; }
ORIGIN_REPO="$(echo "$ORIGIN_URL" | sed -E 's#^(git@[^:]+:|https?://[^/]+/)##; s/\.git$//')"
[ "$ORIGIN_REPO" = "RelationalAI/rai-agent-skills" ] \
  || { echo "ERROR: origin points at '$ORIGIN_REPO', expected 'RelationalAI/rai-agent-skills'" >&2; exit 1; }

LATEST_TAG="$(git tag --sort=-v:refname | head -1 || true)"
if [ -n "$LATEST_TAG" ] \
   && [ "$(git rev-parse "$LATEST_TAG^{commit}")" = "$(git rev-parse HEAD)" ]; then
  cat >&2 <<EOF
ERROR: HEAD is already at tag $LATEST_TAG. A previous release run committed
and tagged locally, and the publishing procedure either hasn't run yet or left
HEAD where it was. Re-running would bump on top of the existing release and
skip a version number.

AGENT: Do NOT re-run this script. Stop and work with the user to reconcile the
current state: check whether $LATEST_TAG was pushed to origin, whether a
GitHub release exists for it, and whether the manifests reflect the intended
version. Only re-run this script after HEAD has advanced past $LATEST_TAG.
EOF
  exit 1
fi

FILES=(
  plugins/rai/.claude-plugin/plugin.json
  plugins/rai/.codex-plugin/plugin.json
  plugins/rai/.cursor-plugin/plugin.json
)
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "ERROR: missing manifest $f" >&2; exit 1; }
done

# ---- read current version (first manifest is source of truth) ----
version_in() { sed -n 's/.*"version": "\([0-9.]*\)".*/\1/p' "$1" | head -1; }
OLD="$(version_in "${FILES[0]}")"
[ -n "$OLD" ] || { echo "ERROR: could not read version from ${FILES[0]}" >&2; exit 1; }

# All three manifests must agree
for f in "${FILES[@]}"; do
  found="$(version_in "$f")"
  [ "$found" = "$OLD" ] \
    || { echo "ERROR: version drift — $f is '$found', expected '$OLD'" >&2; exit 1; }
done

# ---- compute new version ----
case "$BUMP" in
  patch|minor|major)
    IFS=. read -r MAJOR MINOR PATCH <<< "$OLD"
    case "$BUMP" in
      patch) PATCH=$((PATCH + 1)) ;;
      minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
      major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    esac
    NEW="$MAJOR.$MINOR.$PATCH"
    ;;
  [0-9]*.[0-9]*.[0-9]*)
    NEW="$BUMP"
    ;;
  *)
    echo "ERROR: invalid bump '$BUMP' — expected patch|minor|major|X.Y.Z" >&2
    exit 1 ;;
esac

echo "Repo:           $ORIGIN_REPO"
echo "Branch:         $BRANCH"
echo "Latest tag:     ${LATEST_TAG:-<none>}"
echo "Manifests at:   $OLD"
echo "New version:    $NEW (tag: v$NEW)"
echo ""
echo "Plan (all local — nothing pushed):"
echo "  1. Update ${#FILES[@]} manifests -> $NEW"
echo "  2. git commit -m 'Release v$NEW'"
echo "  3. git tag -a v$NEW -m v$NEW"
echo ""
echo "Pushing the bump commit + tag and creating the GitHub release are"
echo "handled by the publishing procedure, under human review. After this"
echo "script finishes:"
echo "  1. Review the repo state and collect any release-note commentary."
echo "  2. git push origin HEAD v$NEW"
echo "  3. gh release create v$NEW --generate-notes -R $ORIGIN_REPO"
echo ""

if [ "$DRY_RUN" = "1" ]; then
  echo "[dry-run] not executing."
  exit 0
fi

read -rp "Proceed? [y/N] " confirm
case "$confirm" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 0 ;;
esac

# ---- execute ----
for f in "${FILES[@]}"; do
  sed -i.bak "s/\"version\": \"$OLD\"/\"version\": \"$NEW\"/" "$f"
  rm "$f.bak"
done

git add -u
git commit -m "Release v$NEW"
git tag -a "v$NEW" -m "v$NEW"

echo ""
echo "Bump commit and tag v$NEW created locally. Nothing has been pushed."
echo ""
echo "Next: review the commit range and collect any release-note commentary,"
echo "then push and publish under human review:"
echo "  git push origin HEAD v$NEW"
echo "  gh release create v$NEW --generate-notes -R $ORIGIN_REPO"
echo ""
echo "See contrib/dev-release/SKILL.md 'Publishing the GitHub release' for the"
echo "agent-driven, human-gated flow (notes mechanisms, spot-checks)."
