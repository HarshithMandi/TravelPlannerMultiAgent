from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ReviewStatus(BaseModel):
    approved: bool = False
    reasons: List[str] = []


class PDFStatus(BaseModel):
    path: Optional[str] = None
    generated: bool = False


class TripPlannerState(BaseModel):
    session_id: str
    user_profile: Dict = Field(default_factory=dict)
    trip_preferences: Dict = Field(default_factory=dict)
    memory_context: Dict = Field(default_factory=dict)
    weather_data: Dict = Field(default_factory=dict)
    transport_data: Dict = Field(default_factory=dict)
    hotel_data: Dict = Field(default_factory=dict)
    places_data: Dict = Field(default_factory=dict)
    budget_summary: Dict = Field(default_factory=dict)
    itinerary: Dict = Field(default_factory=dict)
    food_recommendations: Dict = Field(default_factory=dict)
    emergency_tips: Dict = Field(default_factory=dict)
    review_status: ReviewStatus = Field(default_factory=ReviewStatus)
    pdf_status: PDFStatus = Field(default_factory=PDFStatus)
    orchestrator_decision: Dict = Field(default_factory=dict)
    errors: List[Dict] = Field(default_factory=list)
    warnings: List[Dict] = Field(default_factory=list)
    retry_counts: Dict = Field(default_factory=dict)
    final_output: Dict = Field(default_factory=dict)
