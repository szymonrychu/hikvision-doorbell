import logging
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    class LogLevel(Enum):
        DEBUG = "DEBUG"
        INFO = "INFO"
        WARN = "WARN"
        WARNING = "WARNING"
        ERROR = "ERROR"
        CRITICAL = "CRITICAL"

    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = False
    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    # Hikvision device settings
    HIK_HOST: str = ""
    HIK_USERNAME: str = ""
    HIK_PASSWORD: str = ""
    HIK_HTTPS: bool = False

    # MQTT broker settings
    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_USER: Optional[str] = None
    MQTT_PASS: Optional[str] = None
    MQTT_BASE_TOPIC: str = "home/hikvision_doorbell"
    MQTT_DISCOVERY_PREFIX: str = "homeassistant"

    # Device metadata
    DEVICE_NAME: str = "doorbell"
    DEVICE_MANUFACTURER: str = "Hikvision"
    DEVICE_MODEL: str = "DS-KV6113-WPE1(C)"
    DEVICE_SENSOR_NAME: str = "ring"
    DEVICE_SENSOR_UID: str = "doorbell_state_sensor"
    DEVICE_LOCK_NAME: str = "lock"
    DEVICE_LOCK_UID: str = "doorbell_state_lock"

    # Door relay id
    DOOR_RELAY_ID: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf‑8"


settings = Settings()

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else settings.LOG_LEVEL.value, format=settings.LOG_FORMAT)


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        path = ""
        if record.args and isinstance(record.args, dict):
            path = record.args.get("path", "")
        elif record.args and isinstance(record.args, tuple) and len(record.args) >= 3:
            path = record.args[2] if isinstance(record.args[2], str) else ""
        return path not in ("/healthz/live", "/healthz/ready")


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
