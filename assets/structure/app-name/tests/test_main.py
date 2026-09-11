from main import greeting


def test_greeting_returns_app_greeting() -> None:
    assert greeting() == "Hello from app-name!"
