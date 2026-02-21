import json
import os
import sys
import time

import click
import requests
import urllib3
from kubernetes import client, config

urllib3.disable_warnings()

portainer_url = os.environ.get('PORTAINER_URL', 'http://localhost')

CONFIGMAP_NAME = os.environ.get('CONFIGMAP_NAME', 'portainer-config')
CONFIGMAP_NAMESPACE = os.environ.get('CONFIGMAP_NAMESPACE', 'portainer')
CONFIGMAP_KEY = 'NamespaceAccessPolicies'
K8S_TIMEOUT = int(os.environ.get('K8S_TIMEOUT', '30'))
K8S_MAX_RETRIES = int(os.environ.get('K8S_MAX_RETRIES', '5'))

with open('/root/.token', 'r') as f:
    token = f.read().strip()

headers = {"X-API-Key": "{}".format(token)}


def crear_usuario(username: str, password: str) -> int:
    """Crea un usuario en Portainer y devuelve su ID."""
    data = {
        "username": username,
        "password": password,
        "role": 2,
    }
    r = requests.post(portainer_url + '/api/users', headers=headers, json=data, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al crear el usuario: {r}')
        sys.exit(1)
    print("Usuario creado correctamente")
    return r.json().get('Id')


def crear_namespace(namespace: str) -> None:
    """Crea un namespace en Kubernetes a través de Portainer."""
    data = {"Name": namespace}
    r = requests.post(portainer_url + '/api/kubernetes/1/namespaces', headers=headers, json=data, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al crear el namespace: {r}')
    else:
        print("Namespace creado correctamente")


def get_k8s_core_v1():
    """Carga la configuración de Kubernetes y devuelve un cliente CoreV1Api."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def actualizar_configmap(core_v1: client.CoreV1Api, entradas: dict[str, int]) -> None:
    """Actualiza el ConfigMap usando patch estratégico con reintentos.

    Usa strategic merge patch en lugar de replace para evitar conflictos de
    resourceVersion cuando Portainer modifica el ConfigMap concurrentemente.
    Cada intento lee el estado actual para recalcular el dato a parchear.
    """
    for intento in range(1, K8S_MAX_RETRIES + 1):
        try:
            # Leer el estado actual del ConfigMap (o crearlo si no existe)
            try:
                cm = core_v1.read_namespaced_config_map(
                    name=CONFIGMAP_NAME,
                    namespace=CONFIGMAP_NAMESPACE,
                    _request_timeout=K8S_TIMEOUT,
                )
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    nuevo_cm = client.V1ConfigMap(
                        metadata=client.V1ObjectMeta(
                            name=CONFIGMAP_NAME,
                            namespace=CONFIGMAP_NAMESPACE,
                        ),
                        data={CONFIGMAP_KEY: json.dumps({})},
                    )
                    core_v1.create_namespaced_config_map(
                        namespace=CONFIGMAP_NAMESPACE,
                        body=nuevo_cm,
                        _request_timeout=K8S_TIMEOUT,
                    )
                    cm = core_v1.read_namespaced_config_map(
                        name=CONFIGMAP_NAME,
                        namespace=CONFIGMAP_NAMESPACE,
                        _request_timeout=K8S_TIMEOUT,
                    )
                else:
                    print(f'Error al leer el ConfigMap: {e}')
                    return

            # Calcular el nuevo valor mezclando los datos existentes con las entradas nuevas
            datos_raw = (cm.data or {}).get(CONFIGMAP_KEY, '{}')
            try:
                datos = json.loads(datos_raw)
                if not isinstance(datos, dict):
                    datos = {}
            except json.JSONDecodeError:
                datos = {}

            for namespace, user_id in entradas.items():
                datos[namespace] = {
                    "UserAccessPolicies": {str(user_id): {"RoleId": 0}},
                    "TeamAccessPolicies": {},
                }

            # Usar patch en lugar de replace: no requiere resourceVersion exacto
            patch_body = {"data": {CONFIGMAP_KEY: json.dumps(datos)}}
            core_v1.patch_namespaced_config_map(
                name=CONFIGMAP_NAME,
                namespace=CONFIGMAP_NAMESPACE,
                body=patch_body,
                _request_timeout=K8S_TIMEOUT,
            )
            print(f"ConfigMap '{CONFIGMAP_NAME}' actualizado con {len(entradas)} entradas.")
            return

        except client.exceptions.ApiException as e:
            if e.status in (409, 422):
                espera = 2 ** intento
                print(
                    f"Conflicto al actualizar el ConfigMap (intento {intento}/{K8S_MAX_RETRIES}), reintentando en {espera}s...")
                time.sleep(espera)
            else:
                print(f'Error inesperado al actualizar el ConfigMap (HTTP {e.status}): {e.reason}')
                raise

    print(f"Error: no se pudo actualizar el ConfigMap tras {K8S_MAX_RETRIES} intentos.")
    sys.exit(1)


# Inicializar cliente de Kubernetes una sola vez
k8s_core_v1 = get_k8s_core_v1()

print("--- Datos del usuario --------------")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)
contrasenya = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Confirmar contraseña")

entradas_configmap: dict[str, int] = {}

for i in range(inicial, final + 1):
    usuario = nombre + separador + "{0:0>2}".format(i)

    print(f"\nCreando el usuario {usuario} y sus recursos asociados...\n")

    user_id = crear_usuario(usuario, contrasenya)
    crear_namespace(usuario)
    entradas_configmap[usuario] = user_id

print("\nActualizando el ConfigMap con todos los usuarios creados...")
actualizar_configmap(k8s_core_v1, entradas_configmap)
