import package_name
from package_name import hello


def test_hello_returns_greeting() -> None:
    expected = "Hello from package-name!"

    assert hello() == expected


def test_package_exports_only_public_api() -> None:
    assert package_name.__all__ == ["hello"]
