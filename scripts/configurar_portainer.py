import sys

import click

from portainer_lib import (
    configurar_ajustes,
    load_config,
    marcar_namespaces_sistema,
)

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
# Marcar namespaces de sistema
# ---------------------------------------------------------------------------
print("\n--- Marcar namespaces de sistema ---")
print(
    f"\nNamespaces que se mantendrán como normales (SYSTEM_NAMESPACES): "
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
