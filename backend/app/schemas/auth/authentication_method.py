from enum import StrEnum

class AuthenticationMethod(StrEnum):
    """Method used for client authentication."""

    BASIC_AUTH = "basic_auth"
    BODY = "body"