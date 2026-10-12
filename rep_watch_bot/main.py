"""
Main Controller & CLI cho Bot Cào Listing Đồng Hồ Rep Việt Nam.
"""

import sys
import os
import time
import yaml
import argparse
import logging
from tabulate import tabulate
from dotenv import load_dotenv

from storage import StorageManager
from telegram_notifier import TelegramNotifier
from scrapers.chotot_scraper import ChoTotScraper
from scrapers.webrep_scraper import WebRepScraper
from scrapers.facebook_scraper import FacebookScraper

# Tải biến môi trường từ file .env (nếu có)
load_dotenv()

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RepWatchBot")


def load_config(config_path: str = "config.yaml") -> dict:
    """Tải cấu hình từ config.yaml kết hợp biến môi trường."""
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Ghi đè bằng biến môi trường (nếu có)
    filter_cfg = config.get("filter", {})
    if os.getenv("MAX_PRICE"):
        filter_cfg["max_price"] = int(os.getenv("MAX_PRICE"))
    if os.getenv("MIN_PRICE"):
        filter_cfg["min_price"] = int(os.getenv("MIN_PRICE"))
    if os.getenv("MIN_CONFIDENCE"):
        filter_cfg["min_confidence"] = int(os.getenv("MIN_CONFIDENCE"))
    config["filter"] = filter_cfg

    tg_cfg = config.get("telegram", {})
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        tg_cfg["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHAT_ID"):
        tg_cfg["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
    if os.getenv("TELEGRAM_ENABLED"):
        tg_cfg["enabled"] = os.getenv("TELEGRAM_ENABLED").lower() == "true"
    config["telegram"] = tg_cfg

    settings = config.get("settings", {})
    if os.getenv("STORAGE_DB"):
        settings["storage_db"] = os.getenv("STORAGE_DB")
    config["settings"] = settings

    return config


def run_scrape_cycle(config: dict, storage: StorageManager, notifier: TelegramNotifier):
    """Thực hiện một chu kỳ cào tin từ tất cả các nguồn."""
    logger.info("=== BẮT ĐẦU CHU KỲ CÀO DỮ LIỆU ĐỒNG HỒ REP / PASS ===")

    filter_cfg = config.get("filter", {})
    sources_cfg = config.get("sources", {})
    search_keywords = config.get("search_keywords", [])

    max_price = filter_cfg.get("max_price", 15000000)
    min_price = filter_cfg.get("min_price", 200000)
    min_confidence = filter_cfg.get("min_confidence", 40)

    all_listings = []

    # 1. Cào Chợ Tốt
    if sources_cfg.get("chotot", True):
        chotot = ChoTotScraper(keywords=search_keywords, max_price=max_price, min_price=min_price)
        all_listings.extend(chotot.fetch_listings())

    # 2. Cào các trang Web Rep chuyên biệt
    if sources_cfg.get("webrep", True):
        webrep = WebRepScraper(max_price=max_price, min_price=min_price)
        all_listings.extend(webrep.fetch_listings())

    # 3. Cào Facebook Marketplace
    if sources_cfg.get("facebook", False):
        fb = FacebookScraper(max_price=max_price, min_price=min_price)
        all_listings.extend(fb.fetch_listings())

    new_count = 0
    table_data = []

    for listing in all_listings:
        if listing.confidence_score < min_confidence:
            continue

        is_saved = storage.save_listing(listing)
        if is_saved:
            new_count += 1
            notifier.send_alert(listing)

            table_data.append([
                listing.source,
                listing.brand,
                listing.title[:35] + ("..." if len(listing.title) > 35 else ""),
                listing.formatted_price,
                f"{listing.confidence_score}%",
                ", ".join(listing.matched_slangs[:2]),
                listing.location
            ])

    logger.info(f"=== KẾT THÚC CHU KỲ: Tìm thấy tổng {len(all_listings)} tin, trong đó có {new_count} TIN MỚI ===")

    if table_data:
        headers = ["Nguồn", "Hiệu", "Tiêu đề", "Giá", "Độ Rep", "Mật mã", "Khu vực"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="fancy_grid") + "\n")


def main():
    parser = argparse.ArgumentParser(description="Bot Cào Listing Đồng Hồ Replica / Pass Việt Nam")
    parser.add_argument("--once", action="store_true", help="Chạy cào 1 lần rồi kết thúc")
    parser.add_argument("--monitor", action="store_true", help="Chạy chế độ giám sát định kỳ liên tục")
    parser.add_argument("--interval", type=int, default=0, help="Thời gian lặp lại (phút)")
    parser.add_argument("--export", type=str, choices=["csv", "excel", "json"], help="Xuất báo cáo dữ liệu hiện có")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    config = load_config("config.yaml")
    db_path = config.get("settings", {}).get("storage_db", "data/rep_watches.db")
    storage = StorageManager(db_path=db_path)

    if args.export:
        filepath = storage.export_data(format_type=args.export)
        if filepath:
            print(f"✅ Đã xuất báo cáo thành công ra file: {os.path.abspath(filepath)}")
        else:
            print("⚠️ Chưa có dữ liệu tin đăng nào trong CSDL để xuất báo cáo.")
        return

    tg_cfg = config.get("telegram", {})
    notifier = TelegramNotifier(
        bot_token=tg_cfg.get("bot_token", ""),
        chat_id=tg_cfg.get("chat_id", ""),
        enabled=tg_cfg.get("enabled", False)
    )

    if args.monitor:
        interval_min = args.interval or config.get("settings", {}).get("monitor_interval_minutes", 15)
        logger.info(f"🚀 Bắt đầu chế độ GIÁM SÁT LIÊN TỤC (Tự động cào mỗi {interval_min} phút)... Nhấn Ctrl+C để dừng.")
        try:
            while True:
                run_scrape_cycle(config, storage, notifier)
                logger.info(f"Chờ {interval_min} phút cho chu kỳ tiếp theo...")
                time.sleep(interval_min * 60)
        except KeyboardInterrupt:
            logger.info("Đã dừng bot giám sát.")
    else:
        run_scrape_cycle(config, storage, notifier)
        csv_file = storage.export_data(format_type="csv")
        if csv_file:
            print(f"\n📂 File kết quả báo cáo CSV đã được lưu tại: {os.path.abspath(csv_file)}")


if __name__ == "__main__":
    main()
