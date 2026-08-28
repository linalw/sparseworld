from subprocess import CompletedProcess

from sparseworld_p0.discovery import discover_environment


def test_marks_missing_ros2_as_not_installed_and_stays_read_only(tmp_path) -> None:
    """This catches discovery incorrectly treating an absent executable as success."""
    def runner(command: list[str]) -> CompletedProcess[str]:
        if command == ["ros2", "--version"]:
            return CompletedProcess(command, 127, "", "ros2: command not found")
        return CompletedProcess(command, 0, "fixture-output\n", "")

    snapshot = discover_environment(runner, tmp_path)

    assert snapshot["collection_mode"] == "read_only"
    assert snapshot["software"]["ros2"]["status"] == "not_installed"


def test_marks_missing_orbbec_python_module_as_not_installed(tmp_path) -> None:
    """This catches missing SDK modules being reported as ambiguous detection failures."""
    def runner(command: list[str]) -> CompletedProcess[str]:
        if command[0] == "python" and "pyorbbecsdk" in command[-1]:
            return CompletedProcess(command, 1, "", "ModuleNotFoundError: No module named 'pyorbbecsdk'")
        return CompletedProcess(command, 0, "fixture-output\n", "")

    snapshot = discover_environment(runner, tmp_path)

    assert snapshot["software"]["pyorbbecsdk"]["status"] == "not_installed"
