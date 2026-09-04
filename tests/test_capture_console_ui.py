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
