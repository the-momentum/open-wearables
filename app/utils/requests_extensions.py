from requests import PreparedRequest
from requests.auth import AuthBase


class BearerAuth(AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r: PreparedRequest):
        r.headers["Authorization"] = "Bearer " + self.token
        return r
