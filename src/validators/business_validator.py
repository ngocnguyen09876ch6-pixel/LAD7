import pandas as pd
import numpy as np

EMAIL_PATTERN = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
ALLOWED_ENUMS = {
    "customers": {
        "status": {"active", "inactive"},
    },
    "products": {
        "status": {"active", "inactive", "discontinued"},
    },
    "orders": {
        "status": {
            "cancelled",
            "completed",
            "confirmed",
            "pending",
            "shipped",
        },
        "channel": {"mobile_app", "social", "web"},
    },
    "payments": {
        "payment_method": {
            "bank_transfer",
            "card",
            "cash",
            "e_wallet",
        },
        "payment_status": {"failed", "pending", "success"},
    },
}
def split_valid_invalid(name, df):
    df_out = df.copy()
    df_out["error_code"] = ""

    #  Kiểm tra email
    if name == "customers" and "email" in df_out.columns:
        email = (
            df_out["email"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        invalid_email = ~email.str.match(
            EMAIL_PATTERN,
            na=False,
        )

        df_out.loc[
            invalid_email, "error_code"
        ] = "INVALID_EMAIL"

    #  Kiểm tra Enum
    enum_rules = ALLOWED_ENUMS.get(name, {})

    for col, allowed_values in enum_rules.items():
        if col not in df_out.columns:
            continue

        values = (
            df_out[col]
            .astype("string")
            .str.strip()
            .str.lower()
        )

        invalid = ~values.isin(allowed_values)
        error_code = f"INVALID_{col.upper()}"

        # Xác định trạng thái lỗi trước khi cập nhật
        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid & ~has_existing_error
        has_error = invalid & has_existing_error

        # Chưa có lỗi: gán mã lỗi mới
        df_out.loc[
            no_error, "error_code"
        ] = error_code

        # Đã có lỗi: nối thêm mã lỗi
        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|"
            + error_code
        )
            # Kiểm tra unit_price >= 0
    if "unit_price" in df_out.columns:
        price = pd.to_numeric(
            df_out["unit_price"],
            errors="coerce",
        )

        invalid_price = price.notna() & (price < 0)

        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_price & ~has_existing_error
        has_error = invalid_price & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "NEGATIVE_PRICE"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|NEGATIVE_PRICE"
        )
            #  Kiểm tra quantity > 0
    if "quantity" in df_out.columns:
        quantity = pd.to_numeric(
            df_out["quantity"],
            errors="coerce",
        )

        invalid_quantity = (
            quantity.isna() | (quantity <= 0)
        )

        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_quantity & ~has_existing_error
        has_error = invalid_quantity & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "INVALID_QUANTITY"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|INVALID_QUANTITY"
        )
            # Kiểm tra order_total >= 0
    if "order_total" in df_out.columns:
        total = pd.to_numeric(
            df_out["order_total"],
            errors="coerce",
        )

        invalid_total = total.notna() & (total < 0)

        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_total & ~has_existing_error
        has_error = invalid_total & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "NEGATIVE_ORDER_TOTAL"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|NEGATIVE_ORDER_TOTAL"
        )
            # Kiểm tra discount_amount >= 0
    if "discount_amount" in df_out.columns:
        discount = pd.to_numeric(
            df_out["discount_amount"],
            errors="coerce",
        )

        invalid_discount = discount.notna() & (discount < 0)

        has_existing_error = df_out["error_code"].ne("")

        no_error = invalid_discount & ~has_existing_error
        has_error = invalid_discount & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "NEGATIVE_DISCOUNT"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|NEGATIVE_DISCOUNT"
        )
            # Kiểm tra discount_amount <= quantity * unit_price
    required_cols = {"quantity", "unit_price", "discount_amount"}

    if required_cols.issubset(df_out.columns):
        quantity = pd.to_numeric(
            df_out["quantity"],
            errors="coerce",
        )
        price = pd.to_numeric(
            df_out["unit_price"],
            errors="coerce",
        )
        discount = pd.to_numeric(
            df_out["discount_amount"],
            errors="coerce",
        )

        gross = quantity * price

        invalid_discount_gross = (
            quantity.notna()
            & price.notna()
            & discount.notna()
            & (discount > gross)
        )

        has_existing_error = df_out["error_code"].ne("")
        no_error = invalid_discount_gross & ~has_existing_error
        has_error = invalid_discount_gross & has_existing_error

        df_out.loc[
            no_error, "error_code"
        ] = "DISCOUNT_EXCEEDS_GROSS"

        df_out.loc[
            has_error, "error_code"
        ] = (
            df_out.loc[has_error, "error_code"]
            + "|DISCOUNT_EXCEEDS_GROSS"
        )

    #  Tách valid và rejected
    valid_df = df_out[
        df_out["error_code"] == ""
    ].copy()

    rejected_df = df_out[
        df_out["error_code"] != ""
    ].copy()

    return valid_df, rejected_df