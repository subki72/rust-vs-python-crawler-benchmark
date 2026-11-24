mod crawler;
mod models;
mod parser;

use anyhow::{bail, Context};
use crawler::SocialCrawlerRust;
use models::SocialPost;
use std::env;
use std::fs::{create_dir_all, File};
use std::io::{BufWriter, Write};
use std::path::Path;
use std::time::Instant;

/// Parsed CLI configuration for the Rust ingestion runner.
#[derive(Debug, PartialEq, Eq)]
struct CliConfig {
    topics: String,
    pages: usize,
    output_path: String,
    concurrency: usize,
}

impl Default for CliConfig {
    fn default() -> Self {
        Self {
            topics: "rust,python,technology,ai,datascience".to_string(),
            pages: 3,
            output_path: "../data/social_rust.jsonl".to_string(),
            concurrency: 3,
        }
    }
}

fn parse_args(args: &[String]) -> anyhow::Result<CliConfig> {
    let mut cfg = CliConfig::default();
    let mut idx = 1;
    while idx < args.len() {
        match args[idx].as_str() {
            "--topics" if idx + 1 < args.len() => {
                cfg.topics = args[idx + 1].clone();
                idx += 2;
            }
            "--pages" if idx + 1 < args.len() => {
                cfg.pages = args[idx + 1]
                    .parse()
                    .context("--pages must be a valid positive integer")?;
                idx += 2;
            }
            "--output" if idx + 1 < args.len() => {
                cfg.output_path = args[idx + 1].clone();
                idx += 2;
            }
            "--concurrency" if idx + 1 < args.len() => {
                cfg.concurrency = args[idx + 1]
                    .parse()
                    .context("--concurrency must be a valid positive integer")?;
                idx += 2;
            }
            _ => idx += 1,
        }
    }
    if cfg.pages == 0 || cfg.concurrency == 0 {
        bail!("--pages and --concurrency must be greater than zero");
    }
    Ok(cfg)
}

fn write_jsonl_output(output_path: &str, posts: &[SocialPost]) -> anyhow::Result<()> {
    if let Some(parent) = Path::new(output_path).parent() {
        if !parent.as_os_str().is_empty() {
            create_dir_all(parent)?;
        }
    }
    let file = File::create(output_path)?;
    let mut writer = BufWriter::new(file);
    for post in posts {
        let json_line = serde_json::to_string(post)?;
        writeln!(writer, "{json_line}")?;
    }
    writer.flush()?;
    Ok(())
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args: Vec<String> = env::args().collect();
    let cfg = parse_args(&args)?;
    let topics: Vec<&str> = cfg
        .topics
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .collect();

    println!(
        "[Rust] Starting ingestion pipeline: topics={topics:?}, pages={} (50 posts/page)",
        cfg.pages
    );
    let start_time = Instant::now();
    let crawler = SocialCrawlerRust::try_new(cfg.concurrency)?;
    let mut all_posts = Vec::new();

    for topic in topics {
        let batch = crawler.crawl_topic(topic, cfg.pages, 50).await;
        println!(
            "[Rust] Finished topic '{topic}': ingested {} posts",
            batch.len()
        );
        all_posts.extend(batch);
    }

    let elapsed = start_time.elapsed().as_secs_f64();
    write_jsonl_output(&cfg.output_path, &all_posts)?;
    let throughput = if elapsed > 0.0 {
        all_posts.len() as f64 / elapsed
    } else {
        0.0
    };
    println!(
        "[Rust] Summary: posts={}, elapsed={elapsed:.2}s, throughput={throughput:.2} posts/sec, dest={}",
        all_posts.len(),
        cfg.output_path
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_args_supports_custom_and_default_flags() {
        let args = vec![
            "crawler-rust".to_string(),
            "--topics".to_string(),
            "rust,ai".to_string(),
            "--pages".to_string(),
            "2".to_string(),
            "--concurrency".to_string(),
            "4".to_string(),
            "--output".to_string(),
            "out.jsonl".to_string(),
        ];
        let parsed = parse_args(&args).expect("valid args");
        assert_eq!(parsed.topics, "rust,ai");
        assert_eq!(parsed.pages, 2);
        assert_eq!(parsed.concurrency, 4);
        assert_eq!(parsed.output_path, "out.jsonl");
    }

    #[test]
    fn parse_args_rejects_zero_pages() {
        let args = vec![
            "crawler-rust".to_string(),
            "--pages".to_string(),
            "0".to_string(),
        ];
        assert!(parse_args(&args).is_err());
    }
}
