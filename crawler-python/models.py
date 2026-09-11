from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SocialPost(BaseModel):
    """
    Standardized domain model representing a social media post/discussion item.
    Enforces runtime schema validation and serialization consistency across crawlers.
    """
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str = Field(description="Unique identifier of the post")
    title: str = Field(description="Headline or title of the post")
    author: str = Field(default="[anonymous]", description="Username of the author")
    score: int = Field(default=0, description="Upvotes or points score")
    num_comments: int = Field(default=0, description="Total comment count")
    url: str = Field(default="", description="Original link or destination URL")
    created_utc: float = Field(default=0.0, description="Unix timestamp of post creation")
    selftext: Optional[str] = Field(default=None, description="Body content text if available")
    category: str = Field(description="Topic category or search tag")