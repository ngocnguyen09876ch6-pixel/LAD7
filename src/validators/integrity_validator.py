
from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT / "mock_api" / "data"


def load_reference_tables():
    customers = pd.read_json(
        REFERENCE_DIR / "customers.json"
    )

    products = pd.read_json(
        REFERENCE_DIR / "products.json"
    )

    orders = pd.read_json(
        REFERENCE_DIR / "orders.json"
    )

    return {
        "customers": customers,
        "products": products,
        "orders": orders,
    }

def split_cross_table_invalid(name, df):
    df_out = df.copy()

    # Tạo cột error_code nếu chưa có
    if "error_code" not in df_out.columns:
        df_out["error_code"] = ""
    else:
        df_out["error_code"] = (
            df_out["error_code"]
            .fillna("")
            .astype(str)
        )

    # Đọc các bảng tham chiếu
    references = load_reference_tables()

    if name == "orders":
        customer_ids = set(
            references["customers"]["customer_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = (
            df_out["customer_id"]
            .astype("string")
            .str.strip()
        )

        invalid_customer = (
            values.isna()
            | ~values.isin(customer_ids)
        )

        has_error = df_out["error_code"].ne("")
        no_error = invalid_customer & ~has_error
        has_error = invalid_customer & has_error

        df_out.loc[
            no_error, "error_code"
        ] = "FK_CUSTOMER_NOT_FOUND"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|FK_CUSTOMER_NOT_FOUND"
        )

    if name == "order_items":

        order_ids = set(
            references["orders"]["order_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        order_values = (
            df_out["order_id"]
            .astype("string")
            .str.strip()
        )

        invalid_order = (
            order_values.isna()
            | ~order_values.isin(order_ids)
        )

        has_error = df_out["error_code"].ne("")
        no_error = invalid_order & ~has_error
        has_error = invalid_order & has_error

        df_out.loc[
            no_error, "error_code"
        ] = "FK_ORDER_NOT_FOUND"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|FK_ORDER_NOT_FOUND"
        )

        product_ids = set(
            references["products"]["product_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        product_values = (
            df_out["product_id"]
            .astype("string")
            .str.strip()
        )

        invalid_product = (
            product_values.isna()
            | ~product_values.isin(product_ids)
        )

        has_error = df_out["error_code"].ne("")
        no_error = invalid_product & ~has_error
        has_error = invalid_product & has_error

        df_out.loc[
            no_error, "error_code"
        ] = "FK_PRODUCT_NOT_FOUND"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|FK_PRODUCT_NOT_FOUND"
        )
    if name == "payments":
        order_ids = set(
            references["orders"]["order_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = (
            df_out["order_id"]
            .astype("string")
            .str.strip()
        )

        invalid_order = (
            values.isna()
            | ~values.isin(order_ids)
        )

        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_order & ~has_existing_error
        has_error = invalid_order & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "FK_ORDER_NOT_FOUND"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|FK_ORDER_NOT_FOUND"
        )
            # Kiểm tra payment_date >= order_date
    if name == "payments":
        # Chuẩn hóa order_id trong bảng tham chiếu
        order_reference = references["orders"].copy()

        order_reference["order_id"] = (
            order_reference["order_id"]
            .astype("string")
            .str.strip()
        )

        # Tạo ánh xạ order_id -> order_date
        order_date_map = (
            order_reference
            .dropna(subset=["order_id"])
            .drop_duplicates(subset=["order_id"])
            .set_index("order_id")["order_date"]
        )

        # Lấy ngày đặt hàng tương ứng với từng khoản thanh toán
        order_values = (
            df_out["order_id"]
            .astype("string")
            .str.strip()
        )

        order_dates = pd.to_datetime(
            order_values.map(order_date_map),
            errors="coerce",
            utc=True,
        )

        payment_dates = pd.to_datetime(
            df_out["payment_date"],
            errors="coerce",
            utc=True,
        )

        # Thanh toán sớm hơn ngày đặt hàng
        invalid_chronology = (
            payment_dates.notna()
            & order_dates.notna()
            & (payment_dates < order_dates)
        )

        # Giữ mã lỗi cũ, nối mã mới nếu cần
        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_chronology & ~has_existing_error
        has_error = invalid_chronology & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "PAYMENT_BEFORE_ORDER"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|PAYMENT_BEFORE_ORDER"
        )
            # Kiểm tra products.category_id -> categories.category_id
    if name == "products":
        # Tạm suy ra category IDs từ products.json
        category_ids = set(
            references["products"]["category_id"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = (
            df_out["category_id"]
            .astype("string")
            .str.strip()
        )

        invalid_category = (
            values.isna()
            | ~values.isin(category_ids)
        )

        has_existing_error = df_out["error_code"].ne("")
        no_error = invalid_category & ~has_existing_error
        has_error = invalid_category & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "FK_CATEGORY_NOT_FOUND"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|FK_CATEGORY_NOT_FOUND"
        )


    valid_df = df_out[
        df_out["error_code"] == ""
    ].copy()

    rejected_df = df_out[
        df_out["error_code"] != ""
    ].copy()

    return valid_df, rejected_df