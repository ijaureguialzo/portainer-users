"""Tests de integración para crear_usuarios.py y borrar_usuarios.py.

Ejecutan los scripts completos mockeando las dependencias externas
(Portainer API, Kubernetes API, fichero de token, prompts de Click).
"""

import json
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest

from portainer_lib import PortainerConfig


# ===================================================================
# Helpers
# ===================================================================

def _cfg_test():
    """PortainerConfig de prueba."""
    return PortainerConfig(
        portainer_url="http://portainer-test",
        configmap_name="portainer-config",
        configmap_namespace="portainer",
        configmap_key="NamespaceAccessPolicies",
        k8s_timeout=5,
        k8s_max_retries=2,
        token="test-token",
    )


def _fake_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ===================================================================
# crear_usuarios.py — ejecución completa
# ===================================================================

class TestCrearUsuariosApp:
    """Ejecuta crear_usuarios.py de principio a fin con mocks."""

    @patch("portainer_lib.config")
    @patch("portainer_lib.client")
    @patch("portainer_lib.requests")
    def test_crea_dos_usuarios_completo(self, mock_requests, mock_k8s_client, mock_k8s_config):
        # -- K8s clients --
        mock_core = MagicMock()
        mock_rbac = MagicMock()
        mock_k8s_client.CoreV1Api.return_value = mock_core
        mock_k8s_client.RbacAuthorizationV1Api.return_value = mock_rbac
        mock_k8s_client.exceptions = pytest.importorskip("kubernetes").client.exceptions

        # ConfigMap para lectura
        cm = MagicMock()
        cm.data = {"NamespaceAccessPolicies": "{}"}
        mock_core.read_namespaced_config_map.return_value = cm

        # CRB para lectura
        crb = MagicMock()
        crb.subjects = []
        mock_rbac.read_cluster_role_binding.return_value = crb

        # -- Portainer API responses --
        status_resp = _fake_response(200, {"InstanceID": "inst-test"})
        user_resp_1 = _fake_response(200, {"Id": 101})
        user_resp_2 = _fake_response(200, {"Id": 102})
        endpoint_resp = _fake_response(200, {"UserAccessPolicies": {}})
        ok_resp = _fake_response(200)
        ns_resp = _fake_response(200)

        # Secuencia de llamadas requests: get(status), post(user1), get(endpoint), put(endpoint),
        # post(ns1), get(status ya cacheado)... para 2 usuarios
        mock_requests.get.side_effect = [
            status_resp,      # get_instance_id
            endpoint_resp,    # asignar_acceso_endpoint user1
            endpoint_resp,    # asignar_acceso_endpoint user2
        ]
        mock_requests.post.side_effect = [
            user_resp_1,  # crear_usuario user1
            ns_resp,      # crear_namespace user1
            user_resp_2,  # crear_usuario user2
            ns_resp,      # crear_namespace user2
        ]
        mock_requests.put.side_effect = [ok_resp, ok_resp]
        mock_requests.codes = pytest.importorskip("requests").codes

        # -- Click prompts --
        click_inputs = iter(["test", "-", 1, 2, "password123", "password123"])

        with (
            patch("portainer_lib.open", mock_open(read_data="test-token")),
            patch("builtins.open", mock_open(read_data="test-token")),
            patch("click.prompt", side_effect=click_inputs),
        ):
            # Ejecutar el script como módulo
            if "crear_usuarios" in sys.modules:
                del sys.modules["crear_usuarios"]
            runpy.run_module("crear_usuarios", run_name="__main__", alter_sys=False)

        # Verificaciones
        assert mock_requests.post.call_count == 4  # 2 usuarios + 2 namespaces
        assert mock_requests.put.call_count == 2    # 2 asignaciones de endpoint
        assert mock_core.create_namespaced_service_account.call_count == 2
        assert mock_core.create_namespaced_secret.call_count == 2
        assert mock_rbac.replace_cluster_role_binding.call_count == 2
        assert mock_core.patch_namespaced_config_map.call_count == 1


# ===================================================================
# borrar_usuarios.py — ejecución completa
# ===================================================================

class TestBorrarUsuariosApp:
    """Ejecuta borrar_usuarios.py de principio a fin con mocks."""

    @patch("portainer_lib.config")
    @patch("portainer_lib.client")
    @patch("portainer_lib.requests")
    def test_borra_dos_usuarios_completo(self, mock_requests, mock_k8s_client, mock_k8s_config):
        # -- K8s clients --
        mock_core = MagicMock()
        mock_rbac = MagicMock()
        mock_k8s_client.CoreV1Api.return_value = mock_core
        mock_k8s_client.RbacAuthorizationV1Api.return_value = mock_rbac
        mock_k8s_client.exceptions = pytest.importorskip("kubernetes").client.exceptions

        # CRB mock
        sa1 = SimpleNamespace(name="portainer-sa-user-inst-test-101")
        sa2 = SimpleNamespace(name="portainer-sa-user-inst-test-102")
        crb = MagicMock()
        crb.subjects = [sa1, sa2]
        mock_rbac.read_cluster_role_binding.return_value = crb

        # ConfigMap para lectura
        datos_cm = {
            "test-01": {"UserAccessPolicies": {"101": {"RoleId": 0}}},
            "test-02": {"UserAccessPolicies": {"102": {"RoleId": 0}}},
        }
        cm = MagicMock()
        cm.data = {"NamespaceAccessPolicies": json.dumps(datos_cm)}
        mock_core.read_namespaced_config_map.return_value = cm

        # -- Portainer API responses --
        status_resp = _fake_response(200, {"InstanceID": "inst-test"})
        users_list = [
            {"Username": "test-01", "Id": 101},
            {"Username": "test-02", "Id": 102},
        ]

        endpoint_resp = _fake_response(200, {
            "UserAccessPolicies": {"101": {"RoleId": 0}, "102": {"RoleId": 0}},
        })
        ok_resp = _fake_response(200)
        delete_ok = _fake_response(204)

        # Secuencia de llamadas: get_instance_id, obtener_id user1,
        # get endpoint1, obtener_id user2, get endpoint2, ...
        mock_requests.get.side_effect = [
            status_resp,                               # get_instance_id
            _fake_response(200, users_list),            # obtener_id_usuario user1
            endpoint_resp,                             # revocar_acceso_endpoint user1
            _fake_response(200, users_list),            # obtener_id_usuario (dentro de borrar_usuario) user1
            _fake_response(200, users_list),            # obtener_id_usuario user2
            endpoint_resp,                             # revocar_acceso_endpoint user2
            _fake_response(200, users_list),            # obtener_id_usuario (dentro de borrar_usuario) user2
        ]
        mock_requests.put.side_effect = [ok_resp, ok_resp]  # revocar endpoint x2
        mock_requests.delete.side_effect = [
            delete_ok,  # borrar_usuario user1
            delete_ok,  # borrar_namespace user1
            delete_ok,  # borrar_usuario user2
            delete_ok,  # borrar_namespace user2
        ]
        mock_requests.codes = pytest.importorskip("requests").codes

        # -- Click prompts + confirmación --
        click_inputs = iter(["test", "-", 1, 2])

        with (
            patch("portainer_lib.open", mock_open(read_data="test-token")),
            patch("builtins.open", mock_open(read_data="test-token")),
            patch("click.prompt", side_effect=click_inputs),
            patch("click.confirm", return_value=True),
        ):
            if "borrar_usuarios" in sys.modules:
                del sys.modules["borrar_usuarios"]
            runpy.run_module("borrar_usuarios", run_name="__main__", alter_sys=False)

        # Verificaciones
        assert mock_requests.delete.call_count == 4   # 2 usuarios + 2 namespaces
        assert mock_requests.put.call_count == 2       # 2 revocaciones de endpoint
        assert mock_core.delete_namespaced_service_account.call_count == 2
        assert mock_core.delete_namespaced_secret.call_count == 2
        assert mock_rbac.replace_cluster_role_binding.call_count == 2
        assert mock_core.patch_namespaced_config_map.call_count == 1

