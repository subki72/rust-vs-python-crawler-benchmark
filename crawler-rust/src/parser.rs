use crate::models::{HnResponse, SocialPost};
use anyhow::{bail, Context};

/// Deserializes a raw JSON string into a vector of strongly-typed `SocialPost` domain entities.
///
/// # Arguments
/// * `json_text` - Raw JSON payload returned by the Hacker News Algolia endpoint.
/// * `category` - Topic category label assigned to parsed posts.
///
/// # Returns
/// Tuple containing parsed `SocialPost` entries and total available pages (`nbPages`).
///
/// # Errors
/// Returns an `anyhow::Error` if the payload is empty or fails JSON schema deserialization.
pub fn parse_hn_json(json_text: &str, category: &str) -> anyhow::Result<(Vec<SocialPost>, usize)> {
    if json_text.trim().is_empty() {
        bail!("Empty JSON payload received from upstream endpoint");
    }

    let response: HnResponse = serde_json::from_str(json_text)
        .context("Failed to deserialize Hacker News API JSON payload")?;
    let nb_pages = response.nb_pages.unwrap_or(1);

    let posts = response
        .hits
        .into_iter()
        .map(|hit| SocialPost {
            id: hit.object_id,
            title: hit
                .title
                .or(hit.story_title)
                .unwrap_or_else(|| "No Title".to_string()),
            author: hit.author.unwrap_or_else(|| "[anonymous]".to_string()),
            score: hit.points.unwrap_or(0),
            num_comments: hit.num_comments.unwrap_or(0),
            url: hit.url.or(hit.story_url).unwrap_or_default(),
            created_utc: hit.created_at_i.unwrap_or(0.0),
            selftext: hit.story_text,
            category: category.to_string(),
        })
        .collect();

    Ok((posts, nb_pages))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_hn_json_valid_payload_maps_fields() {
        let payload = r#"{
            "nbPages": 5,
            "hits": [{
                "objectID": "99",
                "title": "Tokio Runtime Internals",
                "author": "alice",
                "points": 250,
                "num_comments": 44,
                "url": "https://example.com/tokio",
                "created_at_i": 1700000100,
                "story_text": null
            }]
        }"#;

        let (posts, nb_pages) = parse_hn_json(payload, "rust").expect("valid payload");
        assert_eq!(nb_pages, 5);
        assert_eq!(posts.len(), 1);
        assert_eq!(posts[0].id, "99");
        assert_eq!(posts[0].title, "Tokio Runtime Internals");
        assert_eq!(posts[0].author, "alice");
        assert_eq!(posts[0].score, 250);
        assert_eq!(posts[0].category, "rust");
    }

    #[test]
    fn parse_hn_json_uses_fallbacks_when_optional_fields_absent() {
        let payload = r#"{
            "hits": [{
                "objectID": "77",
                "story_title": "Ask HN Fallback",
                "story_url": "https://news.ycombinator.com/item?id=77"
            }]
        }"#;

        let (posts, nb_pages) = parse_hn_json(payload, "python").expect("fallback payload");
        assert_eq!(nb_pages, 1);
        assert_eq!(posts[0].title, "Ask HN Fallback");
        assert_eq!(posts[0].author, "[anonymous]");
        assert_eq!(posts[0].url, "https://news.ycombinator.com/item?id=77");
        assert_eq!(posts[0].score, 0);
    }

    #[test]
    fn parse_hn_json_rejects_empty_or_invalid_json() {
        assert!(parse_hn_json("   ", "rust").is_err());
        assert!(parse_hn_json("{not-json", "rust").is_err());
    }
}
