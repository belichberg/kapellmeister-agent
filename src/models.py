from typing import List, Optional, Dict

from pydantic import BaseModel


class ContainerParameters(BaseModel):
    name: str
    image: str
    environment: List[str] = []
    network_mode: Optional[str]
    cpu_period: Optional[int]
    cpu_quota: Optional[int]
    devices: Optional[List[str]]
    tmpfs: Optional[Dict]
    volumes: Optional[Dict]
    nano_cpus: Optional[int]
    ports: Optional[Dict]
    privileged: Optional[bool]
    cap_add: Optional[List[str]]


class Container(BaseModel):
    auth: str
    slug: str
    digest: str
    parameters: ContainerParameters
