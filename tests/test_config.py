"""Tests unitarios para portainer_lib — funciones de configuración y helpers."""

from unittest.mock import mock_open, patch

import pytest

from portainer_lib import PortainerConfig, generar_nombres_usuarios, load_config


# ===================================================================
# load_config
# ===================================================================

class TestLoadConfig:

    def test_carga_valores_por_defecto(self):
        token_content = "mi-token-secreto"
        with patch("builtins.open", mock_open(read_data=token_content)):
            cfg = load_config("/ruta/falsa")

        assert cfg.portainer_url == "http://localhost"
        assert cfg.configmap_name == "portainer-config"
        assert cfg.configmap_namespace == "portainer"
        assert cfg.configmap_key == "NamespaceAccessPolicies"
        assert cfg.k8s_timeout == 30
        assert cfg.k8s_max_retries == 5
        assert cfg.token == "mi-token-secreto"
        assert cfg.headers == {"X-API-Key": "mi-token-secreto"}

    def test_carga_valores_desde_entorno(self, monkeypatch):
        monkeypatch.setenv("PORTAINER_URL", "https://portainer.example.com")
        monkeypatch.setenv("CONFIGMAP_NAME", "mi-cm")
        monkeypatch.setenv("CONFIGMAP_NAMESPACE", "mi-ns")
        monkeypatch.setenv("CONFIGMAP_KEY", "MiClave")
        monkeypatch.setenv("K8S_TIMEOUT", "60")
        monkeypatch.setenv("K8S_MAX_RETRIES", "10")

        with patch("builtins.open", mock_open(read_data="otro-token\n")):
            cfg = load_config("/ruta/falsa")

        assert cfg.portainer_url == "https://portainer.example.com"
        assert cfg.configmap_name == "mi-cm"
        assert cfg.configmap_namespace == "mi-ns"
        assert cfg.configmap_key == "MiClave"
        assert cfg.k8s_timeout == 60
        assert cfg.k8s_max_retries == 10
        assert cfg.token == "otro-token"

    def test_token_strip_whitespace(self):
        with patch("builtins.open", mock_open(read_data="  token-con-espacios  \n")):
            cfg = load_config("/ruta/falsa")
        assert cfg.token == "token-con-espacios"

    def test_fichero_no_encontrado_lanza_excepcion(self):
        with pytest.raises(FileNotFoundError):
            load_config("/ruta/inexistente/token")


# ===================================================================
# PortainerConfig
# ===================================================================

class TestPortainerConfig:

    def test_headers_se_generan_automaticamente(self):
        cfg = PortainerConfig(
            portainer_url="http://x",
            configmap_name="cm",
            configmap_namespace="ns",
            configmap_key="key",
            k8s_timeout=5,
            k8s_max_retries=1,
            token="abc",
        )
        assert cfg.headers == {"X-API-Key": "abc"}

    def test_headers_personalizados_no_se_sobreescriben(self):
        custom = {"Authorization": "Bearer xyz"}
        cfg = PortainerConfig(
            portainer_url="http://x",
            configmap_name="cm",
            configmap_namespace="ns",
            configmap_key="key",
            k8s_timeout=5,
            k8s_max_retries=1,
            token="abc",
            headers=custom,
        )
        assert cfg.headers == custom


# ===================================================================
# generar_nombres_usuarios
# ===================================================================

class TestGenerarNombresUsuarios:

    def test_genera_lista_correcta(self):
        result = generar_nombres_usuarios("user", "-", 1, 3)
        assert result == ["user-01", "user-02", "user-03"]

    def test_un_solo_usuario(self):
        result = generar_nombres_usuarios("admin", ".", 5, 5)
        assert result == ["admin.05"]

    def test_numeros_grandes_con_padding(self):
        result = generar_nombres_usuarios("test", "_", 99, 101)
        assert result == ["test_99", "test_100", "test_101"]

    def test_lista_vacia_si_inicial_mayor_que_final(self):
        result = generar_nombres_usuarios("user", "-", 10, 5)
        assert result == []

