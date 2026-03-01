import click

from portainer_lib import (
    borrar_namespace,
    borrar_service_account,
    borrar_token_service_account,
    borrar_usuario,
    eliminar_entradas_configmap,
    eliminar_subject_cluster_role_binding,
    generar_nombres_usuarios,
    get_instance_id,
    get_k8s_clients,
    load_config,
    obtener_id_usuario,
    revocar_acceso_endpoint,
)

cfg = load_config()
k8s_core_v1, k8s_rbac_v1 = get_k8s_clients(include_rbac=True)
instance_id = get_instance_id(cfg)

print("--- Datos de borrado de usuarios ---")
nombre = click.prompt("Nombre de usuario", default="test")
separador = click.prompt("Separador", default="-")
inicial = click.prompt("Número de usuario inicial", default=1)
final = click.prompt("Número de usuario final", default=20)

usuarios = generar_nombres_usuarios(nombre, separador, inicial, final)
print(f"\nSe van a borrar {len(usuarios)} usuario(s): {usuarios[0]} … {usuarios[-1]}")
respuesta = click.prompt("¿Confirmas el borrado? [s/N]", default="N")
if respuesta.lower() not in ("s", "si", "sí"):
    print("Operación cancelada.")
    raise SystemExit(0)

namespaces_borrados: list[str] = []

for usuario in usuarios:
    print(f"\nBorrando el usuario '{usuario}' y sus recursos asociados...")

    # Obtener el ID antes de borrar el usuario (se necesita para los demás recursos)
    user_id = obtener_id_usuario(cfg, usuario)

    if user_id is not None:
        revocar_acceso_endpoint(cfg, user_id)
        borrar_token_service_account(cfg, k8s_core_v1, instance_id, user_id)
        borrar_service_account(cfg, k8s_core_v1, instance_id, user_id)
        eliminar_subject_cluster_role_binding(cfg, k8s_rbac_v1, instance_id, user_id)

    borrar_usuario(cfg, usuario)
    if borrar_namespace(cfg, usuario):
        namespaces_borrados.append(usuario)

print("\nActualizando el ConfigMap para eliminar las entradas borradas...")
eliminar_entradas_configmap(cfg, k8s_core_v1, usuarios)

print("\n¡Proceso de borrado finalizado!")
