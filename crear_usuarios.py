import sys

import click
import requests

with open('.token', 'r') as f:
    token = f.read().strip()

headers = {"X-API-Key": "{}".format(token)}

print("--- Datos del usuario --------------")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)
contrasenya = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Confirmar contraseña")
grupo = click.prompt("Grupo de usuarios", default=nombre)

print(f"\nCreando el grupo {grupo}...\n")

# Crear el equipo
data = {
    "name": grupo,
}

r = requests.post('https://kubernetes.arriaga.eu/api/teams', headers=headers, json=data)

team_id = r.json().get('Id')

if r.status_code != requests.codes.ok:
    print(f'Error al crear el grupo: {r.json().get('message')}')
    sys.exit(1)
else:
    print("Grupo creado correctamente")

for i in range(inicial, final + 1):
    usuario = nombre + separador + "{0:0>2}".format(i)

    print(f"\nCreando el usuario {usuario} y sus recursos asociados...\n")

    # Crear el usuario
    data = {
        "username": usuario,
        "password": contrasenya,
        "role": 2,
    }

    r = requests.post('https://kubernetes.arriaga.eu/api/users', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al crear el usuario: {r.json().get('message')}')
        sys.exit(1)
    else:
        print("Usuario creado correctamente")

    user_id = r.json().get('Id')

    # Añadir el usuario al equipo
    data = {
        "teamID": team_id,
        "userID": user_id,
        "role": 1,
    }

    r = requests.post('https://kubernetes.arriaga.eu/api/team_memberships', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al añadir el usuario al grupo: {r.json().get('message')}')
        sys.exit(1)
    else:
        print("Usuario añadido al grupo correctamente")

    # Crear el namespace
    data = {
        "Name": usuario,
        "Owner": usuario,
        "ResourceQuota": {
            "cpu": "8",
            "enabled": True,
            "memory": "8Gi"
        }
    }

    r = requests.post('https://kubernetes.arriaga.eu/api/kubernetes/1/namespaces', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al crear el namespace: {r.json().get('message')}')
        sys.exit(1)
    else:
        print("Namespace creado correctamente")
