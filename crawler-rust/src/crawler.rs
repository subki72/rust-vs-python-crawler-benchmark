use crate::models::SocialPost;
use crate::parser::parse_hn_json;
use anyhow::{bail, Context};
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, USER_AGENT};
use reqwest::StatusCode;
use std::sync::Arc;
use tokio::sync::Semaphore;
use tokio::time::{sleep, Duration};

const BASE_HN_SEARCH_URL: &str = "https://hn.algolia.com/api/v1/search";
const MAX_RETRIES: u32 = 3;
const BASE_BACKOFF_MS: u64 = 300;
const REQUEST_TIMEOUT_SECS: u64 = 15;

/// Checks whether an HTTP status code represents a transient retryable error.
fn is_retryable_status(status: StatusCode) -> bool {
    status == StatusCode::TOO_MANY_REQUESTS || status.is_server_error()
}

/// Computes bounded exponential backoff delay in milliseconds.
fn compute_backoff_ms(attempt: u32) -> u64 {
    BASE_BACKOFF_MS.saturating_mul(1_u64 << attempt)
}

/// Asynchronous, high-concurrency crawler client for social data ingestion.
pub struct SocialCrawlerRust {
    client: reqwest::Client,
    semaphore: Arc<Semaphore>,
}

impl SocialCrawlerRust {
    /// Instantiates a new crawler client with bounded concurrency and connection pooling.
    ///
    /// # Errors
    /// Returns an error if `max_concurrency` is zero or the HTTP client fails to initialize.
    pub fn try_new(max_concurrency: usize) -> anyhow::Result<Self> {
        if max_concurrency == 0 {
            bail!("max_concurrency must be at least 1");
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            USER_AGENT,
            HeaderValue::from_static("SocialBenchmarkCrawler/1.0 (Educational Ingestion Lab)"),
        );
        headers.insert(ACCEPT, HeaderValue::from_static("application/json"));

        let client = reqwest::Client::builder()
            .default_headers(headers)
            .connect_timeout(Duration::from_secs(5))
            .timeout(Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .pool_idle_timeout(Duration::from_secs(30))
            .pool_max_idle_per_host(10)
            .tcp_keepalive(Duration::from_secs(60))
            .build()
            .context("Failed to initialize reqwest HTTP client")?;

        Ok(Self {
            client,
            semaphore: Arc::new(Semaphore::new(max_concurrency)),
        })
    }

    async fn fetch_once(&self, url: &str) -> anyhow::Result<String> {
        let _permit = self
            .semaphore
            .acquire()
            .await
            .context("Crawler concurrency semaphore closed")?;
        let response = self.client.get(url).send().await?;
        let text = response.error_for_status()?.text().await?;
        Ok(text)
    }

    /// Performs an asynchronous HTTP GET request with bounded exponential-backoff retries.
    ///
    /// # Errors
    /// Returns an `anyhow::Error` when retries are exhausted or a non-retryable error occurs.
    pub async fn fetch_page(&self, url: &str) -> anyhow::Result<String> {
        for attempt in 0..=MAX_RETRIES {
            match self.fetch_once(url).await {
                Ok(text) => return Ok(text),
                Err(err) => {
                    let retryable = err.downcast_ref::<reqwest::Error>().is_some_and(|req_err| {
                        req_err.is_timeout()
                            || req_err.is_connect()
                            || req_err.status().is_some_and(is_retryable_status)
                    });
                    if !retryable || attempt == MAX_RETRIES {
                        return Err(err.context(format!("HTTP request failed for {url}")));
                    }
                    sleep(Duration::from_millis(compute_backoff_ms(attempt))).await;
                }
            }
        }
        bail!("Exhausted retries for {url}")
    }

    /// Crawls a specific topic keyword across paginated API requests.
    pub async fn crawl_topic(
        &self,
        topic: &str,
        max_pages: usize,
        hits_per_page: usize,
    ) -> Vec<SocialPost> {
        if topic.trim().is_empty() || max_pages == 0 {
            return Vec::new();
        }

        let mut all_posts = Vec::new();
        for page in 0..max_pages {
            let Ok(parsed_url) = reqwest::Url::parse_with_params(
                BASE_HN_SEARCH_URL,
                &[
                    ("query", topic.trim()),
                    ("hitsPerPage", &hits_per_page.to_string()),
                    ("page", &page.to_string()),
                ],
            ) else {
                eprintln!("[Rust Crawler] Invalid URL parameters for topic '{topic}'");
                break;
            };

            if !self
                .ingest_page(parsed_url.as_str(), topic, page, &mut all_posts)
                .await
            {
                break;
            }
            sleep(Duration::from_millis(100)).await;
        }
        all_posts
    }

    async fn ingest_page(
        &self,
        url: &str,
        topic: &str,
        page: usize,
        sink: &mut Vec<SocialPost>,
    ) -> bool {
        let content = match self.fetch_page(url).await {
            Ok(body) => body,
            Err(err) => {
                eprintln!(
                    "[Rust Crawler] Network error on topic '{topic}' (page {}): {err:?}",
                    page + 1
                );
                return false;
            }
        };

        match parse_hn_json(&content, topic) {
            Ok((posts, nb_pages)) => {
                sink.extend(posts);
                page + 1 < nb_pages
            }
            Err(err) => {
                eprintln!(
                    "[Rust Crawler] Parse error on topic '{topic}' (page {}): {err:?}",
                    page + 1
                );
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn try_new_rejects_zero_concurrency() {
        assert!(SocialCrawlerRust::try_new(0).is_err());
        assert!(SocialCrawlerRust::try_new(3).is_ok());
    }

    #[test]
    fn retry_helpers_behave_as_expected() {
        assert!(is_retryable_status(StatusCode::TOO_MANY_REQUESTS));
        assert!(is_retryable_status(StatusCode::SERVICE_UNAVAILABLE));
        assert!(!is_retryable_status(StatusCode::NOT_FOUND));
        assert_eq!(compute_backoff_ms(0), 300);
        assert_eq!(compute_backoff_ms(1), 600);
        assert_eq!(compute_backoff_ms(2), 1200);
    }
}
