use serde::{Deserialize, Serialize};

/// Canonical domain model representing a social media post across the ingestion pipeline.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SocialPost {
    pub id: String,
    pub title: String,
    pub author: String,
    pub score: i64,
    pub num_comments: i64,
    pub url: String,
    pub created_utc: f64,
    pub selftext: Option<String>,
    pub category: String,
}

/// Paginated API response structure from the Hacker News Algolia endpoint.
#[derive(Debug, Deserialize)]
pub struct HnResponse {
    pub hits: Vec<HnHit>,
    #[serde(rename = "nbPages", default)]
    pub nb_pages: Option<usize>,
}

/// Raw payload item representing an individual submission returned by Algolia API.
#[derive(Debug, Deserialize)]
pub struct HnHit {
    #[serde(rename = "objectID")]
    pub object_id: String,
    pub title: Option<String>,
    pub story_title: Option<String>,
    pub author: Option<String>,
    pub points: Option<i64>,
    pub num_comments: Option<i64>,
    pub url: Option<String>,
    pub story_url: Option<String>,
    pub created_at_i: Option<f64>,
    pub story_text: Option<String>,
}