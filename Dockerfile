FROM python:3.14.3-slim-bookworm@sha256:5404df00cf00e6e7273375f415651837b4d192ac6859c44d3b740888ac798c99 AS global_dependencies

ARG INSTALL_DEV=false

RUN pip install poetry

WORKDIR /app

FROM global_dependencies AS dependencies

COPY README.md pyproject.toml poetry.lock* /app/

COPY hikvision_doorbell /app/hikvision_doorbell

RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install ; else poetry install --without=dev ; fi"

ENV PYTHONPATH=/app

CMD ["poetry", "run", "python", "hikvision_doorbell/main.py"]
