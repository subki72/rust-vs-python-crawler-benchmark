use crate::models::{HnResponse, SocialPost};
use anyhow::Context;

/// Deserializes a raw JSON string into a vector of strongly-typed `SocialPost` domain entities.
///
/// Employs zero-copy deserialization where applicable to minimize memory footprint.
///
/// # Errors
/// Returns an `anyhow::Error` if the payload does not conform to the expected schema.
pub fn parse_hn_json(json_text: &str, category: &str) -> anyhow::Result<(Vec<SocialPost>, usize)> {
    let response: HnResponse = serde_json::from_str(json_text)
        .context("Failed to deserialize Hacker News API JSON payload")?;
    let nb_pages = response.nb_pages.unwrap_or(1);

    let posts = response
        .hits
        .into_iter()
        .map(|hit| {
            let title = hit.title.or(hit.story_title).unwrap_or_else(|| "No Title".to_string());
            let author = hit.author.unwrap_or_else(|| "[anonymous]".to_string());
            let url = hit.url.or(hit.story_url).unwrap_or_default();
            let score = hit.points.unwrap_or(0);
            let num_comments = hit.num_comments.unwrap_or(0);
            let created_utc = hit.created_at_i.unwrap_or(0.0);

            SocialPost {
                id: hit.object_id,
                title,
                author,
                score,
                num_comments,
                url,
                created_utc,
                selftext: hit.story_text,
                category: category.to_string(),
            }
        })
        .collect();

    Ok((posts, nb_pages))
}