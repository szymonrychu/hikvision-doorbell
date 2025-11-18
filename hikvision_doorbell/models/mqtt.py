import logging
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CallStateEvent(Enum):
    idle = "idle"
    ring = "ring"
    calling = "onCall"
    error = "error"


class MqttEvent(BaseModel):
    event: CallStateEvent
    channel_id: Optional[str] = None
    rule_name: Optional[str] = None
    raw: Dict[str, Any] = {}


# ───────────────────────────────────────────────
# Event model
class DoorbellEvent(BaseModel):
    event_type: str
    ip_address: Optional[str]
    channel_id: Optional[str]
    rule_name: Optional[str]
    timestamp: Optional[str]
    raw: Dict[str, Any]

    @classmethod
    def from_xml_block(cls, xml_block: str) -> Optional["DoorbellEvent"]:
        try:
            root = ET.fromstring(xml_block)
        except ET.ParseError as e:
            logger.debug(f"XML parse error: {e}")
            return None

        data: Dict[str, Any] = {}
        for child in root:
            data[child.tag] = (child.text or "").strip()

        ev_type = data.get("eventType") or data.get("EventType") or "unknown"
        return cls(
            event_type=ev_type,
            ip_address=data.get("ipAddress"),
            channel_id=data.get("channelID") or data.get("channelId"),
            rule_name=data.get("ruleName"),
            timestamp=data.get("time"),
            raw=data,
        )

    def to_mqtt_event(self):
        return MqttEvent(event=self.event_type, channel_id=self.channel_id, rule_name=self.rule_name, raw=self.raw)
