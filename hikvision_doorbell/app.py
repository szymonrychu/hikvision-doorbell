import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from hikvision_doorbell.workers.doorbell import doorbell

logger = logging.getLogger("uvicorn")


# Lifespan context manager replaces deprecated on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code
    logger.info("Starting Hikvision MQTT bridge...")
    stop_event = asyncio.Event()

    await doorbell.publish_discovery()
    done, pending = await asyncio.wait(
        doorbell.tasks(stop_event),
        return_when=asyncio.FIRST_EXCEPTION,
    )
    try:
        yield
    finally:
        # shutdown code
        logger.info("Stopping Hikvision MQTT bridge...")
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                logger.info("Bridge task cancelled successfully.")


app = FastAPI(title="Hikvision Doorbell MQTT Bridge", lifespan=lifespan)


@app.get("/healthz/live")
async def liveness() -> Response:
    return Response("{}", status_code=200)


@app.get("/healthz/ready")
async def readiness() -> Response:
    return Response("{}", status_code=200)
