from pathlib import Path


def test_launcher_initialises_ament_trace_variable_before_ros_setup():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert 'export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"' in script
    assert script.index("export AMENT_TRACE_SETUP_FILES") < script.index("source /opt/ros/humble/setup.bash")
