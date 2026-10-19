#!/usr/bin/env bash
set -Eeuo pipefail

# Dexhit Collection Launchpad 一键启动脚本。
# 只启动本机网页控制面，不自动启动业务节点，也不调用 arm。

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
# shellcheck source=workspace_paths.sh
source "$SCRIPT_DIR/workspace_paths.sh"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
PYTHON_SITE="$ROOT_DIR/.venv/lib/python3.12/site-packages"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
WORKSPACE_SETUP="$ROTRAC_INSTALL_BASE/setup.bash"
LAUNCHPAD_SRC="$ROOT_DIR/src/rokoko_omnihand_launchpad_node"
URL="http://127.0.0.1:8710"

die() {
  echo "[Launchpad] 错误：$*" >&2
  exit 1
}

[[ -x "$PYTHON_BIN" ]] || die "找不到 .venv 数值 Python：$PYTHON_BIN"
[[ -f "$ROS_SETUP" ]] || die "找不到 ROS Jazzy 环境：$ROS_SETUP"
[[ -d "$LAUNCHPAD_SRC/rokoko_omnihand_launchpad" ]] || die "找不到 Launchpad 源码：$LAUNCHPAD_SRC"

# ROS 的 Debian Python 包与 .venv 数值环境并存。将 .venv site-packages 放在
# ROS 系统 site-packages 之前，避免数值栈版本被系统包覆盖；
# 同时保留 rclpy、fastapi 等系统依赖。
export PYTHONPATH="$PYTHON_SITE:/opt/ros/jazzy/lib/python3.12/site-packages:/usr/lib/python3/dist-packages:$LAUNCHPAD_SRC${PYTHONPATH:+:$PYTHONPATH}"

# 加载 ROS Jazzy，使 Launchpad 后续编排的 ros2 命令可见。
# shellcheck disable=SC1090
set +u
source "$ROS_SETUP"
if [[ -f "$WORKSPACE_SETUP" ]]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_SETUP"
fi
set -u

export PYTHONPATH="$LAUNCHPAD_SRC${PYTHONPATH:+:$PYTHONPATH}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/rotrac-ros-log}"
mkdir -p "$ROS_LOG_DIR"
cd "$ROOT_DIR"

"$PYTHON_BIN" - <<'PY'
for name in ("fastapi", "uvicorn", "click", "yaml", "rclpy", "pinocchio", "nlopt"):
    try:
        __import__(name)
    except Exception as exc:
        raise SystemExit(f"依赖检查失败：{name}: {exc}")
PY

echo "[Launchpad] 环境已就绪：$PYTHON_BIN"
echo "[Launchpad] 控制面地址：$URL"
echo "[Launchpad] 仅启动网页控制面；不会自动启动业务节点或 arm 灵巧手。"

if command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  (sleep 1; xdg-open "$URL" >/dev/null 2>&1) &
fi

exec "$PYTHON_BIN" -m rokoko_omnihand_launchpad
