FROM python:3.14.4-slim-bookworm@sha256:336220baf4dc02a9da56db1720ce6d248aa7c62a0445af0ea1876ae76cc99bed AS global_dependencies

ARG INSTALL_DEV=false

RUN pip install poetry

WORKDIR /app

FROM global_dependencies AS dependencies

COPY README.md pyproject.toml poetry.lock* /app/

COPY hikvision_doorbell /app/hikvision_doorbell

RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install ; else poetry install --without=dev ; fi"

ENV PYTHONPATH=/app

CMD ["poetry", "run", "python", "hikvision_doorbell/main.py"]
