#!make

help: _header
	${info }
	@echo Opciones:
	@echo --------------------------------
	@echo build
	@echo --------------------------------
	@echo crear-usuarios
	@echo --------------------------------
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
	@docker compose run --rm workspace python3 crear_usuarios.py

workspace:
	@docker compose run --rm workspace /bin/bash

clean:
	@docker compose down -v --remove-orphans
