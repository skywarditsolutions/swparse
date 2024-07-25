from __future__ import annotations

import importlib
import os
from functools import lru_cache
from logging import getLogger

from anyio import Path
from dotenv import load_dotenv
from msgspec import ValidationError
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

logger = getLogger(__name__)
DEFAULT_MODULE_NAME = "swparse"
version = importlib.metadata.version(DEFAULT_MODULE_NAME)



def env_prefixed_model_config(env_prefix):
    mode = os.environ["MODE"]
    if mode.lower() == "dev":
        env_file = ".env.dev"
    else:
        env_file = ".env"

    return SettingsConfigDict(
    env_prefix=env_prefix,
    env_file=env_file,
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore"
)

class ServerSetting(BaseSettings):
    model_config = env_prefixed_model_config("SERVER_")
    HF_TOKEN: str =""
    DEVICE: str = "cuda"

class MinioSettings(BaseSettings):
    model_config =  env_prefixed_model_config("MINIO_")
    STORAGE_LOCATION: str
    PORT: int
    ROOT_USER: str
    ROOT_PASSWORD: str
    BUCKET: str
    ENPOINT_URL: str

class WorkerSettings(BaseSettings):
    model_config =  env_prefixed_model_config("WORKER_")
    REDIS_HOST: str
    REDIS_URL: str 



@lru_cache
def load_settings() -> (
    tuple[
        ServerSetting,
        MinioSettings,
        WorkerSettings
    ]
):
    """Load Settings file.
        return settings

    Returns:
        Settings: application settings
    """

    try:
        server: ServerSetting = ServerSetting()
        storage: MinioSettings = MinioSettings()
        worker: WorkerSettings = WorkerSettings()
        print(worker.model_dump(),file=open("wokerdump.log","w"))

    except ValidationError:
        logger.exception("Could not load settings")
        raise
    return server, storage,worker


server,storage,worker = load_settings()
