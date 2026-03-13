"""Shared pytest fixtures and configuration."""

# Sample Hikvision deviceInfo XML response
SAMPLE_DEVICE_INFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DeviceInfo>
  <deviceName>DS-KV6113-WPE1</deviceName>
  <deviceID>12345</deviceID>
  <deviceDescription>IP Video Intercom</deviceDescription>
  <model>DS-KV6113-WPE1(C)</model>
</DeviceInfo>
"""

# Sample Hikvision callStatus JSON response
SAMPLE_CALL_STATUS_IDLE = '{"CallStatus": {"status": "idle"}}'
SAMPLE_CALL_STATUS_RING = '{"CallStatus": {"status": "ring"}}'
SAMPLE_CALL_STATUS_CALLING = '{"CallStatus": {"status": "onCall"}}'
SAMPLE_CALL_STATUS_ERROR = '{"CallStatus": {"status": "error"}}'
