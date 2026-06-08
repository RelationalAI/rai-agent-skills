#!/usr/bin/env bash
#
# bootstrap.sh — drop ORM-tailored GSD templates into the current project.
#
# Usage:
#   bash bootstrap.sh --schema <path-to-schema.sql>
#   bash bootstrap.sh --text   [<path-to-domain-doc.md>]
#
# What it does:
#   1. Creates .planning/ (if missing) and copies the project-level templates
#      (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, CONTEXT.md) with placeholder
#      substitution.
#   2. Creates .planning/phases/<NN-name>/PLAN.md for each phase, seeded from
#      the corresponding template.
#   3. Copies the rai-orm-verifier subagent into .claude/agents/.
#   4. Prints next-step guidance.
#
# Existing files are NOT overwritten — the script refuses to clobber. Re-run
# after removing the relevant files if you want to regenerate.

set -euo pipefail

# ---------- locate ourselves ------------------------------------------------

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATES_DIR="$SCRIPT_DIR/templates"
AGENTS_DIR="$SCRIPT_DIR/agents"

[ -d "$TEMPLATES_DIR" ] || { echo "error: templates/ not found under $SCRIPT_DIR" >&2; exit 1; }
[ -d "$AGENTS_DIR" ]    || { echo "error: agents/ not found under $SCRIPT_DIR" >&2; exit 1; }

# ---------- argument parsing ------------------------------------------------

FLOW=""
INPUT_PATH=""

usage() {
  cat >&2 <<EOF
Usage:
  bash bootstrap.sh --schema <path-to-schema.sql>
  bash bootstrap.sh --text   [<path-to-domain-doc.md>]

Options:
  --schema <path>   Drop SRP-flow templates (5 phases, discuss skipped).
  --text   [<path>] Drop CSDP-flow templates (5 phases, discuss essential).
                    The path is optional; if omitted, you'll be prompted to
                    paste/edit a domain description into .planning/PROJECT.md
                    during /gsd:new-project.
EOF
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --schema)
      FLOW="schema"
      shift
      [ $# -gt 0 ] || { echo "error: --schema requires a path" >&2; usage; }
      INPUT_PATH="$1"
      shift
      ;;
    --text)
      FLOW="text"
      shift
      if [ $# -gt 0 ] && [ "${1:0:2}" != "--" ]; then
        INPUT_PATH="$1"
        shift
      fi
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      ;;
  esac
done

[ -n "$FLOW" ] || { echo "error: must pass --schema or --text" >&2; usage; }

if [ "$FLOW" = "schema" ]; then
  [ -f "$INPUT_PATH" ] || { echo "error: schema file not found: $INPUT_PATH" >&2; exit 1; }
elif [ "$FLOW" = "text" ] && [ -n "$INPUT_PATH" ]; then
  [ -f "$INPUT_PATH" ] || { echo "error: text file not found: $INPUT_PATH" >&2; exit 1; }
fi

# ---------- derived values --------------------------------------------------

PROJECT_NAME="$(basename "$(pwd)")"
INPUT_BASENAME="${INPUT_PATH##*/}"
DATE_TODAY="$(date +%Y-%m-%d)"

if [ "$FLOW" = "schema" ]; then
  METHODOLOGY="Schema Recovery Procedure (SRP)"
  FLOW_LABEL="schema"
  VERBS_PER_PHASE="plan, execute, verify, ship"
  DISCUSS_NOTE="Per-phase discuss is skipped: workflow is deterministic once project-level defaults are locked."
else
  METHODOLOGY="Conceptual Schema Design Procedure (CSDP)"
  FLOW_LABEL="text"
  VERBS_PER_PHASE="discuss, plan, execute, verify, ship"
  DISCUSS_NOTE="Per-phase discuss is essential: CSDP Steps 1, 4, 6 are dialogue with the domain expert."
fi

# ---------- substitution ----------------------------------------------------

# sed-based placeholder substitution. We use | as the sed delimiter to avoid
# escaping forward slashes in paths.
substitute() {
  local src="$1"
  local dest="$2"

  sed \
    -e "s|{{PROJECT_NAME}}|${PROJECT_NAME}|g" \
    -e "s|{{INPUT_PATH}}|${INPUT_PATH}|g" \
    -e "s|{{INPUT_BASENAME}}|${INPUT_BASENAME}|g" \
    -e "s|{{INPUT_TYPE}}|${FLOW_LABEL}|g" \
    -e "s|{{DATE}}|${DATE_TODAY}|g" \
    -e "s|{{METHODOLOGY}}|${METHODOLOGY}|g" \
    -e "s|{{VERBS_PER_PHASE}}|${VERBS_PER_PHASE}|g" \
    -e "s|{{DISCUSS_NOTE}}|${DISCUSS_NOTE}|g" \
    "$src" > "$dest"
}

# ---------- refuse to clobber ----------------------------------------------

require_absent() {
  if [ -e "$1" ]; then
    echo "error: refusing to overwrite existing $1" >&2
    echo "       remove it first, or run bootstrap.sh in a clean project." >&2
    exit 1
  fi
}

require_absent ".planning/PROJECT.md"
require_absent ".planning/REQUIREMENTS.md"
require_absent ".planning/ROADMAP.md"
require_absent ".planning/CONTEXT.md"

# ---------- copy project-level templates ------------------------------------

mkdir -p .planning

PROJECT_TEMPLATES="$TEMPLATES_DIR/project/$FLOW_LABEL"
for tmpl in PROJECT REQUIREMENTS ROADMAP CONTEXT; do
  substitute "$PROJECT_TEMPLATES/${tmpl}.md.tmpl" ".planning/${tmpl}.md"
done

# ---------- copy phase templates --------------------------------------------

mkdir -p .planning/phases

PHASE_TEMPLATES="$TEMPLATES_DIR/phases/$FLOW_LABEL"
PHASE_COUNT=0
for phase_file in "$PHASE_TEMPLATES"/*.md; do
  [ -f "$phase_file" ] || continue
  phase_name="$(basename "$phase_file" .md)"   # e.g. "01-discover"
  mkdir -p ".planning/phases/$phase_name"
  substitute "$phase_file" ".planning/phases/$phase_name/PLAN.md"
  PHASE_COUNT=$((PHASE_COUNT + 1))
done

# ---------- copy verifier agent ---------------------------------------------

mkdir -p .claude/agents
if [ -e ".claude/agents/rai-orm-verifier.md" ]; then
  echo "note: .claude/agents/rai-orm-verifier.md already exists — left as-is."
else
  cp "$AGENTS_DIR/rai-orm-verifier.md" ".claude/agents/rai-orm-verifier.md"
fi

# ---------- report ----------------------------------------------------------

cat <<EOF

✓ Created .planning/PROJECT.md         ($METHODOLOGY for $PROJECT_NAME)
✓ Created .planning/REQUIREMENTS.md    (antipattern flags, dialect, modality defaults)
✓ Created .planning/ROADMAP.md         (5 phases — $VERBS_PER_PHASE)
✓ Created .planning/CONTEXT.md         (Halpin posture, terminology preferences)
✓ Created .planning/phases/            ($PHASE_COUNT phase plans seeded)
✓ Created .claude/agents/rai-orm-verifier.md

Flow:   $METHODOLOGY
Input:  ${INPUT_PATH:-<none — will collect during /gsd:new-project>}

Next:
  claude
  > /gsd:new-project
EOF
