use crate::models::SocialPost;
use crate::parser::parse_hn_json;
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, USER_AGENT};
use std::sync::Arc;
use tokio::sync::Semaphore;
use tokio::time::{sleep, Duration};

/// Asynchronous, high-concurrency crawler client for social data ingestion.
pub struct SocialCrawlerRust {
    client: reqwest::Client,
    semaphore: Arc<Semaphore>,
}

impl SocialCrawlerRust {
    /// Instantiates a new crawler client with bounded concurrency and connection pooling.
    pub fn new(max_concurrency: usize) -> Self {
        let mut headers = HeaderMap::new();
        headers.insert(
            USER_AGENT,
            HeaderValue::from_static("SocialBenchmarkCrawler/1.0 (Educational Ingestion Lab)"),
        );
        headers.insert(ACCEPT, HeaderValue::from_static("application/json"));

        let client = reqwest::Client::builder()
            .default_headers(headers)
            .timeout(Duration::from_secs(15))
            .pool_idle_timeout(Duration::from_secs(30))
            .pool_max_idle_per_host(10)
            .tcp_keepalive(Duration::from_secs(60))
            .build()
            .expect("Failed to initialize reqwest HTTP client");

        Self {
            client,
            semaphore: Arc::new(Semaphore::new(max_concurrency)),
        }
    }

    /// Performs an asynchronous HTTP GET request governed by the concurrency semaphore.
    pub async fn fetch_page(&self, url: &str) -> anyhow::Result<String> {
        let _permit = self.semaphore.acquire().await?;
        let response = self.client.get(url).send().await?;
        let text = response.error_for_status()?.text().await?;
        Ok(text)
    }

    /// Crawls a specific topic keyword across multiple paginated API requests.
    pub async fn crawl_topic(
        &self,
        topic: &str,
        max_pages: usize,
        hits_per_page: usize,
    ) -> Vec<SocialPost> {
        let mut all_posts = Vec::new();

        for page in 0..max_pages {
            let url = format!(
                "https://hn.algolia.com/api/v1/search?query={}&hitsPerPage={}&page={}",
                topic, hits_per_page, page
            );

            match self.fetch_page(&url).await {
                Ok(content) => {
                    match parse_hn_json(&content, topic) {
                        Ok((posts, nb_pages)) => {
                            all_posts.extend(posts);
                            if page + 1 >= nb_pages {
                                break;
                            }
                        }
                        Err(err) => {
                            eprintln!(
                                "[Rust Crawler] Parse error on topic '{}' (page {}): {:?}",
                                topic,
                                page + 1,
                                err
                            );
                            break;
                        }
                    }

                    // Polite delay between subsequent page requests
                    sleep(Duration::from_millis(100)).await;
                }
                Err(err) => {
                    eprintln!(
                        "[Rust Crawler] Network error on topic '{}' (page {}): {:?}",
                        topic,
                        page + 1,
                        err
                    );
                    break;
                }
            }
        }

        all_posts
    }
}
