from pathlib import Path


def test_launcher_initialises_ament_trace_variable_before_ros_setup():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert "set +u" in script
    assert script.index("set +u") < script.index("source /opt/ros/humble/setup.bash")


def test_launcher_sources_ros_setup_with_nounset_temporarily_disabled():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert "set +u" in script
    assert "set -u" in script


def test_launcher_installs_socks_support_when_a_socks_proxy_is_configured():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert '"${ALL_PROXY:-}" == socks5://*' in script
    assert "import socksio" in script


def test_launcher_migrates_old_blip_default_to_florence_two():
    script = (Path(__file__).parents[1] / "scripts" / "start_live_semantic.sh").read_text()
    assert '"Salesforce/blip-image-captioning-base"' in script
    assert "microsoft/Florence-2-base" in script
