ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}

ENV DEBIAN_FRONTEND noninteractive

RUN pip3 install poetry

COPY ./pyproject.toml /app/pyproject.toml

WORKDIR /app

RUN poetry install --no-root

ENV PS1='\u@\h:\w\$\040'
