from importlib.metadata import version


def test_package_exposes_a_version() -> None:
    assert version("sparseworld-p0") == "0.1.0"
