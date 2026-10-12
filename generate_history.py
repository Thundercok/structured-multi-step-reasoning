"""
Script tự động tạo commit lùi thời gian (Backdated Commits) tự nhiên cho GitHub Contribution Graph.
"""

import os
import random
import subprocess
from datetime import datetime, timedelta

# ================= CẤU HÌNH (CONFIGURATION) =================
START_DATE = datetime(2025, 1, 1)      # Ngày bắt đầu
END_DATE = datetime(2025, 5, 31)       # Ngày kết thúc
LOG_FILE = "activity.txt"              # File ghi nhận log thay đổi

# Tỷ lệ có commit trong 1 ngày (0.8 = 80% số ngày sẽ có commit)
ACTIVE_DAY_PROBABILITY = 0.75

# Số commit tối thiểu và tối đa mỗi ngày có hoạt động
MIN_COMMITS_PER_DAY = 1
MAX_COMMITS_PER_DAY = 4

# Danh sách thông điệp commit tự nhiên
COMMIT_MESSAGES = [
    "refactor: clean up helper functions",
    "docs: update installation notes",
    "style: format code according to PEP8",
    "test: add edge case test scenarios",
    "fix: resolve null pointer check in parser",
    "chore: update internal dependencies",
    "perf: optimize database query execution",
    "feat: add logger fallback handling",
    "refactor: modularize request handler",
    "docs: improve API documentation"
]
# ============================================================


def run_command(cmd, env=None):
    """Thực thi lệnh shell."""
    result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Lỗi: {result.stderr}")
    return result.returncode == 0


def generate_backdated_commits():
    current_date = START_DATE
    total_commits = 0

    print(f"🚀 Bắt đầu tạo commit từ {START_DATE.strftime('%Y-%m-%d')} đến {END_DATE.strftime('%Y-%m-%d')}...")

    while current_date <= END_DATE:
        # Bỏ qua ngẫu nhiên một số ngày (đặc biệt là cuối tuần) để biểu đồ trông tự nhiên
        is_weekend = current_date.weekday() >= 5
        probability = ACTIVE_DAY_PROBABILITY * 0.4 if is_weekend else ACTIVE_DAY_PROBABILITY

        if random.random() < probability:
            commits_today = random.randint(MIN_COMMITS_PER_DAY, MAX_COMMITS_PER_DAY)

            for i in range(commits_today):
                # Tạo giờ commit ngẫu nhiên từ 09:00 đến 22:00
                hour = random.randint(9, 22)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                commit_dt = current_date.replace(hour=hour, minute=minute, second=second)
                date_str = commit_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Cập nhật file activity.txt
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"Commit at {date_str}\n")

                # Stage file
                run_command(f"git add {LOG_FILE}")

                # Tạo commit với ngày lùi
                env = os.environ.copy()
                env["GIT_AUTHOR_DATE"] = date_str
                env["GIT_COMMITTER_DATE"] = date_str

                msg = random.choice(COMMIT_MESSAGES)
                success = run_command(f'git commit -m "{msg}"', env=env)

                if success:
                    total_commits += 1

        current_date += timedelta(days=1)

    print(f"✅ Đã tạo thành công {total_commits} commit lùi thời gian!")
    print("👉 Hãy chạy lệnh 'git push origin main' để cập nhật biểu đồ xanh trên GitHub.")


if __name__ == "__main__":
    generate_backdated_commits()
