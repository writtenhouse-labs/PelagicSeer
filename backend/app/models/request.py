from pydantic import BaseModel, Field


class AdviceRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    species: str = Field(default="general", min_length=1)
    target_depth_ft: int | None = Field(default=None, ge=0, le=5000)
