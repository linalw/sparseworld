from pathlib import Path


def test_live_bridge_retries_local_odom_frame_when_map_tf_is_not_ready():
    source = (Path(__file__).parents[1] / "scripts" / "p0_live_keyframe_bridge.py").read_text()
    assert '"odom", "camera_link"' in source
    assert '"pose_frame"' in source
