from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Entidad de Registro RA"
    environment: str = "dev"
    ra_api_key: str = Field(default="change-me", alias="RA_API_KEY")

    openssl_bin: str = Field(default="openssl", alias="OPENSSL_BIN")
    openssl_ca_config: str = Field(alias="OPENSSL_CA_CONFIG")
    openssl_ca_profile: str = Field(default="usr_cert", alias="OPENSSL_CA_PROFILE")
    openssl_ca_workdir: Path = Field(alias="OPENSSL_CA_WORKDIR")
    ec_mode: str = Field(default="local", alias="EC_MODE")
    ec_api_url: str | None = Field(default=None, alias="EC_API_URL")
    ec_source_system: str = Field(default="ER-DEMO", alias="EC_SOURCE_SYSTEM")
    ec_shared_secret: str | None = Field(default=None, alias="EC_SHARED_SECRET")
    ec_hmac_secret: str | None = Field(default=None, alias="EC_HMAC_SECRET")
    ec_http_timeout: int = Field(default=30, alias="EC_HTTP_TIMEOUT")
    ec_security_officer: str = Field(default="oficial", alias="EC_SECURITY_OFFICER")
    ec_organization: str = Field(default="ER", alias="EC_ORGANIZATION")
    ec_registered_by: str = Field(default="operador", alias="EC_REGISTERED_BY")

    database_url: str = Field(default="sqlite:///./data/ra.db", alias="DATABASE_URL")
    ra_uploads_dir: Path = Field(default=Path("./data/uploads"), alias="RA_UPLOADS_DIR")

    reniec_mode: str = Field(default="mock", alias="RENIEC_MODE")
    reniec_api_url: str | None = Field(default=None, alias="RENIEC_API_URL")
    reniec_api_token: str | None = Field(default=None, alias="RENIEC_API_TOKEN")
    reniec_http_timeout: int = Field(default=30, alias="RENIEC_HTTP_TIMEOUT")
    reniec_client_cert_path: Path | None = Field(default=None, alias="RENIEC_CLIENT_CERT_PATH")
    reniec_client_key_path: Path | None = Field(default=None, alias="RENIEC_CLIENT_KEY_PATH")
    reniec_verify_ssl: bool = Field(default=True, alias="RENIEC_VERIFY_SSL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
