"""
Verifies .env.example documents every required env var with a description.
Each line must be either a comment (#), blank, or VAR=description format.
Required vars are defined here as the canonical list.
"""

from pathlib import Path

ENV_EXAMPLE = Path(__file__).parents[2] / ".env.example"

REQUIRED_VARS = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "ANTHROPIC_API_KEY",
]


def _parse_env_example() -> dict[str, str]:
    """Returns {VAR_NAME: description_value} for all non-comment, non-blank lines."""
    result: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "=" in line, f"Malformed line (no '='): {line!r}"
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def test_env_example_exists():
    assert ENV_EXAMPLE.exists(), ".env.example not found at repo root"


def test_required_vars_are_documented():
    documented = _parse_env_example()
    missing = [v for v in REQUIRED_VARS if v not in documented]
    assert not missing, f"Missing from .env.example: {missing}"


def test_all_vars_have_descriptions():
    documented = _parse_env_example()
    empty = [k for k, v in documented.items() if not v]
    assert not empty, f"Vars with no description: {empty}"
