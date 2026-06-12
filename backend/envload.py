"""Optional .env loading. Real environment variables always take precedence (load_dotenv
does not override), and a missing python-dotenv or .env file is a silent no-op so the
offline demo and CI keep working with zero configuration."""

from __future__ import annotations


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)
