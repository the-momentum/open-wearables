from pydantic import BaseModel, Field


class ExtensionInfo(BaseModel):
    name: str
    display_name: str = ""
    version: str = ""
    requires_core: str = Field(default="", description="PEP 440 specifier of the core versions it supports.")
    active: bool
    error: str | None = Field(default=None, description="Why an installed extension is not active.")


class ExtensionsResponse(BaseModel):
    core_version: str
    extensions: list[ExtensionInfo]
