ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}

ENV DEBIAN_FRONTEND noninteractive

RUN pip3 install click requests kubernetes

ENV PS1='\u@\h:\w\$\040'

WORKDIR /app
