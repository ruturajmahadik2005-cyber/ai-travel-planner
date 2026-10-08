from datetime import date
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, model_validator

class TravelRequest(BaseModel):
    destination: str = Field(min_length=2)
    start_date: date
    end_date: date
    budget_min: float = Field(ge=0)
    budget_max: float = Field(gt=0)
    interests: list[str] = Field(min_length=1)
    travelers: int = Field(ge=1, le=30)
    currency: str = "USD"

    @model_validator(mode="after")
    def validate_request(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be >= budget_min")
        return self

class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "modify"]
    feedback: Optional[str] = None
    modifications: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_review(self):
        if self.action == "reject" and not self.feedback:
            raise ValueError("feedback is required when rejecting")
        if self.action == "modify" and not self.modifications:
            raise ValueError("modifications are required when modifying")
        return self
