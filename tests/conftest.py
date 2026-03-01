"""Fixtures compartidos para la suite de tests de portainer-users."""

import sys
from unittest.mock import MagicMock

import pytest

# Añadir scripts/ al path para poder importar portainer_lib
sys.path.insert(0, "scripts")


# ---------------------------------------------------------------------------
# PortainerConfig de prueba
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg():
    """Devuelve un PortainerConfig con valores de prueba sin leer ficheros."""
    from portainer_lib import PortainerConfig

    return PortainerConfig(
        portainer_url="http://portainer-test",
        configmap_name="portainer-config",
        configmap_namespace="portainer",
        configmap_key="NamespaceAccessPolicies",
        k8s_timeout=5,
        k8s_max_retries=2,
        token="test-token",
    )


# ---------------------------------------------------------------------------
# Clientes K8s mockeados
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_core_v1():
    return MagicMock()


@pytest.fixture
def mock_rbac_v1():
    return MagicMock()


# ---------------------------------------------------------------------------
# Helper para simular respuestas HTTP de requests
# ---------------------------------------------------------------------------

class FakeResponse:
    """Respuesta HTTP falsa para mockear requests.get/post/put/delete."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


@pytest.fixture
def fake_response():
    """Factoría de FakeResponse."""
    return FakeResponse

