import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from hikvision_doorbell.workers.doorbell import doorbell

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Hikvision MQTT bridge...")

    stop_event = asyncio.Event()
    app.state.stop_event = stop_event

    await doorbell.publish_discovery()

    tasks = []
    for task in doorbell.tasks(stop_event):
        tasks.append(task)
    app.state.tasks = tasks

    yield

    logger.info("Stopping Hikvision MQTT bridge...")

    stop_event.set()
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            logger.info("Background task cancelled.")


app = FastAPI(title="Hikvision Doorbell MQTT Bridge", lifespan=lifespan)


@app.get("/healthz/live")
async def liveness() -> Response:
    return Response("{}", status_code=200)


@app.get("/healthz/ready")
async def readiness() -> Response:
    return Response("{}", status_code=200)
