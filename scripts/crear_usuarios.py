import json
import os
import sys

import click
import requests
from kubernetes import client, config

portainer_url = os.environ.get('PORTAINER_URL', 'http://localhost')

CONFIGMAP_NAME = os.environ.get('CONFIGMAP_NAME', 'portainer-config')
CONFIGMAP_NAMESPACE = os.environ.get('CONFIGMAP_NAMESPACE', 'portainer')
CONFIGMAP_KEY = 'NamespaceAccessPolicies'

with open('/root/.token', 'r') as f:
    token = f.read().strip()

headers = {"X-API-Key": "{}".format(token)}


def get_k8s_core_v1():
    """Carga la configuración de Kubernetes y devuelve un cliente CoreV1Api."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def actualizar_configmap(core_v1: client.CoreV1Api, user_id: int, namespace: str) -> None:
    """Añade una entrada con user_id y namespace a la clave 'datos' del ConfigMap."""
    try:
        cm = core_v1.read_namespaced_config_map(
            name=CONFIGMAP_NAME,
            namespace=CONFIGMAP_NAMESPACE,
        )
    except client.exceptions.ApiException as e:
        if e.status == 404:
            # Crear el ConfigMap si no existe
            cm = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(
                    name=CONFIGMAP_NAME,
                    namespace=CONFIGMAP_NAMESPACE,
                ),
                data={CONFIGMAP_KEY: json.dumps([])},
            )
            core_v1.create_namespaced_config_map(
                namespace=CONFIGMAP_NAMESPACE,
                body=cm,
            )
            cm = core_v1.read_namespaced_config_map(
                name=CONFIGMAP_NAME,
                namespace=CONFIGMAP_NAMESPACE,
            )
        else:
            print(f'Error al leer el ConfigMap: {e}')
            return

    datos_raw = (cm.data or {}).get(CONFIGMAP_KEY, '[]')
    try:
        datos = json.loads(datos_raw)
        if not isinstance(datos, list):
            datos = [datos]
    except json.JSONDecodeError:
        datos = []

    datos.append({namespace: {"UserAccessPolicies": {user_id: {"RoleId": 0}}, "TeamAccessPolicies": {}}})

    if cm.data is None:
        cm.data = {}
    cm.data[CONFIGMAP_KEY] = json.dumps(datos)

    core_v1.replace_namespaced_config_map(
        name=CONFIGMAP_NAME,
        namespace=CONFIGMAP_NAMESPACE,
        body=cm,
    )
    print(f"ConfigMap '{CONFIGMAP_NAME}' actualizado: user_id={user_id}, namespace={namespace}")


# Inicializar cliente de Kubernetes una sola vez
k8s_core_v1 = get_k8s_core_v1()

print("--- Datos del usuario --------------")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)
contrasenya = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Confirmar contraseña")

for i in range(inicial, final + 1):
    usuario = nombre + separador + "{0:0>2}".format(i)

    print(f"\nCreando el usuario {usuario} y sus recursos asociados...\n")

    # Crear el usuario
    data = {
        "username": usuario,
        "password": contrasenya,
        "role": 2,
    }

    r = requests.post(portainer_url + '/api/users', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al crear el usuario: {r}')
        sys.exit(1)
    else:
        print("Usuario creado correctamente")

    user_id = r.json().get('Id')

    # Crear el namespace
    data = {
        "Name": usuario,
    }

    r = requests.post(portainer_url + '/api/kubernetes/1/namespaces', headers=headers, json=data)

    if r.status_code != requests.codes.ok:
        print(f'Error al crear el namespace: {r}')
    else:
        print("Namespace creado correctamente")

    # Actualizar el ConfigMap con el user_id y el namespace creados
    actualizar_configmap(k8s_core_v1, user_id, usuario)
