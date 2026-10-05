"""Central place to read API keys.

Order of lookup:
1. Streamlit secrets  (.streamlit/secrets.toml locally, or Settings -> Secrets on Streamlit Cloud)
2. Environment variables / .env file

This means the same code works locally, on Streamlit Cloud and in the FastAPI backend.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv is optional
    pass


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        # No secrets file / not running inside Streamlit -> fall back to env vars
        pass

    value = os.getenv(name)
    if value and value.strip():
        return value.strip()

    return default