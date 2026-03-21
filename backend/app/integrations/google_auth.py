import httpx

_GOOGLE_METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
_GOOGLE_METADATA_HEADERS = {"Metadata-Flavor": "Google"}


def get_google_access_token() -> str:
    response = httpx.get(_GOOGLE_METADATA_TOKEN_URL, headers=_GOOGLE_METADATA_HEADERS, timeout=5.0)
    response.raise_for_status()
    token_payload = response.json()
    access_token = token_payload.get("access_token")
    if not access_token:
        raise ValueError("Google metadata server did not return an access token")
    return access_token
