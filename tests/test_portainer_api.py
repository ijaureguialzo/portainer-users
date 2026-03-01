"""Tests unitarios para portainer_lib — funciones de la API de Portainer."""

from unittest.mock import patch

import pytest

from portainer_lib import (
    asignar_acceso_endpoint,
    borrar_namespace,
    borrar_usuario,
    crear_namespace,
    crear_usuario,
    get_instance_id,
    obtener_id_usuario,
    revocar_acceso_endpoint,
)


# ===================================================================
# get_instance_id
# ===================================================================

class TestGetInstanceId:

    @patch("portainer_lib.requests.get")
    def test_devuelve_instance_id(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(200, {"InstanceID": "abc-123"})
        assert get_instance_id(cfg) == "abc-123"
        mock_get.assert_called_once_with(
            "http://portainer-test/api/system/status",
            headers=cfg.headers,
            verify=False,
        )

    @patch("portainer_lib.requests.get")
    def test_sale_con_error_si_falla(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(500)
        with pytest.raises(SystemExit):
            get_instance_id(cfg)


# ===================================================================
# crear_usuario
# ===================================================================

class TestCrearUsuario:

    @patch("portainer_lib.requests.post")
    def test_crea_usuario_y_devuelve_id(self, mock_post, cfg, fake_response):
        mock_post.return_value = fake_response(200, {"Id": 42})
        uid = crear_usuario(cfg, "alumno-01", "pass123")
        assert uid == 42
        mock_post.assert_called_once()
        body = mock_post.call_args.kwargs["json"]
        assert body["username"] == "alumno-01"
        assert body["password"] == "pass123"
        assert body["role"] == 2

    @patch("portainer_lib.requests.post")
    def test_sale_con_error_si_falla(self, mock_post, cfg, fake_response):
        mock_post.return_value = fake_response(409)
        with pytest.raises(SystemExit):
            crear_usuario(cfg, "alumno-01", "pass123")


# ===================================================================
# obtener_id_usuario
# ===================================================================

class TestObtenerIdUsuario:

    @patch("portainer_lib.requests.get")
    def test_devuelve_id_si_existe(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(200, [
            {"Username": "admin", "Id": 1},
            {"Username": "alumno-01", "Id": 42},
        ])
        assert obtener_id_usuario(cfg, "alumno-01") == 42

    @patch("portainer_lib.requests.get")
    def test_devuelve_none_si_no_existe(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(200, [
            {"Username": "admin", "Id": 1},
        ])
        assert obtener_id_usuario(cfg, "noexiste") is None

    @patch("portainer_lib.requests.get")
    def test_devuelve_none_si_error_api(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(500, text="Internal Server Error")
        assert obtener_id_usuario(cfg, "alumno-01") is None


# ===================================================================
# borrar_usuario
# ===================================================================

class TestBorrarUsuario:

    @patch("portainer_lib.requests.delete")
    @patch("portainer_lib.requests.get")
    def test_borra_usuario_existente(self, mock_get, mock_delete, cfg, fake_response):
        mock_get.return_value = fake_response(200, [{"Username": "alumno-01", "Id": 42}])
        mock_delete.return_value = fake_response(204)
        assert borrar_usuario(cfg, "alumno-01") is True

    @patch("portainer_lib.requests.get")
    def test_devuelve_false_si_no_existe(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(200, [])
        assert borrar_usuario(cfg, "noexiste") is False

    @patch("portainer_lib.requests.delete")
    @patch("portainer_lib.requests.get")
    def test_devuelve_false_si_error_al_borrar(self, mock_get, mock_delete, cfg, fake_response):
        mock_get.return_value = fake_response(200, [{"Username": "alumno-01", "Id": 42}])
        mock_delete.return_value = fake_response(500, text="error")
        assert borrar_usuario(cfg, "alumno-01") is False


# ===================================================================
# asignar_acceso_endpoint
# ===================================================================

class TestAsignarAccesoEndpoint:

    @patch("portainer_lib.requests.put")
    @patch("portainer_lib.requests.get")
    def test_asigna_acceso(self, mock_get, mock_put, cfg, fake_response):
        mock_get.return_value = fake_response(200, {"UserAccessPolicies": {}})
        mock_put.return_value = fake_response(200)

        asignar_acceso_endpoint(cfg, 42)

        put_body = mock_put.call_args.kwargs["json"]
        assert "42" in put_body["UserAccessPolicies"]
        assert put_body["UserAccessPolicies"]["42"] == {"RoleId": 0}

    @patch("portainer_lib.requests.put")
    @patch("portainer_lib.requests.get")
    def test_preserva_politicas_existentes(self, mock_get, mock_put, cfg, fake_response):
        existing = {"10": {"RoleId": 0}}
        mock_get.return_value = fake_response(200, {"UserAccessPolicies": existing})
        mock_put.return_value = fake_response(200)

        asignar_acceso_endpoint(cfg, 42)

        put_body = mock_put.call_args.kwargs["json"]
        assert "10" in put_body["UserAccessPolicies"]
        assert "42" in put_body["UserAccessPolicies"]

    @patch("portainer_lib.requests.get")
    def test_sale_con_error_si_get_falla(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(500)
        with pytest.raises(SystemExit):
            asignar_acceso_endpoint(cfg, 42)


# ===================================================================
# revocar_acceso_endpoint
# ===================================================================

class TestRevocarAccesoEndpoint:

    @patch("portainer_lib.requests.put")
    @patch("portainer_lib.requests.get")
    def test_revoca_acceso(self, mock_get, mock_put, cfg, fake_response):
        existing = {"42": {"RoleId": 0}, "10": {"RoleId": 0}}
        mock_get.return_value = fake_response(200, {"UserAccessPolicies": existing})
        mock_put.return_value = fake_response(200)

        assert revocar_acceso_endpoint(cfg, 42) is True

        put_body = mock_put.call_args.kwargs["json"]
        assert "42" not in put_body["UserAccessPolicies"]
        assert "10" in put_body["UserAccessPolicies"]

    @patch("portainer_lib.requests.get")
    def test_omite_si_no_tenia_acceso(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(200, {"UserAccessPolicies": {}})
        assert revocar_acceso_endpoint(cfg, 42) is True

    @patch("portainer_lib.requests.get")
    def test_devuelve_false_si_get_falla(self, mock_get, cfg, fake_response):
        mock_get.return_value = fake_response(500)
        assert revocar_acceso_endpoint(cfg, 42) is False


# ===================================================================
# crear_namespace
# ===================================================================

class TestCrearNamespace:

    @patch("portainer_lib.requests.post")
    def test_crea_namespace(self, mock_post, cfg, fake_response):
        mock_post.return_value = fake_response(200)
        crear_namespace(cfg, "alumno-01")
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["json"] == {"Name": "alumno-01"}

    @patch("portainer_lib.requests.post")
    def test_no_sale_si_falla(self, mock_post, cfg, fake_response):
        mock_post.return_value = fake_response(409)
        # No debe lanzar excepción, sólo imprimir error
        crear_namespace(cfg, "alumno-01")


# ===================================================================
# borrar_namespace
# ===================================================================

class TestBorrarNamespace:

    @patch("portainer_lib.requests.delete")
    def test_borra_namespace(self, mock_delete, cfg, fake_response):
        mock_delete.return_value = fake_response(200)
        assert borrar_namespace(cfg, "alumno-01") is True

    @patch("portainer_lib.requests.delete")
    def test_acepta_204(self, mock_delete, cfg, fake_response):
        mock_delete.return_value = fake_response(204)
        assert borrar_namespace(cfg, "alumno-01") is True

    @patch("portainer_lib.requests.delete")
    def test_devuelve_false_si_error(self, mock_delete, cfg, fake_response):
        mock_delete.return_value = fake_response(500, text="error")
        assert borrar_namespace(cfg, "alumno-01") is False

