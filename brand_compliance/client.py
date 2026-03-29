import os
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

load_dotenv()

_client: TwelveLabs | None = None


def get_client(api_key: str | None = None) -> TwelveLabs:
    """
    Return a TwelveLabs client.

    If api_key is provided (per-request user key), a fresh client is returned.
    Otherwise the module-level singleton is used (env var fallback).
    """
    if api_key:
        return TwelveLabs(api_key=api_key.strip())

    global _client
    if _client is None:
        env_key = os.getenv("TWELVELABS_API_KEY", "").strip()
        if not env_key:
            raise EnvironmentError(
                "No TwelveLabs API key provided. "
                "Pass one in the X-TwelveLabs-Key header or set TWELVELABS_API_KEY in .env."
            )
        _client = TwelveLabs(api_key=env_key)
    return _client
