import sys
from pathlib import Path

import click

from portainer_lib import (
    configurar_ajustes,
    configurar_endpoint,
    configurar_storage_classes,
    load_config,
    marcar_namespaces_sistema,
)

SCRIPTS_DIR = Path(__file__).parent
cfg = load_config()

if not cfg.kubectl_shell_image:
    print("Error: la variable de entorno KUBECTL_SHELL_IMAGE no está definida.")
    sys.exit(1)

AJUSTES = {
    "KubectlShellImage": cfg.kubectl_shell_image,
    "InternalAuthSettings": {
        "RequiredPasswordLength": 10,
    },
    "GlobalDeploymentOptions": {
        "hideStacksFunctionality": True,
    },
}

# ---------------------------------------------------------------------------
# Ajustes generales
# ---------------------------------------------------------------------------
print("--- Configuración de ajustes de Portainer ---")
print("\nSe van a actualizar los siguientes ajustes:")
print(f"  KubectlShellImage = {cfg.kubectl_shell_image}")
print(f"  InternalAuthSettings.RequiredPasswordLength = 10")
print(f"  GlobalDeploymentOptions.hideStacksFunctionality = true")
respuesta = click.prompt("¿Confirmas el cambio? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

print("\nAplicando ajustes en Portainer...")
configurar_ajustes(cfg, AJUSTES)

# ---------------------------------------------------------------------------
# Configuración del endpoint
# ---------------------------------------------------------------------------
print("\n--- Configuración del endpoint de Portainer ---")
print("\nSe van a actualizar las siguientes propiedades del endpoint 1:")
print(f"  Name                       = {cfg.endpoint_name}")
print(f"  PublicURL                  = {cfg.endpoint_public_url}")
print(f"  RestrictDefaultNamespace   = {cfg.endpoint_restrict_default_namespace}")
print(f"  AllowNoneIngressClass      = {cfg.endpoint_allow_none_ingress_class}")
respuesta = click.prompt("¿Confirmas el cambio? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

print("\nAplicando configuración del endpoint en Portainer...")
ok_endpoint = configurar_endpoint(cfg)
if not ok_endpoint:
    print("Error al configurar el endpoint. Revisa los mensajes anteriores.")
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Storage Classes
# ---------------------------------------------------------------------------
STORAGE_CLASSES_FILE = SCRIPTS_DIR / 'storageclasses.json'
print("\n--- Configuración de Storage Classes ---")
print(f"\nSe actualizarán las StorageClasses del endpoint 1 con el contenido de:")
print(f"  {STORAGE_CLASSES_FILE}")
respuesta = click.prompt("¿Confirmas el cambio? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

print("\nAplicando StorageClasses en Portainer...")
ok_sc = configurar_storage_classes(cfg, str(STORAGE_CLASSES_FILE))
if not ok_sc:
    print("Error al configurar las StorageClasses. Revisa los mensajes anteriores.")
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Marcar namespaces de sistema
# ---------------------------------------------------------------------------
print("\n--- Marcar namespaces de sistema ---")
print(
    f"\nNamespaces que se mantendrán como normales (NON_SYSTEM_NAMESPACES): "
    f"{cfg.system_namespaces or ['(ninguno)']}"
)
print("El resto de namespaces del endpoint se marcarán como 'sistema'.")
respuesta = click.prompt("¿Confirmas el cambio? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

print("\nAplicando cambios de namespaces en Portainer...")
ok = marcar_namespaces_sistema(cfg)

if ok:
    print("\n¡Proceso completado correctamente!")
else:
    print("\nEl proceso finalizó con algún error. Revisa los mensajes anteriores.")
    raise SystemExit(1)
