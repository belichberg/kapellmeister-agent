from typing import Dict, List

import requests

from src.models import Container


def http_get_containers(url: str, key: str, agent: str = "kapellmeister-agent", timout: int = 60) -> List[Container]:
    headers: Dict = {
        "Authorization": f"Token {key}",
        "User-Agent": agent,
        "Accept-Encoding": "gzip, deflate, *",
        "Cache-Control": "no-cache",
        "Connection": "close",
    }

    try:
        with requests.get(url, headers=headers, timeout=timout) as r:
            # raise for status
            r.raise_for_status()

            if r.ok:
                containers: dict = r.json()
                return [Container.parse_obj(c) for c in containers]

    except requests.RequestException as err:
        print(err)

    # return empty list
    return []
