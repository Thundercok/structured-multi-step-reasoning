"""
Module Gửi thông báo Telegram Bot khi phát hiện tin đăng Đồng hồ Rep / Pass giá tốt mới.
"""

import httpx
import logging
from typing import Optional
from models import WatchListing

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bool(bot_token and chat_id and bot_token != "YOUR_TELEGRAM_BOT_TOKEN")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_alert(self, listing: WatchListing) -> bool:
        """Gửi thông báo tin đăng đồng hồ mới qua Telegram."""
        if not self.enabled:
            logger.info(f"[Telegram Notifier Disabled] Đã tìm thấy tin mới: {listing.title} ({listing.formatted_price})")
            return False

        # Format nội dung thông báo Markdown
        slangs_str = ", ".join([f"`{s}`" for s in listing.matched_slangs]) if listing.matched_slangs else "Không"
        price_badge = "🔥 BẤT THƯỜNG VỀ GIÁ" if listing.is_price_anomaly else "💰 GIÁ TỐT"
        
        caption = (
            f"⌚ *CẢNH BÁO TÌM THẤY ĐỒNG HỒ REP / PASS*\n\n"
            f"📌 *Tiêu đề:* {listing.title}\n"
            f"🏷️ *Thương hiệu:* #{listing.brand.replace(' ', '')}\n"
            f"💵 *Mức giá:* `{listing.formatted_price}` ({price_badge})\n"
            f"🎯 *Điểm nghi vấn Rep:* `{listing.confidence_score}%` \n"
            f"🏷️ *Mật mã bắt được:* {slangs_str}\n"
            f"📍 *Khu vực:* {listing.location}\n"
            f"👤 *Người bán:* {listing.seller_name} " + (f"(`{listing.seller_phone}`)" if listing.seller_phone else "") + "\n"
            f"🌐 *Nguồn:* `{listing.source}`\n\n"
            f"🔗 [Xem chi tiết bài đăng ngay]({listing.url})"
        )

        try:
            with httpx.Client(timeout=10.0) as client:
                # Nếu có link ảnh -> gửi sendPhoto kèm caption
                if listing.image_url:
                    payload = {
                        "chat_id": self.chat_id,
                        "photo": listing.image_url,
                        "caption": caption,
                        "parse_mode": "Markdown",
                        "reply_markup": {
                            "inline_keyboard": [[
                                {"text": "🔗 Mở bài đăng trên " + listing.source, "url": listing.url}
                            ]]
                        }
                    }
                    resp = client.post(f"{self.api_url}/sendPhoto", json=payload)
                    if resp.status_code == 200:
                        return True

                # Fallback: Gửi tin nhắn text sendMessage
                payload = {
                    "chat_id": self.chat_id,
                    "text": caption,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "🔗 Mở bài đăng trên " + listing.source, "url": listing.url}
                        ]]
                    }
                }
                resp = client.post(f"{self.api_url}/sendMessage", json=payload)
                return resp.status_code == 200

        except Exception as e:
            logger.error(f"[Telegram] Lỗi gửi thông báo qua Telegram: {e}")
            return False
