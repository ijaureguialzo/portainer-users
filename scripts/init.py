"""Inicialización: verifica el acceso a la API de Portainer y, si es necesario,
solicita credenciales para obtener un nuevo token JWT.
"""

import getpass
import os
import sys

import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings()

load_dotenv()

TOKEN_PATH = '/secrets/.token'
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


def main() -> None:
    token = _leer_token()

    if _verificar_acceso(token):
        print('✓ Acceso a la API de Portainer verificado correctamente.')
        return

    print('No se pudo acceder a la API de Portainer con el token actual.')
    print('Por favor, introduce tus credenciales:')

    username = input('Usuario: ').strip()
    password = getpass.getpass('Contraseña: ')

    jwt = _autenticar(username, password)
    if not jwt:
        print('✗ No se pudo obtener un token válido. Verifica las credenciales.')
        sys.exit(1)

    _guardar_token(jwt)
    print('Token JWT guardado en .token.')

    if _verificar_acceso(jwt):
        print('✓ Acceso a la API de Portainer verificado correctamente.')
    else:
        print('✗ El token obtenido no permite acceder a la API de Portainer.')
        sys.exit(1)


if __name__ == '__main__':
    main()
