import os
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

load_dotenv()

_client: TwelveLabs | None = None


def get_client() -> TwelveLabs:
    """Return a shared TwelveLabs client, initializing it once."""
    global _client
    if _client is None:
        api_key = os.getenv("TWELVELABS_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "TWELVELABS_API_KEY not found. "
                "Set it in your .env file or environment."
            )
        _client = TwelveLabs(api_key=api_key.strip())
    return _client
