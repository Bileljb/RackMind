from pydantic import BaseModel, ConfigDict

from app.models import ServerSource


class RackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rack_id: int
    hostname: str
    rack_unit: int
    source: ServerSource
