import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from hikvision_doorbell.mqtt_bridge import bridge

logger = logging.getLogger("uvicorn")


# Lifespan context manager replaces deprecated on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code
    logger.info("Starting Hikvision MQTT bridge...")
    bridge_task = asyncio.create_task(bridge.run())
    try:
        yield
    finally:
        # shutdown code
        logger.info("Stopping Hikvision MQTT bridge...")
        bridge_task.cancel()
        try:
            await bridge_task
        except asyncio.CancelledError:
            logger.info("Bridge task cancelled successfully.")


app = FastAPI(title="Hikvision Doorbell MQTT Bridge", lifespan=lifespan)


@app.get("/healthz/live")
async def liveness() -> Response:
    return Response("{}", status_code=200)


@app.get("/healthz/ready")
async def readiness() -> Response:
    return Response("{}", status_code=200)
