from pydantic import BaseModel


class DeletionImpact(BaseModel):
    title: str
    message: str
    related_itinerary_count: int = 0
