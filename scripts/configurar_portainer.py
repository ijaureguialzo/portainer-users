import sys

import click

from portainer_lib import (
    configurar_ajustes,
    load_config,
)

cfg = load_config()

if not cfg.kubectl_shell_image:
    print("Error: la variable de entorno KUBECTL_SHELL_IMAGE no está definida.")
    sys.exit(1)

print("--- Configuración de ajustes de Portainer ---")
print(f"\nSe va a actualizar el ajuste:")
print(f"  KubectlShellImage = {cfg.kubectl_shell_image}")
respuesta = click.prompt("¿Confirmas el cambio? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

print("\nAplicando ajustes en Portainer...")
configurar_ajustes(cfg, {"KubectlShellImage": cfg.kubectl_shell_image})
