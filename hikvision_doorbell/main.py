import logging

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from hikvision_doorbell.settings import settings

logger = logging.getLogger(__name__)


def serve():
    kwargs = {}
    if settings.DEBUG:
        kwargs["reload"] = True
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = settings.LOG_FORMAT
    uvicorn.run("hikvision_doorbell.app:app", host=str(settings.HOST), port=settings.PORT, **kwargs)


if __name__ == "__main__":
    serve()
