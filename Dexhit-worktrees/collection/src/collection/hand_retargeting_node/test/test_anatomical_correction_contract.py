"""Model-free contracts for the per-side anatomical correction."""

from __future__ import annotations

from hand_retargeting.application.session import FINGER_ACTIVE_INDICES
from hand_retargeting.core.anatomical_correction import (
    correct_anatomical_human_vector,
)
from omnihand_o10_contracts import ACTIVE_JOINT_NAMES, JOINT_LIMITS, Side
import pytest


def test_left_anatomical_correction_reflects_only_lateral_axis():
    """Left correction flips X only; human palm normal and length axes persist."""
    vector = (0.25, -0.5, 0.75)
    assert correct_anatomical_human_vector(Side.LEFT, 0, vector) == (
        -0.25, -0.5, 0.75
    )
    assert correct_anatomical_human_vector(Side.LEFT, 4, vector) == (
        -0.25, -0.5, 0.75
    )


def test_right_thumb_anatomical_correction_reflects_palm_normal_axis():
    """Right thumb opposition uses the corrected Rokoko palm-normal sign."""
    vector = (0.25, -0.5, 0.75)
    assert correct_anatomical_human_vector(Side.RIGHT, 0, vector) == (
        0.25, -0.5, -0.75
    )


def test_right_four_finger_correction_reflects_palm_normal_axis():
    """Right four-finger flexion uses the opposite Rokoko palm-normal sign."""
    vector = (0.25, -0.5, 0.75)
    for finger_index in (1, 2, 3, 4):
        assert correct_anatomical_human_vector(Side.RIGHT, finger_index, vector) == (
            0.25, -0.5, -0.75
        )


def test_middle_has_no_fake_abad_and_only_one_active_degree_of_freedom():
    """Freeze the verified O10 structure: middle is PIP-only."""
    assert FINGER_ACTIVE_INDICES[2] == (5,)
    assert ACTIVE_JOINT_NAMES[5] == "middle_pip"
    assert "middle_abad" not in ACTIVE_JOINT_NAMES
    assert JOINT_LIMITS[Side.LEFT].lower[5] == pytest.approx(0.0)
    assert JOINT_LIMITS[Side.LEFT].upper[5] == pytest.approx(1.4835298641951802)
