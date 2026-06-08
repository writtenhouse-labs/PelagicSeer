from pydantic import BaseModel, Field


class AdviceRequest(BaseModel):
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=2, max_length=40)
    species: str = Field(default="general", min_length=1)
    target_depth_ft: int | None = Field(default=None, ge=0, le=5000)
