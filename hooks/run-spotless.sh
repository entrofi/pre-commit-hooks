#!/usr/bin/env bash
set -euo pipefail

MVN=${MVN:-./mvnw}
[ -x "$MVN" ] || MVN=mvn
MVN_FLAGS=(-B -ntp -DskipTests)

# pre-commit passes staged files as args (relative to repo root)
FILES=("$@")

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
echo "Current directory $(pwd)"

# 1) Keep only staged .java files that still exist
mapfile -t JAVA_FILES < <(printf '%s\n' "${FILES[@]}" | grep -E '\.java$' || true)
if [ ${#JAVA_FILES[@]} -eq 0 ]; then
  echo "pre-commit: no staged Java files; skipping Spotless."
  exit 0
fi

# 2) Build comma-separated list for spotlessFiles
SPOTLESS_FILES=$(IFS=, ; echo "${JAVA_FILES[*]}")

# 3) Detect affected child modules (dirs with pom.xml under root)
declare -A MODS=()
for f in "${JAVA_FILES[@]}"; do
  [ -f "$f" ] || continue
  d=$(dirname "$f")
  while [[ "$d" != "." && "$d" != "/" ]]; do
    if [[ -f "$d/pom.xml" ]]; then
      [[ "$d" != "." ]] && MODS["$d"]=1
      break
    fi
    d=$(dirname "$d")
  done
done

MVN_PL=()
if (( ${#MODS[@]} > 0 )); then
  modules=$(IFS=, ; echo "${!MODS[*]}")
  MVN_PL=(-pl "$modules" -am)
fi

echo "pre-commit: Spotless (files=${#JAVA_FILES[@]}) modules=${MVN_PL[*]:-<all>}"

# 4) Format only the staged files (no ratchet, no stash)
"$MVN" "${MVN_FLAGS[@]}" \
  -DspotlessFiles="$SPOTLESS_FILES" \
  "${MVN_PL[@]}" \
  com.diffplug.spotless:spotless-maven-plugin:apply

# 5) If Spotless changed anything, restage and fail so user recommits
if [ -n "$(git diff --name-only)" ]; then
  git add -A
  echo "✖ Spotless reformatted files. Review and commit again."
  exit 1
fi