FROM python:3.14.5-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb AS global_dependencies

ARG INSTALL_DEV=false

RUN pip install poetry

WORKDIR /app

FROM global_dependencies AS dependencies

COPY README.md pyproject.toml poetry.lock* /app/

COPY hikvision_doorbell /app/hikvision_doorbell

RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install ; else poetry install --without=dev ; fi"

ENV PYTHONPATH=/app

CMD ["poetry", "run", "python", "hikvision_doorbell/main.py"]
