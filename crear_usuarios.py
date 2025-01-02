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

print("--- Cuota de recursos --------------")
cpus = click.prompt("CPUs", type=float, default=8)
ram = click.prompt("RAM (GiB)", type=float, default=8)

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

    # Crear el namespace
    data = {
        "Name": usuario,
        "Owner": usuario,
        "ResourceQuota": {
            "cpu": str(cpus),
            "memory": f"{ram}Gi",
            "enabled": True,
        }
    }

    r = requests.post('https://kubernetes.arriaga.eu/api/kubernetes/1/namespaces', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al crear el namespace: {r.json().get('message')}')
        sys.exit(1)
    else:
        print("Namespace creado correctamente")
