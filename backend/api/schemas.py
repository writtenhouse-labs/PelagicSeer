from datetime import date

from pydantic import BaseModel, Field, model_validator


class AdviceRequest(BaseModel):
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=2, max_length=40)
    species: str = Field(default="general", min_length=1)
    target_depth_ft: int | None = Field(default=None, ge=0, le=5000)
    # Optional fishing window. Both must be given together; when omitted the
    # advisor treats the request as "today" (live mode). The temporal router
    # uses the range to choose live vs historical vs forecast collection.
    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_date_range(self) -> "AdviceRequest":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        return self
