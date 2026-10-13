"""Structural guard for the direct launcher's HCAN device-id knobs.

The historical dual-adapter workstation maps left=Device 1 / right=Device 0.
Single-adapter stations only expose Device 0, so the launcher must read both
indices from environment overrides with those defaults instead of hard-coded
literals inside the ros2-run argument list.
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]
LAUNCHER = ROOT / "scripts" / "start_omnihand_control.sh"
RIGHT_ONE_CLICK = ROOT.parents[2] / "scripts" / "start_omnihand_right_low_latency.sh"


def _launcher_text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_left_canfd_device_id_is_env_overridable_with_workstation_default():
    text = _launcher_text()
    assert 'LEFT_CANFD_DEVICE_ID="${OMNIHAND_O10_LEFT_CANFD_DEVICE_ID:-1}"' in text
    # No hard-coded numeric device index for left outside the default above.
    assert "-p o10.left.canfd_device_id:=1" not in text
    assert "-p o10.left.canfd_device_id:=0" not in text


def test_right_canfd_device_id_is_env_overridable_with_workstation_default():
    text = _launcher_text()
    assert 'RIGHT_CANFD_DEVICE_ID="${OMNIHAND_O10_RIGHT_CANFD_DEVICE_ID:-0}"' in text
    # No hard-coded numeric device index for right outside the default above.
    assert "-p o10.right.canfd_device_id:=1" not in text
    assert "-p o10.right.canfd_device_id:=0" not in text


def test_provider_arguments_use_the_expandable_knobs():
    text = _launcher_text()
    assert '-p "o10.left.canfd_device_id:=$LEFT_CANFD_DEVICE_ID"' in text
    assert '-p "o10.right.canfd_device_id:=$RIGHT_CANFD_DEVICE_ID"' in text


def test_provider_receives_the_selected_sides():
    text = _launcher_text()
    provider_block = text.split("PROVIDER_PARAMS=(", 1)[1].split("sleep 2", 1)[0]
    assert '-p "sides:=$SIDES"' in provider_block


def test_usage_documents_the_single_adapter_override():
    usage = _launcher_text().split("EOF", 1)[1]
    assert "OMNIHAND_O10_LEFT_CANFD_DEVICE_ID" in usage


def test_launcher_supports_explicit_post_start_tactile_rate():
    text = _launcher_text()
    assert "--tactile-rate HZ" in text
    assert 'start_tactile_stream()' in text
    startup = text.split("wait_for_node /o10_control_node", 1)[1]
    assert "start_tactile_stream right" in startup


def test_right_one_click_starts_tactile_at_30_hz():
    text = RIGHT_ONE_CLICK.read_text(encoding="utf-8")
    assert "--sides right --tactile-rate 30" in text
    # 2026-10-04 低时延调整：触觉仍锁 30 Hz，SDK 全局请求间隔改为不限速（0）。
    assert "o10.right.request_interval_ms=0" in text
