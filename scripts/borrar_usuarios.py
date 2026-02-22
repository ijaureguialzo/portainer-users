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


def obtener_id_usuario(username: str) -> int | None:
    """Obtiene el ID de un usuario de Portainer por nombre. Devuelve None si no existe."""
    r = requests.get(portainer_url + '/api/users', headers=headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al obtener la lista de usuarios: {r.status_code} {r.text}')
        return None
    for user in r.json():
        if user.get('Username') == username:
            return user.get('Id')
    return None


def borrar_usuario(username: str) -> bool:
    """Busca y elimina un usuario en Portainer. Devuelve True si se borró correctamente."""
    user_id = obtener_id_usuario(username)
    if user_id is None:
        print(f'  Usuario "{username}" no encontrado en Portainer, omitiendo.')
        return False

    r = requests.delete(portainer_url + f'/api/users/{user_id}', headers=headers, verify=False)
    if r.status_code not in (requests.codes.ok, requests.codes.no_content):
        print(f'  Error al borrar el usuario "{username}" (ID {user_id}): {r.status_code} {r.text}')
        return False

    print(f'  Usuario "{username}" (ID {user_id}) borrado correctamente.')
    return True


def borrar_namespace(namespace: str) -> bool:
    """Elimina un namespace en Kubernetes a través de Portainer. Devuelve True si se borró correctamente."""
    r = requests.delete(
        portainer_url + '/api/kubernetes/1/namespaces',
        headers=headers,
        json=[namespace],
        verify=False,
    )
    if r.status_code not in (requests.codes.ok, requests.codes.no_content):
        print(f'  Error al borrar el namespace "{namespace}": {r.status_code} {r.text}')
        return False

    print(f'  Namespace "{namespace}" borrado correctamente.')
    return True


def get_k8s_core_v1():
    """Carga la configuración de Kubernetes y devuelve un cliente CoreV1Api."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def eliminar_entradas_configmap(core_v1: client.CoreV1Api, namespaces: list[str]) -> None:
    """Elimina las entradas de los namespaces indicados del ConfigMap con reintentos.

    Usa strategic merge patch para leer el estado actual, eliminar las claves
    indicadas y volver a escribir, evitando conflictos de resourceVersion.
    """
    for intento in range(1, K8S_MAX_RETRIES + 1):
        try:
            # Leer el ConfigMap actual
            try:
                cm = core_v1.read_namespaced_config_map(
                    name=CONFIGMAP_NAME,
                    namespace=CONFIGMAP_NAMESPACE,
                    _request_timeout=K8S_TIMEOUT,
                )
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    print(f"ConfigMap '{CONFIGMAP_NAME}' no encontrado, no hay nada que limpiar.")
                    return
                else:
                    print(f'Error al leer el ConfigMap: {e}')
                    return

            # Eliminar las claves correspondientes a los namespaces borrados
            datos_raw = (cm.data or {}).get(CONFIGMAP_KEY, '{}')
            try:
                datos = json.loads(datos_raw)
                if not isinstance(datos, dict):
                    datos = {}
            except json.JSONDecodeError:
                datos = {}

            eliminados = []
            for namespace in namespaces:
                if namespace in datos:
                    del datos[namespace]
                    eliminados.append(namespace)

            if not eliminados:
                print("No se encontraron entradas en el ConfigMap para los namespaces indicados.")
                return

            # Aplicar el patch con los datos actualizados
            patch_body = {"data": {CONFIGMAP_KEY: json.dumps(datos)}}
            core_v1.patch_namespaced_config_map(
                name=CONFIGMAP_NAME,
                namespace=CONFIGMAP_NAMESPACE,
                body=patch_body,
                _request_timeout=K8S_TIMEOUT,
            )
            print(
                f"ConfigMap '{CONFIGMAP_NAME}' actualizado: {len(eliminados)} entrada(s) eliminada(s) "
                f"({', '.join(eliminados)})."
            )
            return

        except client.exceptions.ApiException as e:
            if e.status in (409, 422):
                espera = 2 ** intento
                print(
                    f"Conflicto al actualizar el ConfigMap (intento {intento}/{K8S_MAX_RETRIES}), "
                    f"reintentando en {espera}s..."
                )
                time.sleep(espera)
            else:
                print(f'Error inesperado al actualizar el ConfigMap (HTTP {e.status}): {e.reason}')
                raise

    print(f"Error: no se pudo actualizar el ConfigMap tras {K8S_MAX_RETRIES} intentos.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Inicializar cliente de Kubernetes una sola vez
# ---------------------------------------------------------------------------
k8s_core_v1 = get_k8s_core_v1()

print("--- Datos de borrado de usuarios ---")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)

# Mostrar resumen y pedir confirmación antes de borrar
usuarios = [nombre + separador + "{0:0>2}".format(i) for i in range(inicial, final + 1)]
print(f"\nSe van a borrar {len(usuarios)} usuario(s): {usuarios[0]} … {usuarios[-1]}")
click.confirm("¿Confirmas el borrado?", abort=True)

namespaces_borrados: list[str] = []

for usuario in usuarios:
    print(f"\nBorrando el usuario '{usuario}' y sus recursos asociados...")
    borrar_usuario(usuario)
    if borrar_namespace(usuario):
        namespaces_borrados.append(usuario)

print("\nActualizando el ConfigMap para eliminar las entradas borradas...")
eliminar_entradas_configmap(k8s_core_v1, usuarios)

print("\n¡Proceso de borrado finalizado!")
