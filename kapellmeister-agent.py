import logging
from pathlib import Path
from time import sleep
from typing import List, Set, Tuple

import docker
from docker.models.containers import Container as DockerContainer
from envyaml import EnvYAML

# read env.yaml config file
from src.helpers import http_get_containers
from src.models import Container

# create log
logging.basicConfig(format="%(asctime)-15s | %(message)s", level=logging.INFO)
log = logging.getLogger()

# create env file reader
env = EnvYAML()


def containers_diff(actual: DockerContainer, container: Container) -> bool:
    # check environment
    if any([env_ not in actual.attrs["Config"]["Env"] for env_ in container.parameters.environment]):
        return True

    if actual.attrs.get("Image", "") != container.digest:
        return True

    return False


def containers_check(
    client: docker.DockerClient, containers: List[Container]
) -> Tuple[List[Container], List[Container], List[str]]:
    create: List[Container] = []
    update: List[Container] = []
    remove: List[str] = []

    # get list of containers
    running: List[DockerContainer] = [c for c in client.containers.list(all=True) if c.name != env["name"]]

    # requests
    requested_names: Set[str] = {c.parameters.name for c in containers}
    running_names: Set[str] = {r.name for r in running}

    # find new container to run
    for container in containers:
        if container.parameters.name not in running_names:
            create.append(container)

    # find containers to remove
    for r_name in running_names:
        if r_name not in requested_names:
            remove.append(r_name)

    # find containers to updated
    for actual in running:
        for container in containers:
            if actual.name == container.slug:
                # if update
                if containers_diff(actual, container):
                    update.append(container)

    return create, update, remove


def containers_remove(client: docker.DockerClient, containers: List[str]):
    for name in containers:
        client.containers.get(name).remove(force=True)


def containers_start(client: docker.DockerClient, containers: List[Container]):
    docker_config_path: Path = Path.joinpath(Path.home(), ".docker", "config.json")

    for container in containers:
        # create auth
        if container.auth:
            with open(docker_config_path, "w") as fp:
                fp.write(container.auth)

        client.containers.run(**container.parameters.dict(), detach=True, restart_policy=dict(Name="always"))

        # remove auth
        if container.auth:
            docker_config_path.unlink(missing_ok=True)


def containers_update(client: docker.DockerClient, containers: List[Container]):
    for container in containers:
        # remove
        containers_remove(client, [container.slug])

        # remove image
        client.images.remove(image=container.parameters.image, force=True)

        # start over
        containers_start(client, [container])


def app_main():
    # get containers from management server
    management_url: str = env["management.url"]
    management_project: str = env["management.project"]
    management_channel: str = env["management.channel"]

    # get docker client
    client = docker.from_env()

    # endless loop
    while True:
        url: str = f"{management_url}/{management_project}/{management_channel}/"
        log.info(f"Get containers from management server. Url: {url}")
        containers = http_get_containers(url, key=env["management.key"])

        # if some containers exists
        if containers:
            # get container lists
            create, update, remove = containers_check(client, containers)

            log.info(f"Found {len(create)} create, {len(update)} update, {len(remove)} remove")

            # remove containers
            containers_remove(client, remove)

            # start containers
            containers_start(client, create)

            # containers update
            containers_update(client, update)

        # time to sleep
        sleep(env["request.timeout"])


if __name__ == "__main__":
    app_main()
