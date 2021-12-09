import logging
from pathlib import Path
from time import sleep
from typing import List, Set, Tuple

import docker
import sentry_sdk
from docker.errors import DockerException, APIError
from docker.models.containers import Container as DockerContainer
from docker.models.images import Image
from envyaml import EnvYAML

# read env.yaml config file
from src.helpers import http_get_containers
from src.models import Container

# create log
logging.basicConfig(format="%(asctime)-15s | %(message)s", level=logging.INFO)
log = logging.getLogger()

# create env file reader
env = EnvYAML()

if not env.get("DEBUG"):
    sentry_sdk.init(env.get("SENTRY_DSN"), traces_sample_rate=1.0)


def get_local_image_digest(client: docker.DockerClient, image: str) -> str:
    image_digest: str = ""

    images: list[Image] = client.images.list(image)

    if images and images[0].attrs["RepoDigests"]:
        return images[0].attrs["RepoDigests"][0].split("@")[1]

    return image_digest


def get_registry_image_digest(client: docker.DockerClient, image: str) -> str:
    image_digest: str = ""

    try:
        return client.images.get_registry_data(image).id

    except APIError:
        pass

    return image_digest


def containers_diff(client: docker.DockerClient, actual: DockerContainer, container: Container) -> bool:
    image: str = container.parameters.image

    # check environment
    if any([env_ not in actual.attrs["Config"]["Env"] for env_ in container.parameters.environment]):
        return True

    # check image digest with registry, if different then update
    if get_local_image_digest(client, image) != get_registry_image_digest(client, image):
        return True

    return False


def containers_check(
        client: docker.DockerClient, containers: List[Container]
) -> Tuple[List[Container], List[Container], List[str]]:
    create: List[Container] = []
    update: List[Container] = []
    remove: List[str] = []

    # delete stopped containers
    client.containers.prune()

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
                if containers_diff(client, actual, container):
                    update.append(container)

    return create, update, remove


def containers_remove(client: docker.DockerClient, containers: List[str], remove_image: bool = False):
    for name in containers:
        try:
            container: DockerContainer = client.containers.get(name)

            # remove container
            container.remove(force=True)

            # remove image
            if remove_image:
                client.images.remove(image=container.image.tags[0], force=True)

        except DockerException as err:
            print("Docker remove exception:", err)


def containers_start(client: docker.DockerClient, containers: List[Container]):
    docker_config_path: Path = Path.joinpath(Path.home(), ".docker", "config.json")

    # create new containers
    for container in containers:
        # create auth
        if container.auth:
            # create a .docker folder
            Path.joinpath(Path.home(), ".docker").mkdir(parents=True, exist_ok=True)

            # write config
            with docker_config_path.open("w") as fp:
                fp.write(container.auth)
        try:
            client.containers.run(
                **container.parameters.dict(exclude_unset=True), detach=True, restart_policy=dict(Name="always")
            )

            log.info(f"Start container: {container.parameters.name}")
        except DockerException as err:
            print("Docker start exception:", err)

        # remove auth
        if container.auth:
            docker_config_path.unlink(missing_ok=True)


def containers_update(client: docker.DockerClient, containers: List[Container]):
    for container in containers:
        # remove
        containers_remove(client, [container.parameters.name], remove_image=True)

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
