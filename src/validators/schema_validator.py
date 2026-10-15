import numpy as np
import pandas as pd


REQUIRED = {
    "customers": [
        "customer_id", "full_name", "email", "phone", "city",
        "customer_segment", "status", "source_system",
        "created_at", "updated_at",
    ],
    "products": [
        "product_id", "category_id", "product_name",
        "unit_price", "cost_price", "status", "source_system",
        "created_at", "updated_at",
    ],
    "orders": [
        "order_id", "customer_id", "order_date", "status",
        "shipping_city", "channel", "order_total",
        "source_system", "created_at", "updated_at",
    ],
    "order_items": [
        "order_item_id", "order_id", "product_id", "quantity",
        "unit_price", "discount_amount", "source_system",
        "created_at", "updated_at",
    ],
    "payments": [
        "payment_id", "order_id", "payment_date",
        "payment_method", "payment_status", "amount",
        "source_system", "created_at", "updated_at",
    ],
}

REQUIRED_VALUES = {
    "customers": ["customer_id", "full_name", "email"],
    "products": ["product_id", "category_id", "product_name", "unit_price"],
    "orders": ["order_id", "customer_id", "order_date", "status"],
    "order_items": [
        "order_item_id", "order_id", "product_id",
        "quantity", "unit_price", "discount_amount",
    ],
    "payments": [
        "payment_id", "order_id", "payment_date",
        "payment_method", "payment_status", "amount",
    ],
}


def validate_schema_and_completeness(
    df,
    required_cols,
    required_values,
):
    df_out = df.copy()

  
    missing_cols = set(required_cols) - set(df_out.columns)

    if missing_cols:
        raise ValueError(
            f"Missing cols: {sorted(missing_cols)}"
        )

   
    values = df_out[required_values]

    missing_value = (
        values.isna()
        | values.astype("string")
            .apply(lambda col: col.str.strip().eq(""))
    )

    # 3. Tính score theo từng dòng
    total_required_values = len(required_values)

    if total_required_values == 0:
        raise ValueError("required_values must not be empty")

    missing_count = missing_value.sum(axis=1)

    df_out["score"] = (
        (total_required_values - missing_count)
        / total_required_values
        * 100
    ).round(2)

    df_out["errors"] = np.where(
        missing_value.any(axis=1),
        "MISSING_REQUIRED",
        "",
    )

    return df_out