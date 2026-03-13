from datetime import datetime

from pydantic import BaseModel, Field


class MapConfigMetadata(BaseModel):
    generator_model: str
    reviewer_model: str
    confidence_scores: dict[str, float]
    polygon_count: int
    polity_count: int
    retry_count: int
    review_decision: str
    known_limitations: list[str] = [
        "Natural Earth uses modern boundaries; historical polities did not follow modern province lines.",
        "polities.json accuracy depends on seeded knowledge base.",
    ]


class MapConfigDocument(BaseModel):
    id: str = Field(..., description="Composite key: {year}_{region}")
    year: int
    region: str
    config: dict
    metadata: MapConfigMetadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
