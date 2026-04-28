import ipaddress

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    callback_url: AnyHttpUrl

    @field_validator("callback_url")
    @classmethod
    def _no_private_callback(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        host = v.host
        if host is None:
            raise ValueError("callback_url must have a host")
        try:
            addr = ipaddress.ip_address(host)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                raise ValueError("callback_url must not point to a private or internal address")
        except ValueError as exc:
            # host is a domain name — re-raise only our own errors, not the ip_address parse error.
            # Known limitation: domain names that resolve to private IPs are not blocked here.
            # DNS-rebinding mitigation is expected to be handled at the network/firewall layer.
            if "callback_url" in str(exc):
                raise
        return v


class ChatTaskResponse(BaseModel):
    task_id: str
