#!/usr/bin/env python3
"""Offline analysis of a DexTwist diagnostic MCAP recording.

The recorder writes one independent run directory per launch. This tool reads
the ``twist_state`` topic from that MCAP and produces the first-version
acceptance metrics:

* robot angle vs human intent: RMSE, MAE and Pearson correlation of
  ``theta_robot_fb - theta_increment`` (and the command-side equivalent);
* feedback axis deviation mean/max;
* refinement applied/fallback proportions and failure-reason distribution;
* negative-sample gate false-trigger rate for operator-supplied windows;
* per-frame CSV for debugging and regression.

Time alignment uses message ``header.stamp``. Negative-sample windows are
seconds relative to the first recorded ``TwistState`` header stamp for the side.

The object's actual rotation is NOT measured. This tool can only judge the
robot-vs-human-command loop, never whether the object turned or slipped.

Usage:
    python3 scripts/analyze_twist_diagnosis.py runs/twist-diag/<run> --side left
    python3 scripts/analyze_twist_diagnosis.py <bag> --side both \
        --negative-window 0:120 --negative-window 180:300

Offline only: no node is started, no command is published and no hardware is
touched. Requires the ROS environment so the generated message modules are
importable.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Iterable, Sequence


_STATUS_NAMES = {
    0: "not_active",
    1: "applied",
    2: "fallback_baseline",
}
_FAILURE_NAMES = {
    0: "none",
    1: "robot_reference_invalid",
    2: "human_reference_invalid",
    3: "human_geometry_invalid",
    4: "backend_unavailable",
    5: "solver_error",
    6: "nonfinite",
    7: "limits",
    8: "trust_region",
    9: "degenerate_tripod",
    10: "axis_deviation",
    11: "baseline_incomplete",
    12: "refinement_rejected",
    13: "axis_mismatch",
}

_FRAME_COLUMNS = (
    "stamp_ns",
    "valid",
    "active",
    "gate_aperture",
    "gate_extension",
    "gate_on_count",
    "gate_off_count",
    "theta_task",
    "theta_base",
    "theta_increment",
    "theta_robot_cmd",
    "theta_robot_fb",
    "theta_robot_fb_available",
    "axis_deviation_cmd_deg",
    "axis_deviation_fb_deg",
    "axis_deviation_fb_available",
    "objective_total",
    "objective_rot",
    "objective_conn",
    "objective_axis",
    "objective_pos",
    "refinement_status",
    "failure_reason",
    "iterations",
    "evaluations",
    "solve_duration_sec",
)


def _stamp_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def frame_from_message(message) -> dict:
    """Convert one TwistState message into a plain analysis row."""
    return {
        "stamp_ns": _stamp_ns(message.header.stamp),
        "valid": bool(message.valid),
        "active": bool(message.active),
        "gate_aperture": float(message.gate_aperture),
        "gate_extension": float(message.gate_extension),
        "gate_on_count": int(message.gate_on_count),
        "gate_off_count": int(message.gate_off_count),
        "theta_task": float(message.theta_task),
        "theta_base": float(message.theta_base),
        "theta_increment": float(message.theta_increment),
        "theta_robot_cmd": float(message.theta_robot_cmd),
        "theta_robot_fb": float(message.theta_robot_fb),
        "theta_robot_fb_available": bool(message.theta_robot_fb_available),
        "axis_deviation_cmd_deg": float(message.axis_deviation_cmd_deg),
        "axis_deviation_fb_deg": float(message.axis_deviation_fb_deg),
        "axis_deviation_fb_available": bool(
            message.axis_deviation_fb_available
        ),
        "objective_total": float(message.objective_total),
        "objective_rot": float(message.objective_rot),
        "objective_conn": float(message.objective_conn),
        "objective_axis": float(message.objective_axis),
        "objective_pos": float(message.objective_pos),
        "refinement_status": _STATUS_NAMES.get(
            int(message.refinement_status), str(message.refinement_status)
        ),
        "failure_reason": _FAILURE_NAMES.get(
            int(message.failure_reason), str(message.failure_reason)
        ),
        "iterations": int(message.iterations),
        "evaluations": int(message.evaluations),
        "solve_duration_sec": float(message.solve_duration_sec),
    }


def read_frames(bag_path: Path, side: str) -> list[dict]:
    """Read one side's TwistState topic from an MCAP bag."""
    try:
        from rclpy.serialization import deserialize_message
        from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
        from rokoko_omnihand_msgs.msg import TwistState
    except ImportError as error:  # pragma: no cover - environment gate
        raise RuntimeError(
            "analysis requires the ROS environment (rosbag2_py, generated msgs)"
        ) from error

    topic = f"/hand_retargeting/{side}/twist_state"
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag_path), storage_id="mcap"),
        ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    available = {entry.name for entry in reader.get_all_topics_and_types()}
    if topic not in available:
        raise RuntimeError(f"topic missing from recording: {topic}")
    frames = []
    while reader.has_next():
        name, data, _timestamp = reader.read_next()
        if name != topic:
            continue
        frames.append(frame_from_message(deserialize_message(data, TwistState)))
    return frames


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _rmse(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _mae(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(abs(value) for value in values) / len(values)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Return Pearson r, or None when it is undefined."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)
    )
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_x <= 0.0 or variance_y <= 0.0:
        return None
    return covariance / math.sqrt(variance_x * variance_y)


def _parse_windows(values: Iterable[str]) -> list[tuple[float, float]]:
    windows = []
    for value in values:
        try:
            start_raw, end_raw = value.split(":", 1)
            start, end = float(start_raw), float(end_raw)
        except ValueError as error:
            raise ValueError(
                f"negative window must be START:END seconds, got {value!r}"
            ) from error
        if not (math.isfinite(start) and math.isfinite(end) and start <= end):
            raise ValueError(f"invalid negative window: {value!r}")
        windows.append((start, end))
    return windows


def summarize(
    frames: Sequence[dict],
    side: str,
    negative_windows: Sequence[tuple[float, float]] = (),
) -> dict:
    """Compute all first-version metrics from plain frame rows."""
    active = [frame for frame in frames if frame["active"]]
    valid = [frame for frame in frames if frame["valid"]]
    fb_pairs = [
        (frame["theta_robot_fb"], frame["theta_increment"])
        for frame in active
        if frame["theta_robot_fb_available"]
        and _finite(frame["theta_robot_fb"])
        and _finite(frame["theta_increment"])
    ]
    cmd_pairs = [
        (frame["theta_robot_cmd"], frame["theta_increment"])
        for frame in active
        if _finite(frame["theta_robot_cmd"])
        and _finite(frame["theta_increment"])
    ]
    fb_errors = [fb - increment for fb, increment in fb_pairs]
    cmd_errors = [cmd - increment for cmd, increment in cmd_pairs]
    fb_axis = [
        frame["axis_deviation_fb_deg"]
        for frame in active
        if frame["axis_deviation_fb_available"]
        and _finite(frame["axis_deviation_fb_deg"])
    ]
    cmd_axis = [
        frame["axis_deviation_cmd_deg"]
        for frame in active
        if _finite(frame["axis_deviation_cmd_deg"])
    ]

    status_counts = {}
    for frame in active:
        status_counts[frame["refinement_status"]] = (
            status_counts.get(frame["refinement_status"], 0) + 1
        )
    failure_counts = {}
    for frame in active:
        reason = frame["failure_reason"]
        if reason != "none":
            failure_counts[reason] = failure_counts.get(reason, 0) + 1
    applied = status_counts.get("applied", 0)
    fallback = status_counts.get("fallback_baseline", 0)

    gate = {
        "available": False,
        "windows": [],
        "note": "no negative windows supplied",
    }
    if negative_windows:
        base_ns = frames[0]["stamp_ns"] if frames else 0
        gate_frames = 0
        gate_active = 0
        episodes = 0
        windows = []
        for start, end in negative_windows:
            selected = [
                frame
                for frame in frames
                if frame["valid"]
                and _finite(frame["gate_aperture"])
                and start
                <= (frame["stamp_ns"] - base_ns) / 1e9
                <= end
            ]
            active_selected = [frame for frame in selected if frame["active"]]
            window_episodes = 0
            previous = False
            for frame in selected:
                if frame["active"] and not previous:
                    window_episodes += 1
                previous = frame["active"]
            gate_frames += len(selected)
            gate_active += len(active_selected)
            episodes += window_episodes
            windows.append(
                {
                    "start_sec": start,
                    "end_sec": end,
                    "valid_frames": len(selected),
                    "active_frames": len(active_selected),
                    "activation_episodes": window_episodes,
                    "false_trigger_rate": (
                        len(active_selected) / len(selected) if selected else None
                    ),
                }
            )
        gate = {
            "available": True,
            "windows": windows,
            "valid_frames": gate_frames,
            "active_frames": gate_active,
            "false_trigger_rate": (
                gate_active / gate_frames if gate_frames else None
            ),
            "activation_episodes": episodes,
        }

    return {
        "side": side,
        "frame_count": len(frames),
        "valid_frame_count": len(valid),
        "active_frame_count": len(active),
        "active_frame_ratio": len(active) / len(valid) if valid else None,
        "feedback_available_ratio": (
            len(fb_pairs) / len(active) if active else None
        ),
        "angle_feedback": {
            "available": bool(fb_errors),
            "sample_count": len(fb_errors),
            "rmse_rad": _rmse(fb_errors),
            "mae_rad": _mae(fb_errors),
            "pearson": pearson(
                [pair[0] for pair in fb_pairs],
                [pair[1] for pair in fb_pairs],
            ),
        },
        "angle_command": {
            "available": bool(cmd_errors),
            "sample_count": len(cmd_errors),
            "rmse_rad": _rmse(cmd_errors),
            "mae_rad": _mae(cmd_errors),
            "pearson": pearson(
                [pair[0] for pair in cmd_pairs],
                [pair[1] for pair in cmd_pairs],
            ),
        },
        "axis_deviation_feedback_deg": {
            "available": bool(fb_axis),
            "sample_count": len(fb_axis),
            "mean": sum(fb_axis) / len(fb_axis) if fb_axis else None,
            "max": max(fb_axis) if fb_axis else None,
        },
        "axis_deviation_command_deg": {
            "available": bool(cmd_axis),
            "sample_count": len(cmd_axis),
            "mean": sum(cmd_axis) / len(cmd_axis) if cmd_axis else None,
            "max": max(cmd_axis) if cmd_axis else None,
        },
        "refinement": {
            "applied_frames": applied,
            "fallback_frames": fallback,
            "applied_ratio": applied / len(active) if active else None,
            "fallback_ratio": fallback / len(active) if active else None,
            "status_counts": status_counts,
            "failure_reason_counts": failure_counts,
        },
        "negative_gate": gate,
        "time_alignment": (
            "message header.stamp; negative windows are seconds relative to "
            "the first recorded TwistState header stamp for this side"
        ),
        "object_rotation_measured": False,
        "object_rotation_note": (
            "物体实际转角未测。本报告只验收机器人关节转角 vs 人手意图和轴偏差，"
            "不能证明物体被拧动或没有滑移。"
        ),
    }


def write_frames_csv(frames: Sequence[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FRAME_COLUMNS)
        writer.writeheader()
        for frame in frames:
            writer.writerow({name: frame.get(name) for name in _FRAME_COLUMNS})


def _resolve_bag(path: Path) -> Path:
    if (path / "bag").is_dir():
        return path / "bag"
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "run",
        help="twist-diag run directory or a rosbag2/MCAP directory",
    )
    parser.add_argument(
        "--side", default="left", choices=("left", "right", "both")
    )
    parser.add_argument(
        "--negative-window",
        action="append",
        default=[],
        help="negative-sample window START:END in seconds (repeatable)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="summary/CSV destination (default: the run directory)",
    )
    arguments = parser.parse_args(argv)

    run_path = Path(arguments.run).expanduser()
    if not run_path.exists():
        raise SystemExit(f"run path does not exist: {run_path}")
    bag_path = _resolve_bag(run_path)
    output_dir = (
        Path(arguments.output_dir).expanduser()
        if arguments.output_dir
        else (run_path if run_path.is_dir() and (run_path / "bag").is_dir() else bag_path.parent)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    windows = _parse_windows(arguments.negative_window)
    sides = ("left", "right") if arguments.side == "both" else (arguments.side,)

    combined = {}
    for side in sides:
        frames = read_frames(bag_path, side)
        summary = summarize(frames, side, windows)
        summary_path = output_dir / f"summary_{side}.json"
        csv_path = output_dir / f"frames_{side}.csv"
        summary_path.write_text(
            json.dumps(summary, indent=2, allow_nan=True) + "\n",
            encoding="utf-8",
        )
        write_frames_csv(frames, csv_path)
        combined[side] = summary
        print(f"[twist-analyze] {side}: {summary_path}")
        print(f"[twist-analyze] {side}: {csv_path}")

    if len(combined) > 1:
        combined_path = output_dir / "summary.json"
        combined_path.write_text(
            json.dumps(
                {
                    "sides": combined,
                    "object_rotation_measured": False,
                    "object_rotation_note": combined["left"]["object_rotation_note"],
                },
                indent=2,
                allow_nan=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"[twist-analyze] combined: {combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
