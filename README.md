# Hikvision Doorbell MQTT Bridge

Bridges a Hikvision video doorbell (ISAPI) to Home Assistant via MQTT. Publishes MQTT
discovery for a lock entity and a doorbell button, polls device and call status, and
executes lock commands to open/close the door relay.

## Features

- **MQTT discovery** — Home Assistant discovers a lock and a doorbell (button) entity
- **Lock commands** — Subscribes to MQTT and opens/closes the door relay on command
- **Ring/call status polling** — Polls the device for call status (idle, ring, onCall, error)
  and publishes button events
- **Retries** — HTTP calls use configurable retries with delay; last exception
  re-raised after all attempts
- **Robustness** — Safe parsing of device JSON/XML; MQTT errors caught and logged;
  `handle_lock_command` reconnects on failure
- **Rate-limited logging** — Duplicate log messages are throttled (1 h)

## Requirements

- **Python** 3.11+
- **Poetry** — dependency and venv management
- **Hikvision device** — video doorbell/intercom with ISAPI (deviceInfo,
  VideoIntercom/callStatus, AccessControl door control)
- **MQTT broker** — e.g. Mosquitto, for Home Assistant

## Configuration

Configuration via env vars or `.env`. See `hikvision_doorbell/settings.py`.

### Required

| Variable        | Description                    |
|----------------|--------------------------------|
| `HIK_HOST`     | Hikvision device IP/hostname   |
| `HIK_USERNAME` | Device HTTP digest username    |
| `HIK_PASSWORD` | Device HTTP digest password    |

### Optional (defaults)

| Variable                  | Default                    | Description                          |
|---------------------------|----------------------------|--------------------------------------|
| `HIK_HTTPS`               | `false`                    | Use HTTPS for device                 |
| `HOST`                    | `0.0.0.0`                  | HTTP server bind address             |
| `PORT`                    | `8080`                     | HTTP server port                     |
| `MQTT_HOST`               | `mosquitto`                | MQTT broker hostname                  |
| `MQTT_PORT`               | `1883`                     | MQTT broker port                     |
| `MQTT_USER` / `MQTT_PASS` | `None`                     | MQTT credentials (optional)          |
| `MQTT_BASE_TOPIC`         | `home/hikvision_doorbell`  | Base topic for state/commands        |
| `MQTT_DISCOVERY_PREFIX`   | `homeassistant`            | Home Assistant discovery prefix      |
| `DEVICE_NAME`             | `Door Bell`                | Device name in HA                    |
| `DEVICE_MANUFACTURER`     | `Hikvision`                | Manufacturer in discovery             |
| `DEVICE_MODEL`            | `DS-KV6113-WPE1(C)`       | Model in discovery                   |
| `DEVICE_UNLOCK_SLEEP_TIME_S` | `10` | Seconds to keep door open before re-lock |
| `DEVICE_AUTOLOCKING`      | `true`                     | Auto-close door after unlock         |
| `DEVICE_CALL_RETRY_MAX_COUNT` | `10` | HTTP retry attempts |
| `DEVICE_CALL_RETRY_DELAY` | `0.5`                     | Delay between retries (s)            |
| `DOOR_RELAY_ID`           | `1`                        | Door relay ID in ISAPI path          |

## Running locally

```bash
poetry install
poe app
```

Or:

```bash
poetry run python -m hikvision_doorbell.main
```

The server listens on `HOST:PORT` (default `0.0.0.0:8080`).

### Health endpoints

| Endpoint         | Description           |
|------------------|-----------------------|
| `GET /healthz/live`  | Liveness probe; always 200  |
| `GET /healthz/ready` | Readiness probe; always 200 |

Readiness does not check device or MQTT connectivity.

## Running in Docker/Kubernetes

- **Dockerfile** — builds a container image
- **Helm chart** — under `chart/hikvision-doorbell/` (Deployment, ConfigMap, Secret, ServiceAccount)

CI builds the image and chart; pushes image to Harbor and chart to OCI. See `.github/workflows/`.

## Architecture

- **FastAPI app** — HTTP server; lifespan starts/stops a single `Doorbell` worker.
- **Doorbell worker** — Maintains an `httpx.AsyncClient` (refreshed periodically),
  runs four background tasks:
  - `handle_lock_command` — subscribes to MQTT lock command topic; on command,
    opens door, waits, closes door; reconnects on MQTT failure
  - `refresh_client` — recreates the HTTP client every few seconds, closes the old one
  - `handle_device_infos` — polls `/ISAPI/System/deviceInfo`, publishes availability
  - `handle_call_statuses` — polls `/ISAPI/VideoIntercom/callStatus`, publishes ring/button events
- **Hikvision** — HTTP with digest auth; ISAPI XML (deviceInfo) and JSON (callStatus).
- **MQTT** — Publishes discovery (lock + button), availability, state; subscribes to
  lock commands. Uses short-lived clients per publish; `handle_lock_command` holds
  one connection and reconnects on error.

## API

| Method | Path             | Status | Description      |
|--------|------------------|--------|------------------|
| GET    | `/healthz/live`  | 200    | Liveness probe   |
| GET    | `/healthz/ready` | 200    | Readiness probe  |

## Testing

```bash
poe test
```

Or:

```bash
poetry run coverage run -m pytest
poetry run coverage report -m --fail-under=80
```

Coverage must be ≥80% (enforced in pre-commit and CI).

## Development

1. **Pre-commit** — `pre-commit install`; hooks run on commit (incl. tests).
2. **Lint** — ruff, autoflake, isort, vulture, markdownlint, helmlint.
3. **Commits** — conventional commits (enforced by conventional-pre-commit).
