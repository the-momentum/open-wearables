from pydantic import Field
from pydantic_settings import BaseSettings


class LoadTestSettings(BaseSettings):
    email: str = Field(default="", alias="LOAD_TEST_EMAIL")
    password: str = Field(default="", alias="LOAD_TEST_PASSWORD")
    api_key: str = Field(default="", alias="LOAD_TEST_API_KEY")
    user_id: str = Field(default="", alias="LOAD_TEST_USER_ID")

    model_config = {"populate_by_name": True}


settings = LoadTestSettings()
