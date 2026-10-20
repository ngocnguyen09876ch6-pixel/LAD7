import argparse
import json
import uuid
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from src.validators.business_validator import split_valid_invalid
from src.config import ROOT, SETTINGS
from src.extract_files import read_dataset
from src.logger import get_logger
from src.transform import normalize
from src.load_postgres import upsert_dataframe
from src.api_client import fetch_all_pages
from src.refresh_mart import run_refresh
log = get_logger(__name__)

STATE_PATH = SETTINGS.metadata_dir / "pipeline_state.json"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Daily data pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/incremental/day_2026-07-01"),
        help="Thu muc du lieu dau vao",
    )

    parser.add_argument(
        "--source",
        choices=["file", "api", "both"],
        default="file",
        help="Chon nguon du lieu",
    )

    parser.add_argument(
        "--refresh-mart",
        action="store_true",
        help="Kich hoat lam moi Mart",
    )

    parser.add_argument(
        "--skip-processed-file",
        action="store_true",
        help="Bo qua batch file da xu ly thanh cong",
    )

    return parser


def _empty_state():
    return {
        "last_run_id": None,
        "last_successful_at": None,
        "last_source": None,
        "status": None,
        "api_watermarks": {},
        "processed_file_batches": [],
    }


def _read_state():
    if not STATE_PATH.exists():
        return _empty_state()

    content = STATE_PATH.read_text(encoding="utf-8").strip()

    if not content:
        return _empty_state()

    try:
        state = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"State file contains invalid JSON: {STATE_PATH}"
        ) from exc

    if not isinstance(state, dict):
        raise ValueError(
            f"State file must contain a JSON object: {STATE_PATH}"
        )

    # Phòng thủ: Bù đắp các khóa bị thiếu nếu file json bị sửa thiếu trường
    for key, default_val in _empty_state().items():
        state.setdefault(key, default_val)

    return state


FILE_CANDIDATES = {
    "customers": ("customers_daily.csv", "customers.csv"),
    "products": ("products_daily.csv", "products.csv"),
    "orders": ("orders_daily.csv", "orders.csv"),
    "order_items": ("order_items_daily.csv", "order_items.csv"),
    "payments": ("payments_daily.json", "payments.json"),
}


def _file_frames(input_dir, target_datasets=None):
    if not input_dir.is_absolute():
        input_dir = ROOT / input_dir

    frames = {}

    for name, filenames in FILE_CANDIDATES.items():
        # 1. Lọc bảng (Nếu không nằm trong danh sách mục tiêu thì bỏ qua)
        if target_datasets is not None and name not in target_datasets:
            continue
            
        # 2. KHỞI TẠO BIẾN file_path 
        file_path = next(
            (
                input_dir / filename
                for filename in filenames
                if (input_dir / filename).is_file()
            ),
            None,
        )

        # 3. Kiểm tra file 
        if file_path is None:
            raise FileNotFoundError(
                f"Khong tim thay file cho dataset {name} trong {input_dir}"
            )
            
        # 4. Đọc file
        frames[name] = read_dataset(file_path)

        # Dùng log.info thay cho print để ghi đồng thời ra màn hình và file log.log
        log.info(
            "[2/8] source=file dataset=%s rows=%s",
            name,
            len(frames[name]),
        )

    return frames
def _api_frames(run_id, state, target_datasets=None):
    frames = {}
    
    # 1. Tạo thư mục lưu dữ liệu thô (RAW) cho riêng phiên chạy này
    raw_dir = ROOT / "data" / "raw" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    endpoints = target_datasets if target_datasets else ["customers", "products", "orders", "order_items", "payments"]
    for endpoint in endpoints:
        raw_payloads = []
        
        # Lấy watermark từ file trạng thái cũ
        watermark = state["api_watermarks"].get(endpoint)
        
        try:
            # Kéo dữ liệu từ API
            rows = fetch_all_pages(
                resource=endpoint,
                updated_after=watermark,
                raw_payloads=raw_payloads
            )
        except Exception as e:
            # Ghi log [CRITICAL] theo đúng định dạng yêu cầu
            log.error(f"[CRITICAL] run_id={run_id} | step=Extract_API | dataset={endpoint} | error_type={type(e).__name__} | msg={str(e)}")
            raise # Ném lỗi ra ngoài để dừng ngay lập tức, bảo toàn pipeline_state.json
            
        # Ghi JSON gốc ra file
        raw_file = raw_dir / f"{endpoint}.json"
        with raw_file.open("w", encoding="utf-8") as f:
            json.dump(raw_payloads, f, ensure_ascii=False, indent=2)
            
        # Chuyển đổi dữ liệu thành bảng
        frames[endpoint] = pd.DataFrame(rows)
        
        log.info(
            "[2/8] source=api dataset=%s rows=%s", 
            endpoint, 
            len(rows)
        )
    return frames

def run(args):
    # [1/8] Khởi tạo phiên chạy
    run_id = str(uuid.uuid4())
    state = _read_state()

    log.info("[1/8] Khởi tạo run_id=%s", run_id)
    log.info("State file: %s", STATE_PATH)
    log.info("Previous run: %s", state.get("last_run_id"))

    if args.source in ["file", "both"] and args.skip_processed_file:
        current_batch = str(args.input_dir.resolve())
        if current_batch in state.get("processed_file_batches", []):
            log.info("Batch %s đã được xử lý trước đó. Bỏ qua do có cờ --skip-processed-file.", current_batch)
            return

   # [2/8] Trích xuất dữ liệu theo nguồn
    if args.source == "file":
        frames = _file_frames(args.input_dir)
    elif args.source == "api":
        frames = _api_frames(run_id, state)
    elif args.source == "both":
        # Khởi tạo từ điển tổng
        frames = {}
        
        # 1. Gọi hàm lấy file, chỉ nhắm mục tiêu vào 2 bảng Master
        file_data = _file_frames(args.input_dir, target_datasets=["customers", "products"])
        frames.update(file_data)
        
        # 2. Gọi hàm lấy api, chỉ nhắm mục tiêu vào 3 bảng Transaction
        api_data = _api_frames(run_id, state, target_datasets=["orders", "order_items", "payments"])
        frames.update(api_data)
    else:
        raise ValueError(f"Nguồn dữ liệu không hợp lệ: {args.source}")

    for name, df in frames.items():
        # [3/8] Chuẩn hóa
        clean_df = normalize(df)
        log.info("[3/8] Chuẩn hóa & Schema dataset=%s hoàn tất", name)

        # [4/8] Kiểm định chất lượng
        valid_df, invalid_df = split_valid_invalid(name, clean_df)
        log.info("[4/8] Kiểm tra chất lượng dataset=%s: valid=%s, invalid=%s", name, len(valid_df), len(invalid_df))

        # [5/8] Ghi Reject và Nạp DB
        if len(invalid_df) > 0:
            reject_dir = ROOT / "data" / "rejected" / run_id
            reject_dir.mkdir(parents=True, exist_ok=True)
            reject_path = reject_dir / f"{name}_reject.csv"
            invalid_df.to_csv(reject_path, index=False, encoding="utf-8-sig")

        db_stats = upsert_dataframe(name, valid_df)
        log.info("[5/8] Nạp Database dataset=%s | input=%s valid=%s reject=%s inserted=%s updated=%s", name, len(df), len(valid_df), len(invalid_df), db_stats.get("inserted", 0), db_stats.get("updated", 0))

        # [6/8] Đối soát
        assert len(df) == (len(valid_df) + len(invalid_df)), f"Dữ liệu đầu vào và đầu ra không khớp tại bảng {name}"
        log.info("[6/8] Đối soát dữ liệu dataset=%s OK", name)

   
    # [7/8] Làm mới Data Mart
    if args.refresh_mart:
        run_refresh()  # BỔ SUNG DÒNG NÀY VÀO ĐÂY
        log.info("[7/8] Làm mới Data Mart OK")
    else:
        log.info("[7/8] Làm mới Data Mart SKIPPED")
    # [8/8] Cập nhật Checkpoint
    state["last_run_id"] = run_id
    state["last_successful_at"] = datetime.now().isoformat()
    state["last_source"] = args.source
    state["status"] = "success"
    
    if args.source in ["file", "both"]:
        state["processed_file_batches"].append(str(args.input_dir.resolve()))

    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    log.info("[8/8] Cập nhật Checkpoint State OK")
    
def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        run(args)
        sys.exit(0)  # Thoát thành công với mã 0
    except Exception as exc:
        log.exception("Pipeline thất bại với lỗi nghiêm trọng: %s", exc)
        sys.exit(1)  # Thoát thất bại với mã 1


if __name__ == "__main__":
    main()