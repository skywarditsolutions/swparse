from dataclasses import dataclass
from typing import Literal

from swparse.__about__ import __version__ as current_version
from swparse.config.base import get_settings

__all__ = ("SystemHealth",)

settings = get_settings()


@dataclass
class SystemHealth:
    database_status: Literal["online", "offline"]
    cache_status: Literal["online", "offline"]
    swparse: str = settings.app.NAME
    version: str = current_version
