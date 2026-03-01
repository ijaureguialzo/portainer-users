import click

from portainer_lib import (
    actualizar_cluster_role_binding,
    actualizar_configmap,
    asignar_acceso_endpoint,
    crear_namespace,
    crear_service_account,
    crear_token_service_account,
    crear_usuario,
    generar_nombres_usuarios,
    get_instance_id,
    get_k8s_clients,
    load_config,
)

cfg = load_config()
k8s_core_v1, k8s_rbac_v1 = get_k8s_clients(include_rbac=True)

print("--- Datos del usuario --------------")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)
contrasenya = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Confirmar contraseña")

entradas_configmap: dict[str, int] = {}
instance_id = get_instance_id(cfg)

for usuario in generar_nombres_usuarios(nombre, separador, inicial, final):
    print(f"\nCreando el usuario {usuario} y sus recursos asociados...\n")

    user_id = crear_usuario(cfg, usuario, contrasenya)
    asignar_acceso_endpoint(cfg, user_id)
    sa_name = crear_service_account(cfg, k8s_core_v1, instance_id, user_id)
    crear_token_service_account(cfg, k8s_core_v1, instance_id, sa_name)
    actualizar_cluster_role_binding(cfg, k8s_rbac_v1, instance_id, user_id)
    crear_namespace(cfg, usuario)
    entradas_configmap[usuario] = user_id

print("\nActualizando el ConfigMap con todos los usuarios creados...")
actualizar_configmap(cfg, k8s_core_v1, entradas_configmap)
