"""Librería compartida para la gestión de usuarios y recursos de Portainer/Kubernetes."""

import json
import os
import sys
import time
from dataclasses import dataclass, field

import requests
import urllib3
from kubernetes import client, config

urllib3.disable_warnings()

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CLUSTER_ROLE_BINDING_NAME = 'portainer-crb-user'


@dataclass
class PortainerConfig:
    """Configuración centralizada para Portainer y Kubernetes."""

    portainer_url: str
    configmap_name: str
    configmap_namespace: str
    configmap_key: str
    k8s_timeout: int
    k8s_max_retries: int
    token: str
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.headers:
            self.headers = {"X-API-Key": self.token}


def load_config(token_path: str = '/root/.token') -> PortainerConfig:
    """Carga la configuración desde variables de entorno y el fichero de token."""
    with open(token_path, 'r') as f:
        token = f.read().strip()

    return PortainerConfig(
        portainer_url=os.environ.get('PORTAINER_URL', 'http://localhost'),
        configmap_name=os.environ.get('CONFIGMAP_NAME', 'portainer-config'),
        configmap_namespace=os.environ.get('CONFIGMAP_NAMESPACE', 'portainer'),
        configmap_key=os.environ.get('CONFIGMAP_KEY', 'NamespaceAccessPolicies'),
        k8s_timeout=int(os.environ.get('K8S_TIMEOUT', '30')),
        k8s_max_retries=int(os.environ.get('K8S_MAX_RETRIES', '5')),
        token=token,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generar_nombres_usuarios(nombre: str, separador: str, inicial: int, final: int) -> list[str]:
    """Genera la lista de nombres de usuario con formato nombre-NN."""
    return [nombre + separador + "{0:0>2}".format(i) for i in range(inicial, final + 1)]


# ---------------------------------------------------------------------------
# Clientes de Kubernetes
# ---------------------------------------------------------------------------


def get_k8s_clients(include_rbac: bool = False):
    """Carga la configuración de Kubernetes y devuelve clientes API.

    Args:
        include_rbac: si es True devuelve (CoreV1Api, RbacAuthorizationV1Api);
                      en caso contrario devuelve solo CoreV1Api.
    """
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    core_v1 = client.CoreV1Api()
    if include_rbac:
        return core_v1, client.RbacAuthorizationV1Api()
    return core_v1


# ---------------------------------------------------------------------------
# Funciones de la API de Portainer
# ---------------------------------------------------------------------------


def get_instance_id(cfg: PortainerConfig) -> str:
    """Consulta el endpoint /api/system/status y devuelve el InstanceID de Portainer."""
    r = requests.get(cfg.portainer_url + '/api/system/status', headers=cfg.headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al obtener el estado del sistema: {r}')
        sys.exit(1)
    return r.json().get('InstanceID')


def crear_usuario(cfg: PortainerConfig, username: str, password: str) -> int:
    """Crea un usuario en Portainer y devuelve su ID."""
    data = {
        "username": username,
        "password": password,
        "role": 2,
    }
    r = requests.post(cfg.portainer_url + '/api/users', headers=cfg.headers, json=data, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al crear el usuario: {r}')
        sys.exit(1)
    print("Usuario creado correctamente")
    return r.json().get('Id')


def asignar_acceso_endpoint(cfg: PortainerConfig, user_id: int) -> None:
    """Añade el usuario al endpoint 1 actualizando UserAccessPolicies via PUT /api/endpoints/1."""
    r = requests.get(cfg.portainer_url + '/api/endpoints/1', headers=cfg.headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al obtener el endpoint: {r}')
        sys.exit(1)

    endpoint_data = r.json()
    policies = endpoint_data.get('UserAccessPolicies', {})
    policies[str(user_id)] = {"RoleId": 0}

    r = requests.put(
        cfg.portainer_url + '/api/endpoints/1',
        headers=cfg.headers,
        json={"UserAccessPolicies": policies},
        verify=False,
    )
    if r.status_code != requests.codes.ok:
        print(f'Error al asignar acceso al endpoint: {r}')
        sys.exit(1)
    print(f"Acceso al endpoint asignado para el usuario {user_id}")


def obtener_id_usuario(cfg: PortainerConfig, username: str) -> int | None:
    """Obtiene el ID de un usuario de Portainer por nombre. Devuelve None si no existe."""
    r = requests.get(cfg.portainer_url + '/api/users', headers=cfg.headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'Error al obtener la lista de usuarios: {r.status_code} {r.text}')
        return None
    for user in r.json():
        if user.get('Username') == username:
            return user.get('Id')
    return None


def borrar_usuario(cfg: PortainerConfig, username: str) -> bool:
    """Busca y elimina un usuario en Portainer. Devuelve True si se borró correctamente."""
    user_id = obtener_id_usuario(cfg, username)
    if user_id is None:
        print(f'  Usuario "{username}" no encontrado en Portainer, omitiendo.')
        return False

    r = requests.delete(cfg.portainer_url + f'/api/users/{user_id}', headers=cfg.headers, verify=False)
    if r.status_code not in (requests.codes.ok, requests.codes.no_content):
        print(f'  Error al borrar el usuario "{username}" (ID {user_id}): {r.status_code} {r.text}')
        return False

    print(f'  Usuario "{username}" (ID {user_id}) borrado correctamente.')
    return True


def crear_namespace(cfg: PortainerConfig, namespace: str) -> None:
    """Crea un namespace en Kubernetes a través de Portainer."""
    data = {"Name": namespace}
    r = requests.post(
        cfg.portainer_url + '/api/kubernetes/1/namespaces',
        headers=cfg.headers,
        json=data,
        verify=False,
    )
    if r.status_code != requests.codes.ok:
        print(f'Error al crear el namespace: {r}')
    else:
        print("Namespace creado correctamente")


def borrar_namespace(cfg: PortainerConfig, namespace: str) -> bool:
    """Elimina un namespace en Kubernetes a través de Portainer. Devuelve True si se borró correctamente."""
    r = requests.delete(
        cfg.portainer_url + '/api/kubernetes/1/namespaces',
        headers=cfg.headers,
        json=[namespace],
        verify=False,
    )
    if r.status_code not in (requests.codes.ok, requests.codes.no_content):
        print(f'  Error al borrar el namespace "{namespace}": {r.status_code} {r.text}')
        return False

    print(f'  Namespace "{namespace}" borrado correctamente.')
    return True


# ---------------------------------------------------------------------------
# Funciones de Kubernetes (ConfigMap, ServiceAccount, RBAC)
# ---------------------------------------------------------------------------


def actualizar_configmap(cfg: PortainerConfig, core_v1: client.CoreV1Api, entradas: dict[str, int]) -> None:
    """Actualiza el ConfigMap usando patch estratégico con reintentos.

    Usa strategic merge patch en lugar de replace para evitar conflictos de
    resourceVersion cuando Portainer modifica el ConfigMap concurrentemente.
    Cada intento lee el estado actual para recalcular el dato a parchear.
    """
    for intento in range(1, cfg.k8s_max_retries + 1):
        try:
            try:
                cm = core_v1.read_namespaced_config_map(
                    name=cfg.configmap_name,
                    namespace=cfg.configmap_namespace,
                    _request_timeout=cfg.k8s_timeout,
                )
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    nuevo_cm = client.V1ConfigMap(
                        metadata=client.V1ObjectMeta(
                            name=cfg.configmap_name,
                            namespace=cfg.configmap_namespace,
                        ),
                        data={cfg.configmap_key: json.dumps({})},
                    )
                    core_v1.create_namespaced_config_map(
                        namespace=cfg.configmap_namespace,
                        body=nuevo_cm,
                        _request_timeout=cfg.k8s_timeout,
                    )
                    cm = core_v1.read_namespaced_config_map(
                        name=cfg.configmap_name,
                        namespace=cfg.configmap_namespace,
                        _request_timeout=cfg.k8s_timeout,
                    )
                else:
                    print(f'Error al leer el ConfigMap: {e}')
                    return

            datos_raw = (cm.data or {}).get(cfg.configmap_key, '{}')
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

            patch_body = {"data": {cfg.configmap_key: json.dumps(datos)}}
            core_v1.patch_namespaced_config_map(
                name=cfg.configmap_name,
                namespace=cfg.configmap_namespace,
                body=patch_body,
                _request_timeout=cfg.k8s_timeout,
            )
            print(f"ConfigMap '{cfg.configmap_name}' actualizado con {len(entradas)} entradas.")
            return

        except client.exceptions.ApiException as e:
            if e.status in (409, 422):
                espera = 2 ** intento
                print(
                    f"Conflicto al actualizar el ConfigMap (intento {intento}/{cfg.k8s_max_retries}), "
                    f"reintentando en {espera}s..."
                )
                time.sleep(espera)
            else:
                print(f'Error inesperado al actualizar el ConfigMap (HTTP {e.status}): {e.reason}')
                raise

    print(f"Error: no se pudo actualizar el ConfigMap tras {cfg.k8s_max_retries} intentos.")
    sys.exit(1)


def eliminar_entradas_configmap(cfg: PortainerConfig, core_v1: client.CoreV1Api, namespaces: list[str]) -> None:
    """Elimina las entradas de los namespaces indicados del ConfigMap con reintentos.

    Usa strategic merge patch para leer el estado actual, eliminar las claves
    indicadas y volver a escribir, evitando conflictos de resourceVersion.
    """
    for intento in range(1, cfg.k8s_max_retries + 1):
        try:
            try:
                cm = core_v1.read_namespaced_config_map(
                    name=cfg.configmap_name,
                    namespace=cfg.configmap_namespace,
                    _request_timeout=cfg.k8s_timeout,
                )
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    print(f"ConfigMap '{cfg.configmap_name}' no encontrado, no hay nada que limpiar.")
                    return
                else:
                    print(f'Error al leer el ConfigMap: {e}')
                    return

            datos_raw = (cm.data or {}).get(cfg.configmap_key, '{}')
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
                print(
                    f"Aviso: ninguno de los namespaces indicados ({', '.join(namespaces)}) "
                    f"tenía entrada en el ConfigMap '{cfg.configmap_name}'."
                )
                return

            patch_body = {"data": {cfg.configmap_key: json.dumps(datos)}}
            core_v1.patch_namespaced_config_map(
                name=cfg.configmap_name,
                namespace=cfg.configmap_namespace,
                body=patch_body,
                _request_timeout=cfg.k8s_timeout,
            )
            print(
                f"ConfigMap '{cfg.configmap_name}' actualizado: {len(eliminados)} entrada(s) eliminada(s) "
                f"({', '.join(eliminados)})."
            )
            return

        except client.exceptions.ApiException as e:
            if e.status in (409, 422):
                espera = 2 ** intento
                print(
                    f"Conflicto al actualizar el ConfigMap (intento {intento}/{cfg.k8s_max_retries}), "
                    f"reintentando en {espera}s..."
                )
                time.sleep(espera)
            else:
                print(f'Error inesperado al actualizar el ConfigMap (HTTP {e.status}): {e.reason}')
                raise

    print(f"Error: no se pudo actualizar el ConfigMap tras {cfg.k8s_max_retries} intentos.")
    sys.exit(1)


def crear_service_account(
    cfg: PortainerConfig, core_v1: client.CoreV1Api, instance_id: str, user_id: int
) -> str:
    """Crea una ServiceAccount en el namespace portainer y devuelve su nombre."""
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    sa = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=sa_name,
            namespace=cfg.configmap_namespace,
        )
    )
    try:
        core_v1.create_namespaced_service_account(namespace=cfg.configmap_namespace, body=sa)
        print(f"ServiceAccount '{sa_name}' creada correctamente")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"ServiceAccount '{sa_name}' ya existe, omitiendo creación")
        else:
            print(f'Error al crear la ServiceAccount: {e}')
            sys.exit(1)
    return sa_name


def crear_token_service_account(
    cfg: PortainerConfig, core_v1: client.CoreV1Api, instance_id: str, sa_name: str
) -> None:
    """Crea un Secret de tipo service-account-token para la SA."""
    secret_name = f"{instance_id}-{sa_name}-secret"
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name,
            namespace=cfg.configmap_namespace,
            annotations={
                "kubernetes.io/service-account.name": sa_name,
            },
        ),
        type="kubernetes.io/service-account-token",
    )
    try:
        core_v1.create_namespaced_secret(namespace=cfg.configmap_namespace, body=secret)
        print(f"Secret '{secret_name}' creado correctamente")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"Secret '{secret_name}' ya existe, omitiendo creación")
        else:
            print(f'Error al crear el Secret: {e}')
            sys.exit(1)


def actualizar_cluster_role_binding(
    cfg: PortainerConfig, rbac_v1: client.RbacAuthorizationV1Api, instance_id: str, user_id: int
) -> None:
    """Añade una ServiceAccount al ClusterRoleBinding portainer-crb-user."""
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    try:
        crb = rbac_v1.read_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME)
    except client.exceptions.ApiException as e:
        print(f'Error al leer el ClusterRoleBinding: {e}')
        return

    subjects = crb.subjects or []
    if not any(s.name == sa_name for s in subjects):
        nuevo_subject = {
            "kind": "ServiceAccount",
            "name": sa_name,
            "namespace": cfg.configmap_namespace,
        }
        subjects.append(nuevo_subject)
    crb.subjects = subjects

    rbac_v1.replace_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME, body=crb)
    print(f"ClusterRoleBinding '{CLUSTER_ROLE_BINDING_NAME}' actualizado: ServiceAccount={sa_name}")


def revocar_acceso_endpoint(cfg: PortainerConfig, user_id: int) -> bool:
    """Elimina el acceso del usuario al endpoint 1 borrando su entrada de UserAccessPolicies.

    Devuelve True si se revocó correctamente.
    """
    r = requests.get(cfg.portainer_url + '/api/endpoints/1', headers=cfg.headers, verify=False)
    if r.status_code != requests.codes.ok:
        print(f'  Error al obtener el endpoint: {r}')
        return False

    endpoint_data = r.json()
    policies = endpoint_data.get('UserAccessPolicies', {})
    clave = str(user_id)

    if clave not in policies:
        print(f'  El usuario {user_id} no tenía acceso al endpoint, omitiendo.')
        return True

    del policies[clave]

    r = requests.put(
        cfg.portainer_url + '/api/endpoints/1',
        headers=cfg.headers,
        json={"UserAccessPolicies": policies},
        verify=False,
    )
    if r.status_code != requests.codes.ok:
        print(f'  Error al revocar acceso al endpoint para el usuario {user_id}: {r.status_code} {r.text}')
        return False

    print(f'  Acceso al endpoint revocado para el usuario {user_id}.')
    return True


def borrar_service_account(
    cfg: PortainerConfig, core_v1: client.CoreV1Api, instance_id: str, user_id: int
) -> bool:
    """Elimina la ServiceAccount del usuario en el namespace de Portainer.

    Devuelve True si se borró correctamente.
    """
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    try:
        core_v1.delete_namespaced_service_account(name=sa_name, namespace=cfg.configmap_namespace)
        print(f"  ServiceAccount '{sa_name}' borrada correctamente.")
        return True
    except client.exceptions.ApiException as e:
        if e.status == 404:
            print(f"  ServiceAccount '{sa_name}' no encontrada, omitiendo.")
            return True
        else:
            print(f'  Error al borrar la ServiceAccount "{sa_name}": {e}')
            return False


def borrar_token_service_account(
    cfg: PortainerConfig, core_v1: client.CoreV1Api, instance_id: str, user_id: int
) -> bool:
    """Elimina el Secret de tipo service-account-token asociado al usuario.

    Devuelve True si se borró correctamente.
    """
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    secret_name = f"{instance_id}-{sa_name}-secret"
    try:
        core_v1.delete_namespaced_secret(name=secret_name, namespace=cfg.configmap_namespace)
        print(f"  Secret '{secret_name}' borrado correctamente.")
        return True
    except client.exceptions.ApiException as e:
        if e.status == 404:
            print(f"  Secret '{secret_name}' no encontrado, omitiendo.")
            return True
        else:
            print(f'  Error al borrar el Secret "{secret_name}": {e}')
            return False


def eliminar_subject_cluster_role_binding(
    rbac_v1: client.RbacAuthorizationV1Api, instance_id: str, user_id: int
) -> bool:
    """Elimina la ServiceAccount del usuario del ClusterRoleBinding portainer-crb-user.

    Devuelve True si se actualizó correctamente.
    """
    sa_name = f"portainer-sa-user-{instance_id}-{user_id}"
    try:
        crb = rbac_v1.read_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME)
    except client.exceptions.ApiException as e:
        print(f'  Error al leer el ClusterRoleBinding: {e}')
        return False

    subjects = crb.subjects or []
    nuevos_subjects = [s for s in subjects if s.name != sa_name]

    if len(nuevos_subjects) == len(subjects):
        print(f"  ServiceAccount '{sa_name}' no encontrada en el ClusterRoleBinding, omitiendo.")
        return True

    crb.subjects = nuevos_subjects
    try:
        rbac_v1.replace_cluster_role_binding(name=CLUSTER_ROLE_BINDING_NAME, body=crb)
        print(f"  ClusterRoleBinding '{CLUSTER_ROLE_BINDING_NAME}' actualizado: eliminada ServiceAccount={sa_name}")
        return True
    except client.exceptions.ApiException as e:
        print(f'  Error al actualizar el ClusterRoleBinding: {e}')
        return False
