from __future__ import annotations
from pathlib import Path
from pydantic import Field 
from pydantic_settings import BaseSettings, SettingsConfigDict 


class SqlServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file = ".env", env_prefix = "SQLSERVER_", extra = "ignore")

    host: str
    port: int = 1433
    db: str
    user: str
    password: str
    driver: str = "ODBC Driver 17 for SQL Server"
    encrypt: str = "yes"
    trust_cert: str = "yes"

    def odbc_connection_string(self) -> str:
        return(
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.db};"
            f"UID={self.user};"
            f"PWD={self.password};"
            f"Encrypt={self.encrypt};"
            f"TrustServerCertificate={self.trust_cert};"
        )
    
class EtlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file = ".env", extra = "ignore")

    batch_size: int = Field(default = 5000, alias = "BATCH_SIZE")
    max_retries: int = Field(default = 3, alias = "MAX_RETRIES")
    retry_wait_seconds: int = Field(default = 10, alias = "RETRY_WAIT_SECODS")
    log_level: str = Field(default = "INFO", alias = "LOG_LEVEL")
    log_dir: Path = Path("./logs")
    output_dir: Path = Path("./output")

class Settings:
    def __init__(self) -> None:
        self.sqlserver = SqlServerSettings()
        self.etl = EtlSettings()