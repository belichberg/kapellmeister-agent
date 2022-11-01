import logging
from time import sleep

import sentry_sdk
from envyaml import EnvYAML

from src.dockers import DockerContainers
from src.helpers import http_get_containers

# create log
logging.basicConfig(format="%(asctime)-15s | %(message)s", level=logging.INFO)
log = logging.getLogger()

# create env file reader
env = EnvYAML()

if not env.get("DEBUG"):
    sentry_sdk.init(env.get("SENTRY_DSN"), traces_sample_rate=1.0)


def app_main():
    # get containers from management server
    management_url: str = env["management.url"]
    management_project: str = env["management.project"]
    management_channel: str = env["management.channel"]

    # client docker client
    client = DockerContainers(env["name"])

    # endless loop
    while True:
        url: str = f"{management_url}/{management_project}/{management_channel}/"
        log.info(f"Get containers from management server. Url: {url}")
        req_containers = http_get_containers(url, key=env["management.key"])

        # if some containers exists
        for req_container in req_containers:
            req_name: str = req_container.parameters.name

            # login
            if client.login(req_container.auth):

                # check client
                if client.check(req_container):
                    log.info(f" - Found container '{req_name}' that need to be updated")

                    # remove old container
                    client.remove(req_name)

                    # start new container
                    client.start(req_container)

        # remove unknown containers
        if req_containers:
            rem_list: set[str] = set([r.name for r in client.containers.values()]).difference(
                [r.parameters.name for r in req_containers]
            )

            for rem_name in rem_list:
                log.info(f"Found container '{rem_name}' to remove")
                client.remove(rem_name)

            # finished
            log.info("Finished")

        # time to sleep
        sleep(env["request.timeout"])


if __name__ == "__main__":
    app_main()
