from pathlib import Path


def test_launcher_initialises_ament_trace_variable_before_ros_setup():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert "set +u" in script
    assert script.index("set +u") < script.index("source /opt/ros/humble/setup.bash")


def test_launcher_sources_ros_setup_with_nounset_temporarily_disabled():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert "set +u" in script
    assert "set -u" in script
