#!/usr/bin/env bash
set -euo pipefail

MVN=${MVN:-./mvnw}
[ -x "$MVN" ] || MVN=mvn
MVN_FLAGS=(-B -ntp -q -DskipTests)

# --- parse optional flags before filenames ---
EXTRA_SRC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
  --extra-src=*) EXTRA_SRC="${1#*=}"; shift ;;
  --) shift; break ;;
  -* ) echo "Unknown option: $1" >&2; exit 2 ;;
  * ) break ;; # first filename hit
  esac
done

# Remaining args are filenames from pre-commit
FILES=("$@")

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

# staged .java only
mapfile -t JAVA_FILES < <(printf '%s\n' "${FILES[@]}" | grep -E '\.java$' || true)
[[ ${#JAVA_FILES[@]} -eq 0 ]] && { echo "pre-commit: no staged Java files; skipping Checkstyle."; exit 0; }

# build source roots list (defaults + optional extras)
SOURCE_ROOTS=("src/main/java" "src/test/java")
if [[ -n "$EXTRA_SRC" ]]; then
  IFS=',' read -r -a _EXTRA <<< "$EXTRA_SRC"
  for s in "${_EXTRA[@]}"; do
    [[ -n "$s" ]] && SOURCE_ROOTS+=("$s")
  done
fi

# group files by module, compute includes relative to source roots
declare -A MODULE_INCLUDES
declare -A MODULE_SEEN

for f in "${JAVA_FILES[@]}"; do
  [[ -f "$f" ]] || continue

  # find module dir (ancestor with pom.xml)
  mod="$f"
  while [[ "$mod" != "." && "$mod" != "/" ]]; do
    mod="$(dirname "$mod")"
    [[ -f "$mod/pom.xml" ]] && break
  done
  [[ ! -f "$mod/pom.xml" ]] && continue

  rel=""
  for src in "${SOURCE_ROOTS[@]}"; do
    prefix="$mod/$src/"
    if [[ "$f" == "$prefix"* ]]; then
      rel="${f#"$prefix"}"  # e.g., com/acme/Foo.java
      break
    fi
  done
  [[ -z "$rel" ]] && continue

  MODULE_SEEN["$mod"]=1
  if [[ -n "${MODULE_INCLUDES[$mod]+x}" && -n "${MODULE_INCLUDES[$mod]}" ]]; then
    MODULE_INCLUDES["$mod"]+=",${rel}"
  else
    MODULE_INCLUDES["$mod"]="$rel"
  fi
done

(( ${#MODULE_SEEN[@]} == 0 )) && { echo "pre-commit: staged Java files not under configured source roots; skipping."; exit 0; }

# run checkstyle per module with module-relative includes, show only errors/warnings
for mod in "${!MODULE_SEEN[@]}"; do
  includes="${MODULE_INCLUDES[$mod]:-}"
  [[ -z "$includes" ]] && continue

  echo "pre-commit: Checkstyle module=$mod files=$(tr -cd ',' <<<"$includes" | wc -c | awk '{print $1+1}')"
  out=$(
    "$MVN" "${MVN_FLAGS[@]}" \
      -Dcheckstyle.includes="$includes" \
      -pl "$mod" checkstyle:check 2>&1 \
      | grep -E "^\[(ERROR|WARNING)\] .+\.java:"
  )
  if [[ -n "$out" ]]; then
    echo "$out"
    echo "✖ Checkstyle issues in module: $mod"
    exit 1
  else
    echo "✔ $mod passed"
  fi
done