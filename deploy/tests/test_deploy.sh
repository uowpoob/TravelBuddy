#!/usr/bin/env bash
# Exercise deployment ordering and failure handling without contacting a server.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
deploy_script="$script_dir/../scripts/deploy.sh"
temp_base=${TMPDIR:-/tmp}
test_root=$(mktemp -d "$temp_base/travelbuddy-cd-test.XXXXXX")
[[ "$test_root" == "$temp_base"/travelbuddy-cd-test.* ]] || exit 1
trap 'rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/bin"
export PATH="$test_root/bin:$PATH"
export TEST_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

cat > "$test_root/bin/git" <<'MOCK'
#!/usr/bin/env bash
set -eu
printf 'git %s\n' "$*" >> "$TEST_LOG"
case "$*" in
  'rev-parse --show-toplevel') printf '%s\n' "$TEST_PROJECT" ;;
  'branch --show-current') echo master ;;
  'status --porcelain') [[ "$TEST_CASE" != dirty ]] || echo ' M compose.yaml' ;;
  'rev-parse refs/remotes/origin/master')
    if [[ "$TEST_CASE" == stale ]]; then echo bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; else echo "$TEST_SHA"; fi ;;
  'rev-parse HEAD')
    if [[ -f "$TEST_PROJECT/merged" ]]; then echo "$TEST_SHA"; else echo cccccccccccccccccccccccccccccccccccccccc; fi ;;
  'merge --ff-only '*) touch "$TEST_PROJECT/merged" ;;
esac
exit 0
MOCK

cat > "$test_root/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -eu
printf 'docker tag=%s %s\n' "${TRAVELBUDDY_IMAGE_TAG:-default}" "$*" >> "$TEST_LOG"
case "$*" in
  'inspect --format {{.Config.Image}} backend-id') echo travelbuddy-backend:0.1.0 ;;
  'inspect --format {{.Config.Image}} frontend-id') echo travelbuddy-frontend:0.1.0 ;;
  *'ps -q backend') echo backend-id ;;
  *'ps -q frontend') echo frontend-id ;;
  *'exec -T db pg_dump '*)
    [[ "$TEST_CASE" != backup-failure ]] || exit 1
    [[ "$TEST_CASE" != empty-backup ]] || exit 0
    echo 'test database backup' ;;
  *'build backend frontend') [[ "$TEST_CASE" != build-failure ]] || exit 1 ;;
  *'run --rm --no-deps -T --interactive=false migrate') [[ "$TEST_CASE" != migration-failure ]] || exit 1 ;;
  *'up -d --no-deps --no-build --wait --wait-timeout 180 backend') [[ "$TEST_CASE" != health-failure ]] || exit 1 ;;
esac
MOCK
printf '#!/usr/bin/env bash\nexit 0\n' > "$test_root/bin/flock"
chmod +x "$test_root/bin/git" "$test_root/bin/docker" "$test_root/bin/flock"

check_absent() {
  if grep -Fq -- "$1" "$TEST_LOG"; then
    printf 'Unexpected operation in %s: %s\n' "$TEST_CASE" "$1" >&2
    exit 1
  fi
}

for test_case in success stale dirty backup-failure empty-backup build-failure migration-failure health-failure; do
  export TEST_CASE=$test_case
  export TEST_PROJECT="$test_root/$test_case"
  export TEST_LOG="$TEST_PROJECT/commands.log"
  mkdir -p "$TEST_PROJECT/deploy"
  printf 'test=true\n' > "$TEST_PROJECT/deploy/.env"
  : > "$TEST_PROJECT/compose.yaml"
  : > "$TEST_LOG"
  result=0
  # Match production: SSH sends this script on stdin to bash -s.
  bash -s -- "$TEST_PROJECT" "$TEST_SHA" < "$deploy_script" > "$TEST_PROJECT/output.log" 2>&1 || result=$?
  case "$test_case" in
    success)
      [[ $result == 0 ]] || { cat "$TEST_PROJECT/output.log"; exit 1; }
      [[ "$(cat "$TEST_PROJECT/.local/deployments/current-commit")" == "$TEST_SHA" ]]
      grep -Fq 'status=success' "$TEST_PROJECT"/.local/deployments/*.txt
      grep -Fq "docker tag=$TEST_SHA compose" "$TEST_LOG"
      dump_line=$(grep -n 'pg_dump' "$TEST_LOG" | cut -d: -f1)
      build_line=$(grep -n 'build backend frontend' "$TEST_LOG" | cut -d: -f1)
      stop_line=$(grep -n 'stop frontend backend' "$TEST_LOG" | cut -d: -f1)
      migrate_line=$(grep -n 'run --rm' "$TEST_LOG" | cut -d: -f1)
      start_line=$(grep -n 'up -d' "$TEST_LOG" | head -1 | cut -d: -f1)
      (( dump_line < build_line && build_line < stop_line && stop_line < migrate_line && migrate_line < start_line )) ;;
    stale)
      [[ $result == 0 ]]
      check_absent pg_dump
      check_absent 'build backend frontend'
      check_absent 'stop frontend backend' ;;
    dirty)
      [[ $result != 0 ]]
      check_absent 'git fetch'
      check_absent pg_dump ;;
    backup-failure|empty-backup|build-failure)
      [[ $result != 0 ]]
      check_absent 'stop frontend backend'
      check_absent 'run --rm' ;;
    migration-failure)
      [[ $result != 0 ]]
      check_absent 'up -d' ;;
    health-failure)
      [[ $result != 0 ]]
      check_absent '--wait-timeout 180 frontend' ;;
  esac
  if [[ "$test_case" == *failure || "$test_case" == empty-backup ]]; then
    [[ ! -e "$TEST_PROJECT/.local/deployments/current-commit" ]]
    grep -Fq 'status=failed' "$TEST_PROJECT"/.local/deployments/*.txt
  fi
  printf 'PASS: %s\n' "$test_case"
done
