from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_is_ament_python_and_uses_standard_tactile_image():
    package_xml = (PACKAGE_ROOT / "package.xml").read_text(encoding="utf-8")
    setup_py = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    assert "<name>omnihand_o10_hardware_adapter</name>" in package_xml
    assert "<build_type>ament_python</build_type>" in package_xml
    assert "<depend>omnihand_o10_contracts</depend>" in package_xml
    assert "<depend>sensor_msgs</depend>" in package_xml
    assert "omnihand_2025_node_msgs" not in package_xml
    assert "omnihand_node" not in package_xml
    assert "sdk" not in package_xml.lower()
    assert "setup(" in setup_py
