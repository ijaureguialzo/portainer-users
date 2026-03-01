import click

from portainer_lib import (
    borrar_namespace,
    borrar_usuario,
    eliminar_entradas_configmap,
    generar_nombres_usuarios,
    get_k8s_clients,
    load_config,
)

cfg = load_config()
k8s_core_v1 = get_k8s_clients()

print("--- Datos de borrado de usuarios ---")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)

usuarios = generar_nombres_usuarios(nombre, separador, inicial, final)
print(f"\nSe van a borrar {len(usuarios)} usuario(s): {usuarios[0]} … {usuarios[-1]}")
click.confirm("¿Confirmas el borrado?", abort=True)

namespaces_borrados: list[str] = []

for usuario in usuarios:
    print(f"\nBorrando el usuario '{usuario}' y sus recursos asociados...")
    borrar_usuario(cfg, usuario)
    if borrar_namespace(cfg, usuario):
        namespaces_borrados.append(usuario)

print("\nActualizando el ConfigMap para eliminar las entradas borradas...")
eliminar_entradas_configmap(cfg, k8s_core_v1, usuarios)

print("\n¡Proceso de borrado finalizado!")
