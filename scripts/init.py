"""Inicialización: verifica el acceso a la API de Portainer y, si es necesario,
solicita credenciales para obtener un nuevo token JWT.
"""

import getpass
import os
import sys

import requests
import urllib3
from dotenv import load_dotenv
from kubernetes import client, config

urllib3.disable_warnings()

load_dotenv()

TOKEN_PATH = '/secrets/.token'
KUBECONFIG_PATH = '/secrets/.kubeconfig'
PORTAINER_URL = os.environ.get('PORTAINER_URL', 'http://localhost')


def _leer_token() -> str:
    """Lee el token del fichero .token. Devuelve cadena vacía si no existe."""
    try:
        with open(TOKEN_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


def _guardar_token(token: str) -> None:
    """Guarda el token en el fichero .token."""
    with open(TOKEN_PATH, 'w') as f:
        f.write(token + '\n')


def _verificar_acceso(token: str) -> bool:
    """Comprueba si el token permite acceder a /api/users/me.

    Devuelve True si el acceso es válido.
    """
    if not token:
        return False
    headers = {'X-API-Key': token} if token.startswith('ptr_') else {'Authorization': f'Bearer {token}'}
    try:
        r = requests.get(
            PORTAINER_URL + '/api/users/me',
            headers=headers,
            verify=False,
            timeout=10,
        )
        return r.status_code == requests.codes.ok
    except requests.RequestException:
        return False


def _autenticar(username: str, password: str) -> str | None:
    """Realiza POST /api/auth con las credenciales proporcionadas.

    Devuelve el JWT obtenido, o None si la autenticación falla.
    """
    try:
        r = requests.post(
            PORTAINER_URL + '/api/auth',
            json={'Username': username, 'Password': password},
            verify=False,
            timeout=10,
        )
        if r.status_code == requests.codes.ok:
            return r.json().get('jwt')
        print(f'Error de autenticación: {r.status_code} {r.text}')
        return None
    except requests.RequestException as e:
        print(f'Error de conexión: {e}')
        return None


def _verificar_kubeconfig(path: str) -> bool:
    """Comprueba si el kubeconfig en *path* permite acceder al cluster.

    Intenta obtener la versión del servidor. Devuelve True si tiene éxito.
    """
    if not os.path.exists(path):
        return False
    try:
        cfg = client.Configuration()
        config.load_kube_config(config_file=path, client_configuration=cfg)
        with client.ApiClient(cfg) as api_client:
            version_api = client.VersionApi(api_client)
            version_api.get_code()
        return True
    except Exception:
        return False


def _descargar_kubeconfig(token: str, path: str) -> bool:
    """Descarga el kubeconfig desde /api/kubernetes/config de Portainer y lo guarda en *path*.

    Devuelve True si tuvo éxito.
    """
    headers = {'X-API-Key': token} if token.startswith('ptr_') else {'Authorization': f'Bearer {token}'}
    try:
        r = requests.get(
            PORTAINER_URL + '/api/kubernetes/config',
            headers=headers,
            verify=False,
            timeout=15,
        )
        if r.status_code != 200:
            print(f'Error al descargar el kubeconfig: {r.status_code} {r.text}')
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(r.text)
        print(f'Kubeconfig guardado en {path}.')
        return True
    except requests.RequestException as e:
        print(f'Error de conexión al descargar kubeconfig: {e}')
        return False


def main() -> None:
    token = _leer_token()

    if _verificar_acceso(token):
        print('✓ Acceso a la API de Portainer verificado correctamente.')
    else:
        print('No se pudo acceder a la API de Portainer con el token actual.')
        print('Por favor, introduce tus credenciales:')

        username = input('Usuario: ').strip()
        password = getpass.getpass('Contraseña: ')

        jwt = _autenticar(username, password)
        if not jwt:
            print('✗ No se pudo obtener un token válido. Verifica las credenciales.')
            sys.exit(1)

        _guardar_token(jwt)
        token = jwt
        print('Token JWT guardado en .token.')

        if _verificar_acceso(token):
            print('✓ Acceso a la API de Portainer verificado correctamente.')
        else:
            print('✗ El token obtenido no permite acceder a la API de Portainer.')
            sys.exit(1)

    # Verificar acceso al cluster Kubernetes
    if _verificar_kubeconfig(KUBECONFIG_PATH):
        print('✓ Acceso al cluster Kubernetes verificado correctamente.')
    else:
        print('El kubeconfig no existe o no permite acceder al cluster. Descargando desde Portainer...')
        if not _descargar_kubeconfig(token, KUBECONFIG_PATH):
            print('✗ No se pudo obtener el kubeconfig desde Portainer.')
            sys.exit(1)
        if _verificar_kubeconfig(KUBECONFIG_PATH):
            print('✓ Acceso al cluster Kubernetes verificado correctamente.')
        else:
            print('✗ El kubeconfig descargado no permite acceder al cluster.')
            sys.exit(1)


if __name__ == '__main__':
    main()
