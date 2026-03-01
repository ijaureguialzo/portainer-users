#!make

ifeq (,$(wildcard ./.env))
$(error No se encuentra el fichero .env)
endif

ifeq (,$(wildcard ./.token))
$(error No se encuentra el fichero .token)
endif

help: _header
	${info }
	@echo Opciones:
	@echo --------------------------------
	@echo build
	@echo --------------------------------
	@echo crear-usuarios
	@echo borrar-usuarios
	@echo --------------------------------
	@echo test
	@echo workspace
	@echo clean
	@echo --------------------------------

_header:
	@echo ----------------------
	@echo Portainer User Manager
	@echo ----------------------

build:
	@docker compose build

crear-usuarios:
	@docker compose run -q --rm workspace poetry run python3 scripts/crear_usuarios.py

borrar-usuarios:
	@docker compose run -q --rm workspace poetry run python3 scripts/borrar_usuarios.py

workspace:
	@docker compose run -q --rm workspace /bin/bash

test:
	@docker compose run -q --rm workspace poetry run python3 -m pytest

clean:
	@docker compose down -v --remove-orphans
