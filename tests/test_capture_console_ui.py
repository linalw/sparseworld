from pathlib import Path


def test_console_assets_exist_and_reference_api():
    static = Path(__file__).parents[1] / "src" / "sparseworld_p0" / "static"
    html = (static / "capture_console.html").read_text(encoding="utf-8")
    js = (static / "capture_console.js").read_text(encoding="utf-8")
    assert "capture_console.css" in html and "capture_console.js" in html
    assert "/api/status" in js and "/api/start" in js and "/api/stop" in js
    assert "不控制底盘" in html
    assert "实时稀疏建图" in html
    assert "debug-bag" in html
    assert "slam_status" in js
    assert "semantic-canvas" in html
    assert "/api/map/state" in js
    assert "pointerdown" in js and "wheel" in js and "keydown" in js
    assert "对象图片" in html
    assert "image-mode" in js
    assert "/api/plan" in js
    assert "第一视角漫游路径" in html
    assert "inspector" in html and "route" in js


def test_explorer_has_distinct_trajectory_route_and_object_layers():
    static = Path(__file__).parents[1] / "src" / "sparseworld_p0" / "static"
    html = (static / "capture_console.html").read_text(encoding="utf-8")
    js = (static / "capture_console.js").read_text(encoding="utf-8")
    css = (static / "capture_console.css").read_text(encoding="utf-8")
    assert "legend-route" in html
    assert "trajectory" in js and "plannedRoute" in js
    assert "strokeStyle='#79adff'" in js
    assert "strokeStyle='#f5b942'" in js
    assert "fillStyle='#65e6bf'" in js
    assert "data-kind" in js
    assert "legend-route" in css


def test_explorer_supports_click_inspector_and_replay_exit():
    static = Path(__file__).parents[1] / "src" / "sparseworld_p0" / "static"
    html = (static / "capture_console.html").read_text(encoding="utf-8")
    js = (static / "capture_console.js").read_text(encoding="utf-8")
    assert "退出漫游" in html
    assert "click" in js
    assert "showInspector" in js
    assert "replayCamera" in js
    assert "/cmd_vel" not in js
