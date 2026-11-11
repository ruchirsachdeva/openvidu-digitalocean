#!/usr/bin/env bash
# Opt-in guard for the exact reviewed 3.8 AMD64 egress image. This is not a
# recorder-pool readiness certificate or permission to remove recovery files.
set -euo pipefail

hold() { printf '%s\n' "CourseUltra recorder startup held: $1" >&2; exit 1; }

[[ $# -eq 0 ]] || hold "unexpected startup arguments"
[[ $(uname -m) == x86_64 ]] || hold "unreviewed architecture"
[[ $(id -un) == egress ]] || hold "unexpected service user"
[[ ${EGRESS_CONFIG_FILE:-} == /config/egress.yaml ]] || hold "unexpected configuration path"

ENTRYPOINT=/entrypoint.sh
EXPECTED_ENTRYPOINT=f2bdec0a85a20a4ee1954c69924549aba24c73b530029a5a8cc0e1579da38ca0
CONFIG=/config/egress.yaml
CONFIG_HASH=/courseultra-guard/egress-config.sha256
START_LOCK=/courseultra-guard/start.lock
RECOVERY_ROOT=/home/egress

for file in "$ENTRYPOINT" "$CONFIG" "$CONFIG_HASH" "$START_LOCK"; do
  [[ -f $file && ! -L $file && -r $file ]] || hold "required regular file unavailable"
done
[[ -x $ENTRYPOINT ]] || hold "original entrypoint is not executable"
entrypoint_hash=$(sha256sum "$ENTRYPOINT") || hold "entrypoint verification unavailable"
[[ ${entrypoint_hash%% *} == "$EXPECTED_ENTRYPOINT" ]] || hold "unreviewed entrypoint"
expected_config=$(< "$CONFIG_HASH")
[[ $expected_config =~ ^[0-9a-f]{64}$ ]] || hold "invalid reviewed configuration fingerprint"
config_hash=$(sha256sum "$CONFIG") || hold "configuration verification unavailable"
[[ ${config_hash%% *} == "$expected_config" ]] || hold "configuration changed"

# A host maintenance operation and every cooperating guarded launch use the same
# persistent inode. Never recreate/unlink this file or close FD9 before vendor exit:
# the read-only bind permits flock without giving egress permission to change it.
# This excludes cooperating starts, not a privileged operator bypassing the guard.
exec 9< "$START_LOCK" || hold "startup lock unavailable"
flock --exclusive --nonblock 9 || hold "recorder startup or maintenance already active"
# Check durable intent AFTER acquiring the lock. Checking before it would let a
# paused launch overlook an operation written by a maintainer that then crashed.
opened_lock=$(stat -Lc '%d:%i' /proc/self/fd/9) || hold "startup lock inspection failed"
current_lock=$(stat -Lc '%d:%i' "$START_LOCK") || hold "startup lock inspection failed"
[[ ! -L $START_LOCK && $opened_lock == "$current_lock" ]] || hold "startup lock replaced"
[[ ! -s /proc/self/fd/9 ]] || hold "unfinished recorder preservation"

# The upstream script ignores failed EG_* backup copies and then clears tmp.
# Refuse ALL residual entries (also hidden files/symlinks), rather than treating
# a failed upload or a partial copy as safe. No backup/delete/recovery is attempted.
[[ -d $RECOVERY_ROOT && ! -L $RECOVERY_ROOT ]] || hold "recovery root unavailable"
for directory in "$RECOVERY_ROOT/tmp" "$RECOVERY_ROOT/backup_storage"; do
  [[ -d $directory && ! -L $directory && -r $directory && -x $directory ]] \
    || hold "recovery directory unavailable"
  entry=$(find "$directory" -mindepth 1 -maxdepth 1 -print -quit) \
    || hold "recovery inventory unavailable"
  [[ -z $entry ]] || hold "unresolved recovery artifacts"
done

# Preserve the vendor's non-root PulseAudio initialization and exec/tini chain.
# Docker's independent restart policy re-enters this guard; do not restart the
# shared Compose/systemd stack to recover an individual recorder.
exec "$ENTRYPOINT"
