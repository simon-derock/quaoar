# the installed package reports the version pyproject declares
import quaoar


def test_version_matches_pyproject() -> None:
    assert quaoar.__version__ == "0.1.0"
