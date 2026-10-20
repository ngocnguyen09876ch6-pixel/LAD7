#!/bin/bash
# Lệnh 'set -euo pipefail' giúp script dừng ngay lập tức nếu có bất kỳ lỗi nào 
# (như gọi sai tên biến, hoặc một lệnh trong pipeline bị hỏng).
set -euo pipefail

# Tự động xác định đường dẫn thư mục gốc dự án (dù bạn gọi script từ thư mục nào)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Tạo thư mục logs nếu chưa có
mkdir -p logs

# Khai báo file log riêng theo ngày hiện tại (ví dụ: pipeline_20261019.log)
LOG_FILE="logs/pipeline_$(date +%Y%m%d).log"

echo "========================================" >> "$LOG_FILE"
echo "BẮT ĐẦU CHẠY PIPELINE: $(date)" >> "$LOG_FILE"

# Kích hoạt môi trường ảo Python (Hỗ trợ cả môi trường Windows Git Bash và Linux)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[CRITICAL] Không tìm thấy môi trường ảo .venv" | tee -a "$LOG_FILE"
    exit 1
fi

# Chạy pipeline, đẩy output vào log (lệnh tee giúp in ra cả màn hình lẫn ghi vào file)
# Tạm tắt cờ ngắt tự động (set +e) để lấy chính xác mã lỗi (exit code) của Python
set +e
python -m src.pipeline --source both --input-dir data/incremental/day_2026-07-01 --refresh-mart 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

echo "KẾT THÚC PIPELINE VỚI MÃ LỖI: $EXIT_CODE LÚC $(date)" >> "$LOG_FILE"

# Trả về đúng exit code của Python cho hệ điều hành
exit $EXIT_CODE