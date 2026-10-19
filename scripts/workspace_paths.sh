#!/usr/bin/env bash
# Colcon bases for this worktree.
#
# The repository path contains non-ASCII characters. CMake file(STRINGS), used
# by rosidl_adapt_interfaces, splits generated lines at non-ASCII bytes, so
# interface generation fails when the build path also contains them. Keep every
# generated artifact under an ASCII base and leave the source tree untouched.
#
# Override the base with ROTRAC_COLCON_BASE. The default intentionally lives
# outside the repository so a clean checkout never inherits stale artifacts.

ROTRAC_COLCON_BASE="${ROTRAC_COLCON_BASE:-$HOME/rotrac-build}"

if [[ -z "$ROTRAC_COLCON_BASE" ]]; then
    echo "[workspace] ERROR: ROTRAC_COLCON_BASE is empty" >&2
    return 1 2>/dev/null || exit 1
fi
if printf '%s' "$ROTRAC_COLCON_BASE" | LC_ALL=C grep -q '[^ -~]'; then
    echo "[workspace] ERROR: ROTRAC_COLCON_BASE must be ASCII: $ROTRAC_COLCON_BASE" >&2
    return 1 2>/dev/null || exit 1
fi

ROTRAC_BUILD_BASE="$ROTRAC_COLCON_BASE/build"
ROTRAC_INSTALL_BASE="$ROTRAC_COLCON_BASE/install"
ROTRAC_LOG_BASE="$ROTRAC_COLCON_BASE/log"
ROTRAC_TEST_RESULT_BASE="$ROTRAC_BUILD_BASE"

export ROTRAC_COLCON_BASE ROTRAC_BUILD_BASE ROTRAC_INSTALL_BASE \
    ROTRAC_LOG_BASE ROTRAC_TEST_RESULT_BASE
