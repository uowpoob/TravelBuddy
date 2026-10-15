#!/usr/bin/env bash
# Invoked over SSH using the script from the commit that passed CI.
set -Eeuo pipefail
umask 077

fail() { printf 'Deployment stopped: %s\n' "$*" >&2; exit 1; }

[[ $# == 2 ]] || fail 'Usage: deploy.sh ABSOLUTE_PROJECT_PATH COMMIT_SHA'
project_path=$1
target_sha=$2
[[ "$project_path" == /* && -d "$project_path" ]] || fail 'Project path must be an existing absolute directory'
[[ "$target_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'Expected a full commit SHA'
cd -- "$project_path"
project_path=$(pwd -P)

for tool in git docker flock; do
  command -v "$tool" >/dev/null || fail "Missing command: $tool"
done
[[ "$(git rev-parse --show-toplevel)" == "$project_path" ]] || fail 'Project path must be the Git repository root'
[[ "$(git branch --show-current)" == master ]] || fail 'Server checkout must be on master'
[[ -s deploy/.env ]] || fail 'Server deploy/.env is missing or empty'

mkdir -p .local/backups .local/deployments
exec 9>.local/deployments/deploy.lock
flock -n 9 || fail 'Another deployment is already running on this server'
[[ -z "$(git status --porcelain)" ]] || fail 'Server checkout has local changes; resolve them before deployment'

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes'
git fetch --no-tags origin master </dev/null
if [[ "$(git rev-parse refs/remotes/origin/master)" != "$target_sha" ]]; then
  printf 'Skipping outdated deployment: master has advanced beyond %s.\n' "$target_sha"
  exit 0
fi
git merge-base --is-ancestor HEAD "$target_sha" || fail 'Server master cannot fast-forward to the tested commit'
previous_sha=$(git rev-parse HEAD)
compose=(docker compose --project-directory "$project_path" -f "$project_path/compose.yaml" --env-file "$project_path/deploy/.env")
"${compose[@]}" config --quiet
"${compose[@]}" exec -T db pg_isready -U travelbuddy -d travelbuddy </dev/null
"${compose[@]}" exec -T redis redis-cli ping </dev/null

stamp="$(date -u +%Y%m%dT%H%M%SZ)-${target_sha:0:12}"
record=".local/deployments/$stamp.txt"
backup=".local/backups/$stamp.dump"
previous_backend=$("${compose[@]}" ps -q backend)
previous_frontend=$("${compose[@]}" ps -q frontend)
[[ -n "$previous_backend" && -n "$previous_frontend" ]] || fail 'Expected an existing backend and frontend deployment'
previous_backend_image=$(docker inspect --format '{{.Config.Image}}' "$previous_backend")
previous_frontend_image=$(docker inspect --format '{{.Config.Image}}' "$previous_frontend")
printf 'previous_commit=%s\ntarget_commit=%s\nprevious_backend_image=%s\nprevious_frontend_image=%s\nbackup=%s\n' \
  "$previous_sha" "$target_sha" "$previous_backend_image" "$previous_frontend_image" "$backup" > "$record"
phase=backup
trap 'result=$?; printf "status=failed\nphase=%s\n" "$phase" >> "$record"; printf "Deployment failed during %s. See %s; database rollback is not automatic.\n" "$phase" "$record" >&2; exit "$result"' ERR

# A failed dump or build exits before stopping the currently running application.
"${compose[@]}" exec -T db pg_dump -U travelbuddy -Fc travelbuddy < /dev/null > "$backup.partial"
[[ -s "$backup.partial" ]]
mv -- "$backup.partial" "$backup"
phase=build
git merge --ff-only "$target_sha" </dev/null
[[ "$(git rev-parse HEAD)" == "$target_sha" ]] || fail 'Checkout does not match the tested commit'
export TRAVELBUDDY_IMAGE_TAG="$target_sha"
"${compose[@]}" config --quiet
"${compose[@]}" build backend frontend </dev/null

phase=migration
"${compose[@]}" stop frontend backend
"${compose[@]}" run --rm --no-deps -T --interactive=false migrate

phase=startup
# Explicitly migrate first, then update only application containers.
"${compose[@]}" up -d --no-deps --no-build --wait --wait-timeout 180 backend
"${compose[@]}" up -d --no-deps --no-build --wait --wait-timeout 180 frontend
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/db', timeout=10)"
printf '%s\n' "$target_sha" > .local/deployments/current-commit
printf 'status=success\n' >> "$record"
trap - ERR
printf 'Deployed %s successfully. Backup: %s; record: %s\n' "$target_sha" "$backup" "$record"
