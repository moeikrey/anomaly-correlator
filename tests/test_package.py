"""Phase 0 sanity test: the package installs and imports."""

import ghostbadge


def test_package_imports_and_has_version() -> None:
    assert ghostbadge.__version__
