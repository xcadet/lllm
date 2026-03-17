"""
conftest for live integration tests.

Keys are loaded in this order (first found wins for each key):
  1. .env file in the project root (or LLLM_ENV_FILE env var)
  2. Shell environment (os.environ)

Tests are **skipped automatically** when the required key is absent or the
initial API call fails with an auth error.
"""
import os
import pytest

# ── Load .env ──────────────────────────────────────────────────────────────
# python-dotenv: silently does nothing if the file doesn't exist
try:
    from dotenv import load_dotenv

    _env_file = os.environ.get("LLLM_ENV_FILE", ".env")
    load_dotenv(_env_file, override=False)  # don't overwrite already-set vars
except ImportError:
    pass  # dotenv not installed – rely on shell environment


# ── Helpers ────────────────────────────────────────────────────────────────

def _key(name: str) -> str | None:
    return os.environ.get(name) or None


# ── Pytest markers / skip conditions ──────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "live: live integration test (requires API key)")
    config.addinivalue_line("markers", "openai: requires OPENAI_API_KEY")
    config.addinivalue_line("markers", "anthropic: requires ANTHROPIC_API_KEY")


# ── Session-scoped fixtures ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def openai_key():
    key = _key("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set – skipping live OpenAI tests")
    return key


@pytest.fixture(scope="session")
def anthropic_key():
    key = _key("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set – skipping live Anthropic tests")
    return key


# ── Cheap "probe" fixtures – skip on auth errors ──────────────────────────

@pytest.fixture(scope="session")
def openai_available(openai_key):
    """Verifies the key actually works; skips otherwise."""
    import litellm

    try:
        resp = litellm.completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=3,
        )
        assert resp.choices
        return True
    except Exception as exc:
        pytest.skip(f"OpenAI key invalid or quota exhausted: {exc}")


@pytest.fixture(scope="session")
def anthropic_available(anthropic_key):
    """Verifies the key actually works; skips otherwise."""
    import litellm

    try:
        resp = litellm.completion(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=3,
        )
        assert resp.choices
        return True
    except Exception as exc:
        pytest.skip(f"Anthropic key invalid or quota exhausted: {exc}")
