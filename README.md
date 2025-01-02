# portainer-users

Scripts para crear usuarios en Portainer.

## Configuración

1. [Settings](https://kubernetes.arriaga.eu/#!/settings)

    - Deshabilitar `Allow stacks functionality with Kubernetes environments`.

2. [Authentication](https://kubernetes.arriaga.eu/#!/settings/auth)

    - Cambiar la longitud de contraseña a 10 caracteres.

3. [Kubernetes features configuration](https://kubernetes.arriaga.eu/#!/1/kubernetes/cluster/configure)

    - Habilitar `Restrict access to the default namespace`.
    - Habilitar `rook-ceph-block`.

4. Crear los usuarios y namespaces con el script.

5. [Darles acceso al entorno](https://kubernetes.arriaga.eu/#!/endpoints/1/access)

6. [Darles acceso a su propio namespace](https://kubernetes.arriaga.eu/#!/1/kubernetes/pools)

## Referencias

- [Portainer API documentation](https://app.swaggerhub.com/apis/portainer/portainer-ce)
- [HTTPie](https://httpie.io)
- [Requests: HTTP for Humans](https://requests.readthedocs.io/en/latest/)
