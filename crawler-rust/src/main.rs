mod crawler;
mod models;
mod parser;

use crawler::SocialCrawlerRust;
use std::env;
use std::fs::{create_dir_all, File};
use std::io::{BufWriter, Write};
use std::path::Path;
use std::time::Instant;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args: Vec<String> = env::args().collect();

    let mut topics_str = "rust,python,technology,ai,datascience".to_string();
    let mut pages: usize = 3;
    let mut output_path = "../data/social_rust.jsonl".to_string();
    let concurrency: usize = 3;

    // CLI argument parser
    let mut idx = 1;
    while idx < args.len() {
        match args[idx].as_str() {
            "--topics" if idx + 1 < args.len() => {
                topics_str = args[idx + 1].clone();
                idx += 2;
            }
            "--pages" if idx + 1 < args.len() => {
                pages = args[idx + 1].parse().unwrap_or(3);
                idx += 2;
            }
            "--output" if idx + 1 < args.len() => {
                output_path = args[idx + 1].clone();
                idx += 2;
            }
            _ => {
                idx += 1;
            }
        }
    }

    let topics: Vec<&str> = topics_str
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();

    println!(
        "[Rust] Starting ingestion pipeline: topics={:?}, pages={} (50 posts/page)",
        topics, pages
    );
    let start_time = Instant::now();

    let crawler = SocialCrawlerRust::new(concurrency);
    let mut all_posts = Vec::new();

    for topic in topics {
        let batch = crawler.crawl_topic(topic, pages, 50).await;
        println!(
            "[Rust] Finished topic '{}': ingested {} posts",
            topic,
            batch.len()
        );
        all_posts.extend(batch);
    }

    let elapsed = start_time.elapsed().as_secs_f64();

    // Ensure target directory exists
    if let Some(parent) = Path::new(&output_path).parent() {
        create_dir_all(parent)?;
    }

    // Buffered I/O stream serialization for maximum disk write efficiency
    let file = File::create(&output_path)?;
    let mut writer = BufWriter::new(file);

    for post in &all_posts {
        let json_line = serde_json::to_string(post)?;
        writeln!(writer, "{}", json_line)?;
    }
    writer.flush()?;

    let throughput = if elapsed > 0.0 {
        all_posts.len() as f64 / elapsed
    } else {
        0.0
    };

    println!("\n--------------------------------------------------");
    println!("[Rust] Ingestion Summary");
    println!("--------------------------------------------------");
    println!("Total Posts Ingested : {}", all_posts.len());
    println!("Elapsed Time         : {:.2} seconds", elapsed);
    println!("Throughput           : {:.2} posts/second", throughput);
    println!("Destination          : {}", output_path);

    Ok(())
}
