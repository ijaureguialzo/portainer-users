"""Tests unitarios para portainer_lib — funciones de Kubernetes."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from kubernetes import client

from portainer_lib import (
    actualizar_cluster_role_binding,
    actualizar_configmap,
    borrar_service_account,
    borrar_token_service_account,
    crear_service_account,
    crear_token_service_account,
    eliminar_entradas_configmap,
    eliminar_subject_cluster_role_binding,
    CLUSTER_ROLE_BINDING_NAME,
)


# ===================================================================
# get_k8s_clients
# ===================================================================

class TestGetK8sClients:

    @patch("portainer_lib.client")
    @patch("portainer_lib.config")
    def test_solo_core_v1(self, mock_config, mock_client):
        from portainer_lib import get_k8s_clients

        mock_config.load_incluster_config.side_effect = Exception("no cluster")
        mock_client.CoreV1Api.return_value = "core"

        result = get_k8s_clients(include_rbac=False)
        assert result == "core"
        mock_config.load_kube_config.assert_called_once()

    @patch("portainer_lib.client")
    @patch("portainer_lib.config")
    def test_con_rbac(self, mock_config, mock_client):
        from portainer_lib import get_k8s_clients

        mock_config.load_incluster_config.return_value = None
        mock_client.CoreV1Api.return_value = "core"
        mock_client.RbacAuthorizationV1Api.return_value = "rbac"

        core, rbac = get_k8s_clients(include_rbac=True)
        assert core == "core"
        assert rbac == "rbac"


# ===================================================================
# crear_service_account / borrar_service_account
# ===================================================================

class TestCrearServiceAccount:

    def test_crea_sa(self, cfg, mock_core_v1):
        sa_name = crear_service_account(cfg, mock_core_v1, "inst1", 42)
        assert sa_name == "portainer-sa-user-inst1-42"
        mock_core_v1.create_namespaced_service_account.assert_called_once()

    def test_omite_si_ya_existe(self, cfg, mock_core_v1):
        error_409 = client.exceptions.ApiException(status=409)
        mock_core_v1.create_namespaced_service_account.side_effect = error_409

        sa_name = crear_service_account(cfg, mock_core_v1, "inst1", 42)
        assert sa_name == "portainer-sa-user-inst1-42"

    def test_sale_si_error_distinto(self, cfg, mock_core_v1):
        error_500 = client.exceptions.ApiException(status=500)
        mock_core_v1.create_namespaced_service_account.side_effect = error_500

        with pytest.raises(SystemExit):
            crear_service_account(cfg, mock_core_v1, "inst1", 42)


class TestBorrarServiceAccount:

    def test_borra_sa(self, cfg, mock_core_v1):
        assert borrar_service_account(cfg, mock_core_v1, "inst1", 42) is True
        mock_core_v1.delete_namespaced_service_account.assert_called_once_with(
            name="portainer-sa-user-inst1-42",
            namespace=cfg.configmap_namespace,
        )

    def test_omite_si_no_existe(self, cfg, mock_core_v1):
        mock_core_v1.delete_namespaced_service_account.side_effect = (
            client.exceptions.ApiException(status=404)
        )
        assert borrar_service_account(cfg, mock_core_v1, "inst1", 42) is True

    def test_devuelve_false_si_error(self, cfg, mock_core_v1):
        mock_core_v1.delete_namespaced_service_account.side_effect = (
            client.exceptions.ApiException(status=500)
        )
        assert borrar_service_account(cfg, mock_core_v1, "inst1", 42) is False


# ===================================================================
# crear_token_service_account / borrar_token_service_account
# ===================================================================

class TestCrearTokenServiceAccount:

    def test_crea_secret(self, cfg, mock_core_v1):
        crear_token_service_account(cfg, mock_core_v1, "inst1", 42, "portainer-sa-user-inst1-42")
        mock_core_v1.create_namespaced_secret.assert_called_once()
        body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert body.metadata.name == "inst1-portainer-sa-user-inst1-42-secret"
        assert body.type == "kubernetes.io/service-account-token"

    def test_omite_si_ya_existe(self, cfg, mock_core_v1):
        mock_core_v1.create_namespaced_secret.side_effect = (
            client.exceptions.ApiException(status=409)
        )
        # No debe lanzar excepción
        crear_token_service_account(cfg, mock_core_v1, "inst1", 42, "portainer-sa-user-inst1-42")

    def test_sale_si_error_distinto(self, cfg, mock_core_v1):
        mock_core_v1.create_namespaced_secret.side_effect = (
            client.exceptions.ApiException(status=500)
        )
        with pytest.raises(SystemExit):
            crear_token_service_account(cfg, mock_core_v1, "inst1", 42, "sa")


class TestBorrarTokenServiceAccount:

    def test_borra_secret(self, cfg, mock_core_v1):
        assert borrar_token_service_account(cfg, mock_core_v1, "inst1", 42) is True
        expected_name = "inst1-portainer-sa-user-inst1-42-secret"
        mock_core_v1.delete_namespaced_secret.assert_called_once_with(
            name=expected_name,
            namespace=cfg.configmap_namespace,
        )

    def test_omite_si_no_existe(self, cfg, mock_core_v1):
        mock_core_v1.delete_namespaced_secret.side_effect = (
            client.exceptions.ApiException(status=404)
        )
        assert borrar_token_service_account(cfg, mock_core_v1, "inst1", 42) is True

    def test_devuelve_false_si_error(self, cfg, mock_core_v1):
        mock_core_v1.delete_namespaced_secret.side_effect = (
            client.exceptions.ApiException(status=500)
        )
        assert borrar_token_service_account(cfg, mock_core_v1, "inst1", 42) is False


# ===================================================================
# actualizar_cluster_role_binding / eliminar_subject_cluster_role_binding
# ===================================================================

class TestActualizarClusterRoleBinding:

    def test_anade_subject(self, cfg, mock_rbac_v1):
        crb = MagicMock()
        crb.subjects = []
        mock_rbac_v1.read_cluster_role_binding.return_value = crb

        actualizar_cluster_role_binding(cfg, mock_rbac_v1, "inst1", 42)

        mock_rbac_v1.replace_cluster_role_binding.assert_called_once()
        assert len(crb.subjects) == 1
        assert crb.subjects[0]["name"] == "portainer-sa-user-inst1-42"

    def test_no_duplica_subject(self, cfg, mock_rbac_v1):
        existing = SimpleNamespace(name="portainer-sa-user-inst1-42")
        crb = MagicMock()
        crb.subjects = [existing]
        mock_rbac_v1.read_cluster_role_binding.return_value = crb

        actualizar_cluster_role_binding(cfg, mock_rbac_v1, "inst1", 42)

        assert len(crb.subjects) == 1


class TestEliminarSubjectClusterRoleBinding:

    def test_elimina_subject(self, cfg, mock_rbac_v1):
        sa = SimpleNamespace(name="portainer-sa-user-inst1-42")
        other = SimpleNamespace(name="otro-sa")
        crb = MagicMock()
        crb.subjects = [sa, other]
        mock_rbac_v1.read_cluster_role_binding.return_value = crb

        assert eliminar_subject_cluster_role_binding(cfg, mock_rbac_v1, "inst1", 42) is True
        mock_rbac_v1.replace_cluster_role_binding.assert_called_once()
        assert len(crb.subjects) == 1
        assert crb.subjects[0].name == "otro-sa"

    def test_omite_si_no_existe(self, cfg, mock_rbac_v1):
        crb = MagicMock()
        crb.subjects = []
        mock_rbac_v1.read_cluster_role_binding.return_value = crb

        assert eliminar_subject_cluster_role_binding(cfg, mock_rbac_v1, "inst1", 42) is True
        mock_rbac_v1.replace_cluster_role_binding.assert_not_called()

    def test_devuelve_false_si_error_lectura(self, cfg, mock_rbac_v1):
        mock_rbac_v1.read_cluster_role_binding.side_effect = (
            client.exceptions.ApiException(status=500)
        )
        assert eliminar_subject_cluster_role_binding(cfg, mock_rbac_v1, "inst1", 42) is False


# ===================================================================
# actualizar_configmap
# ===================================================================

class TestActualizarConfigmap:

    def _make_cm(self, cfg, datos=None):
        """Crea un ConfigMap mock con datos opcionales."""
        cm = MagicMock()
        cm.data = {cfg.configmap_key: json.dumps(datos or {})}
        return cm

    def test_actualiza_configmap(self, cfg, mock_core_v1):
        cm = self._make_cm(cfg)
        mock_core_v1.read_namespaced_config_map.return_value = cm

        actualizar_configmap(cfg, mock_core_v1, {"alumno-01": 42})

        mock_core_v1.patch_namespaced_config_map.assert_called_once()
        patch_body = mock_core_v1.patch_namespaced_config_map.call_args.kwargs["body"]
        datos = json.loads(patch_body["data"][cfg.configmap_key])
        assert "alumno-01" in datos
        assert datos["alumno-01"]["UserAccessPolicies"]["42"]["RoleId"] == 0

    def test_preserva_entradas_existentes(self, cfg, mock_core_v1):
        cm = self._make_cm(cfg, {"otro-ns": {"UserAccessPolicies": {"1": {"RoleId": 0}}}})
        mock_core_v1.read_namespaced_config_map.return_value = cm

        actualizar_configmap(cfg, mock_core_v1, {"alumno-01": 42})

        patch_body = mock_core_v1.patch_namespaced_config_map.call_args.kwargs["body"]
        datos = json.loads(patch_body["data"][cfg.configmap_key])
        assert "otro-ns" in datos
        assert "alumno-01" in datos

    def test_crea_configmap_si_no_existe(self, cfg, mock_core_v1):
        mock_core_v1.read_namespaced_config_map.side_effect = [
            client.exceptions.ApiException(status=404),  # primera lectura
            self._make_cm(cfg),  # lectura después de crear
        ]

        actualizar_configmap(cfg, mock_core_v1, {"alumno-01": 42})

        mock_core_v1.create_namespaced_config_map.assert_called_once()
        mock_core_v1.patch_namespaced_config_map.assert_called_once()

    @patch("portainer_lib.time.sleep")
    def test_reintenta_en_conflicto(self, mock_sleep, cfg, mock_core_v1):
        cm = self._make_cm(cfg)
        mock_core_v1.read_namespaced_config_map.return_value = cm
        mock_core_v1.patch_namespaced_config_map.side_effect = [
            client.exceptions.ApiException(status=409),
            None,  # segundo intento OK
        ]

        actualizar_configmap(cfg, mock_core_v1, {"alumno-01": 42})
        mock_sleep.assert_called_once()

    @patch("portainer_lib.time.sleep")
    def test_sale_tras_max_reintentos(self, mock_sleep, cfg, mock_core_v1):
        cm = self._make_cm(cfg)
        mock_core_v1.read_namespaced_config_map.return_value = cm
        mock_core_v1.patch_namespaced_config_map.side_effect = (
            client.exceptions.ApiException(status=409)
        )

        with pytest.raises(SystemExit):
            actualizar_configmap(cfg, mock_core_v1, {"alumno-01": 42})


# ===================================================================
# eliminar_entradas_configmap
# ===================================================================

class TestEliminarEntradasConfigmap:

    def _make_cm(self, cfg, datos=None):
        cm = MagicMock()
        cm.data = {cfg.configmap_key: json.dumps(datos or {})}
        return cm

    def test_elimina_entradas(self, cfg, mock_core_v1):
        datos = {
            "alumno-01": {"UserAccessPolicies": {}},
            "alumno-02": {"UserAccessPolicies": {}},
            "otro": {"UserAccessPolicies": {}},
        }
        cm = self._make_cm(cfg, datos)
        mock_core_v1.read_namespaced_config_map.return_value = cm

        eliminar_entradas_configmap(cfg, mock_core_v1, ["alumno-01", "alumno-02"])

        patch_body = mock_core_v1.patch_namespaced_config_map.call_args.kwargs["body"]
        resultado = json.loads(patch_body["data"][cfg.configmap_key])
        assert "alumno-01" not in resultado
        assert "alumno-02" not in resultado
        assert "otro" in resultado

    def test_no_hace_nada_si_no_hay_entradas(self, cfg, mock_core_v1):
        cm = self._make_cm(cfg, {"otro": {}})
        mock_core_v1.read_namespaced_config_map.return_value = cm

        eliminar_entradas_configmap(cfg, mock_core_v1, ["alumno-01"])

        mock_core_v1.patch_namespaced_config_map.assert_not_called()

    def test_devuelve_si_configmap_no_existe(self, cfg, mock_core_v1):
        mock_core_v1.read_namespaced_config_map.side_effect = (
            client.exceptions.ApiException(status=404)
        )
        # No debe lanzar excepción
        eliminar_entradas_configmap(cfg, mock_core_v1, ["alumno-01"])

    @patch("portainer_lib.time.sleep")
    def test_reintenta_en_conflicto(self, mock_sleep, cfg, mock_core_v1):
        datos = {"alumno-01": {"UserAccessPolicies": {}}}
        cm = self._make_cm(cfg, datos)
        mock_core_v1.read_namespaced_config_map.return_value = cm
        mock_core_v1.patch_namespaced_config_map.side_effect = [
            client.exceptions.ApiException(status=409),
            None,
        ]

        eliminar_entradas_configmap(cfg, mock_core_v1, ["alumno-01"])
        mock_sleep.assert_called_once()

