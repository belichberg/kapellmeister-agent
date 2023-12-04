import base64
import json
from typing import Dict, List, Tuple

from docker import DockerClient, from_env
from docker.errors import APIError
from docker.models.containers import Container

from src.models import Container as ReqContainer


class DockerContainers:
    name: str
    client: DockerClient

    def __init__(self, name: str, client: DockerClient = None, timeout: int = 60):
        self.client = client or from_env(timeout=timeout)
        self.name = name

    @property
    def containers(self) -> Dict[str, Container]:
        return {c.name: c for c in self.client.containers.list(all=True) if c.name != self.name}

    def check(self, container: ReqContainer) -> bool:
        try:
            # get all containers
            if container.parameters.name not in self.containers:
                return True

            # check environments attributes
            actual: Container = self.containers[container.parameters.name]
            envs = actual.attrs["Config"]["Env"]

            for req_env in container.parameters.environment:
                if req_env not in envs:
                    return True

            # check image digest or time
            reg_image = self.client.images.get_registry_data(container.parameters.image)

            # local images
            loc_image = self.client.images.get(container.parameters.image)

            # extract digests
            reg_digest: str = reg_image.attrs["Descriptor"]["digest"]
            loc_digest: str = loc_image.attrs["RepoDigests"][0].split("@")[1]

            return reg_digest != loc_digest

        except Exception as err:
            print(err)

        return False

    def remove(self, name: str):
        if name in self.containers:
            # get images
            images: list[str] = self.containers[name].image.tags

            # stop and remove container
            self.containers[name].remove(force=True)

            # remove image
            for image in images:
                self.client.images.remove(image=image, force=True, noprune=True)

            # prune unused images
            self.client.images.prune()

    def login(self, auth: str) -> bool:
        success: bool = False

        # first pass authentication
        for registry, username, password in self.registry_credentials(auth):
            try:
                # use client to authenticate
                self.client.login(username=username, password=password, registry=registry, reauth=True)

                # success
                success = True
            except APIError:
                # ignore ex
                print(f"Login error with registry {registry} and username {username[:8]}...")

        return success

    def start(self, container: ReqContainer):
        try:
            # pull new images
            self.client.images.pull(container.parameters.image)

            # create docker container
            self.client.containers.run(
                **container.parameters.dict(exclude_unset=True),
                detach=True,
                restart_policy=dict(Name="always"),
            )
        except Exception as err:
            print(err)

    @staticmethod
    def registry_credentials(auth: str) -> List[Tuple[str, str, str]]:
        auths: List = []
        parsed: Dict = json.loads(auth)

        if "auths" in parsed:
            for registry, content in parsed["auths"].items():
                if "auth" in content:
                    # extract username / password
                    username, password = base64.b64decode(content["auth"]).decode().split(":")

                    # add to collections
                    auths.append((registry, username, password))

        return auths
