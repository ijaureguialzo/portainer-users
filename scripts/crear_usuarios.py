import json
import os
import sys

import click
import requests
import urllib3
from kubernetes import client, config

urllib3.disable_warnings()

portainer_url = os.environ.get('PORTAINER_URL', 'http://localhost')

CONFIGMAP_NAME = os.environ.get('CONFIGMAP_NAME', 'portainer-config')
CONFIGMAP_NAMESPACE = os.environ.get('CONFIGMAP_NAMESPACE', 'portainer')
CONFIGMAP_KEY = 'NamespaceAccessPolicies'
CLUSTER_ROLE_BINDING_NAME = 'portainer-crb-user'

with open('/root/.token', 'r') as f:
    token = f.read().strip()

headers = {"X-API-Key": "{}".format(token)}


def get_instance_id() -> str:
    """Consulta el endpoint /api/system/status y devuelve el InstanceID de Portainer."""
    r = requests.get(portainer_url + '/api/system/status', headers=headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al obtener el estado del sistema: {r}')
        sys.exit(1)
    return r.json().get('InstanceID')


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


def get_k8s_clients():
    """Carga la configuración de Kubernetes y devuelve clientes CoreV1Api y RbacAuthorizationV1Api."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.RbacAuthorizationV1Api()


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
                data={CONFIGMAP_KEY: json.dumps({})},
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

    datos_raw = (cm.data or {}).get(CONFIGMAP_KEY, '{}')
    try:
        datos = json.loads(datos_raw)
        if not isinstance(datos, dict):
            datos = {}
    except json.JSONDecodeError:
        datos = {}

    datos[namespace] = {"UserAccessPolicies": {str(user_id): {"RoleId": 0}}, "TeamAccessPolicies": {}}

    if cm.data is None:
        cm.data = {}
    cm.data[CONFIGMAP_KEY] = json.dumps(datos)

    core_v1.replace_namespaced_config_map(
        name=CONFIGMAP_NAME,
        namespace=CONFIGMAP_NAMESPACE,
        body=cm,
    )
    print(f"ConfigMap '{CONFIGMAP_NAME}' actualizado: user_id={user_id}, namespace={namespace}")


def crear_service_account(core_v1: client.CoreV1Api, instance_id: str, user_id: int) -> str:
    """Crea una ServiceAccount en el namespace portainer y devuelve su nombre."""
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    sa = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=sa_name,
            namespace=CONFIGMAP_NAMESPACE,
        )
    )
    try:
        core_v1.create_namespaced_service_account(namespace=CONFIGMAP_NAMESPACE, body=sa)
        print(f"ServiceAccount '{sa_name}' creada correctamente")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"ServiceAccount '{sa_name}' ya existe, omitiendo creación")
        else:
            print(f'Error al crear la ServiceAccount: {e}')
            sys.exit(1)
    return sa_name


def crear_token_service_account(core_v1: client.CoreV1Api, instance_id: str, user_id: int, sa_name: str) -> None:
    """Crea un Secret de tipo service-account-token para la SA."""
    secret_name = f"{instance_id}-{sa_name}-secret"
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name,
            namespace=CONFIGMAP_NAMESPACE,
            annotations={
                "kubernetes.io/service-account.name": sa_name,
            },
        ),
        type="kubernetes.io/service-account-token",
    )
    try:
        core_v1.create_namespaced_secret(namespace=CONFIGMAP_NAMESPACE, body=secret)
        print(f"Secret '{secret_name}' creado correctamente")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"Secret '{secret_name}' ya existe, omitiendo creación")
        else:
            print(f'Error al crear el Secret: {e}')
            sys.exit(1)


def actualizar_cluster_role_binding(rbac_v1: client.RbacAuthorizationV1Api, instance_id: str, user_id: int) -> None:
    """Añade una ServiceAccount al ClusterRoleBinding portainer-crb-user."""
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    try:
        crb = rbac_v1.read_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME)
    except client.exceptions.ApiException as e:
        print(f'Error al leer el ClusterRoleBinding: {e}')
        return

    subjects = crb.subjects or []
    # Evitar duplicados
    if not any(s.name == sa_name for s in subjects):
        nuevo_subject = {
            "kind": "ServiceAccount",
            "name": sa_name,
            "namespace": CONFIGMAP_NAMESPACE,
        }
        subjects.append(nuevo_subject)
    crb.subjects = subjects

    rbac_v1.replace_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME, body=crb)
    print(f"ClusterRoleBinding '{CLUSTER_ROLE_BINDING_NAME}' actualizado: ServiceAccount={sa_name}")


# Inicializar clientes de Kubernetes una sola vez
k8s_core_v1, k8s_rbac_v1 = get_k8s_clients()

print("--- Datos del usuario --------------")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)
contrasenya = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Confirmar contraseña")

instance_id = get_instance_id()

for i in range(inicial, final + 1):
    usuario = nombre + separador + "{0:0>2}".format(i)

    print(f"\nCreando el usuario {usuario} y sus recursos asociados...\n")

    user_id = crear_usuario(usuario, contrasenya)
    sa_name = crear_service_account(k8s_core_v1, instance_id, user_id)
    crear_token_service_account(k8s_core_v1, instance_id, user_id, sa_name)
    actualizar_cluster_role_binding(k8s_rbac_v1, instance_id, user_id)
    crear_namespace(usuario)
    actualizar_configmap(k8s_core_v1, user_id, usuario)
