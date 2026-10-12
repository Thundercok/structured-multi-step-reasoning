use serde_json::json;
use spider::tokio;
use spider::website::Website;
use std::fs::OpenOptions;
use std::io::Write;
use std::sync::{Arc, Mutex};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Initialize the target engine targeting a clear software engineering job board
    let target_url = "https://news.ycombinator.com/jobs";
    let mut website = Website::new(target_url);

    // 2. Set strict parameters for extraction limits and domain isolation
    website.configuration.respect_robots_txt = true;
    website.configuration.user_agent = Some("CV-Skill-Gap-Bot/1.0".into());
    website.configuration.delay = 300; // 300ms politeness gap
    website.configuration.limit = 20; // Keep initial runs small for debugging

    // 3. Setup a flat file stream mapping output to local storage
    let local_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open("crawled_market_skills.jsonl")?;
    let thread_safe_file = Arc::new(Mutex::new(local_file));

    // 4. Subscribe to the web page asset communication channel
    let mut channel_stream = website.subscribe(32);

    // Spawn an isolated concurrent thread runner to collect text lines as they fall in
    let file_writer_clone = thread_safe_file.clone();
    tokio::spawn(async move {
        while let Ok(page) = channel_stream.recv().await {
            let page_url = page.get_url();

            // Get clean text completely stripped of deep HTML nested code elements
            if let Some(body_text) = page.get_html_text() {
                if body_text.trim().len() > 150 {
                    // Normalize white spaces to keep our flat JSON row clean
                    let compressed_text = body_text.trim().replace('\n', " ");

                    let flat_record = json!({
                        "source_url": page_url,
                        "extracted_text": compressed_text
                    });

                    if let Ok(mut protected_file) = file_writer_clone.lock() {
                        if let Ok(_) = writeln!(protected_file, "{}", flat_record.to_string()) {
                            println!("[GATHERED] Data captured from path -> {}", page_url);
                        }
                    }
                }
            }
        }
    });

    println!("Starting crawler on: {}", target_url);
    website.crawl().await;
    website.unsubscribe();

    println!("Process finished. Inspect 'spider/crawled_market_skills.jsonl'");
    Ok(())
}
