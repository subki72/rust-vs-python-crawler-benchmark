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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn social_post_roundtrip_serializes_consistently() {
        let post = SocialPost {
            id: "42".to_string(),
            title: "Rust Async".to_string(),
            author: "ferris".to_string(),
            score: 120,
            num_comments: 14,
            url: "https://example.org/rust".to_string(),
            created_utc: 1_700_000_000.0,
            selftext: None,
            category: "rust".to_string(),
        };

        let serialized = serde_json::to_string(&post).expect("serialize SocialPost");
        let deserialized: SocialPost =
            serde_json::from_str(&serialized).expect("deserialize SocialPost");
        assert_eq!(post, deserialized);
    }

    #[test]
    fn hn_response_handles_missing_optional_fields() {
        let raw = r#"{"hits":[{"objectID":"101"}]}"#;
        let parsed: HnResponse = serde_json::from_str(raw).expect("parse HnResponse");
        assert_eq!(parsed.hits.len(), 1);
        assert_eq!(parsed.hits[0].object_id, "101");
        assert!(parsed.nb_pages.is_none());
        assert!(parsed.hits[0].title.is_none());
    }
}
