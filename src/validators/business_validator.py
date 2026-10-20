import re
import pandas as pd

EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

VALID = {
    'customers': {'status': {'active', 'inactive'}},
    'products': {'status': {'active', 'inactive', 'discontinued'}},
    'orders': {
        'status': {'pending', 'confirmed', 'shipped', 'completed', 'cancelled'},
        'channel': {'web', 'mobile_app', 'social'},
    },
    'payments': {
        'payment_status': {'pending', 'success', 'failed', 'refunded'},
        'payment_method': {'cash', 'bank_transfer', 'card', 'e_wallet'},
    },
}

REQUIRED_VALUES = {
    'customers': ['customer_id', 'full_name', 'email'],
    'products': ['product_id', 'category_id', 'product_name'],
    'orders': ['order_id', 'customer_id', 'order_date'],
    'order_items': ['order_item_id', 'order_id', 'product_id'],
    'payments': ['payment_id', 'order_id', 'payment_date'],
}

def _missing(val):
    return pd.isna(val) or (isinstance(val, str) and val.strip() == '')

def split_valid_invalid(name: str, df: pd.DataFrame):
    """Áp dụng row-level rules, trả về (valid_df, rejected_df kèm cột error_code)."""
    errors = []
    for _, row in df.iterrows():
        row_errors = []

        # 1. Missing required fields
        for col in REQUIRED_VALUES.get(name, []):
            if col not in df.columns or _missing(row.get(col)):
                row_errors.append('MISSING_REQUIRED')
                break

        # 2. Enum status/channel/method
        for col, allowed in VALID.get(name, {}).items():
            if col in df.columns and row.get(col) not in allowed:
                row_errors.append(f'INVALID_{col.upper()}')

        # 3. Custom dataset rules
        if name == 'customers':
            email = row.get('email')
            if not isinstance(email, str) or not EMAIL.match(email):
                row_errors.append('INVALID_EMAIL')

        elif name == 'products':
            u_price = pd.to_numeric(row.get('unit_price'), errors='coerce')
            c_price = pd.to_numeric(row.get('cost_price'), errors='coerce')
            if pd.isna(u_price): row_errors.append('INVALID_UNIT_PRICE')
            elif u_price < 0: row_errors.append('NEGATIVE_PRICE')
            if pd.isna(c_price): row_errors.append('INVALID_COST_PRICE')
            elif c_price < 0: row_errors.append('NEGATIVE_COST_PRICE')

        elif name == 'orders':
            total = pd.to_numeric(row.get('order_total'), errors='coerce')
            if pd.isna(row.get('order_date')): row_errors.append('INVALID_ORDER_DATE')
            if pd.isna(total): row_errors.append('INVALID_ORDER_TOTAL')
            elif total < 0: row_errors.append('NEGATIVE_ORDER_TOTAL')

        elif name == 'order_items':
            qty = pd.to_numeric(row.get('quantity'), errors='coerce')
            u_price = pd.to_numeric(row.get('unit_price'), errors='coerce')
            disc = pd.to_numeric(row.get('discount_amount'), errors='coerce')
            if pd.isna(qty) or qty <= 0: row_errors.append('INVALID_QUANTITY')
            if pd.isna(u_price): row_errors.append('INVALID_UNIT_PRICE')
            elif u_price < 0: row_errors.append('NEGATIVE_PRICE')
            if pd.isna(disc): row_errors.append('INVALID_DISCOUNT')
            elif disc < 0: row_errors.append('NEGATIVE_DISCOUNT')
            if pd.notna(qty) and pd.notna(u_price) and pd.notna(disc) and qty > 0 and u_price >= 0:
                if disc > qty * u_price: row_errors.append('DISCOUNT_EXCEEDS_GROSS')

        elif name == 'payments':
            amt = pd.to_numeric(row.get('amount'), errors='coerce')
            if pd.isna(row.get('payment_date')): row_errors.append('INVALID_PAYMENT_DATE')
            if pd.isna(amt): row_errors.append('INVALID_AMOUNT')
            elif amt < 0: row_errors.append('NEGATIVE_AMOUNT')

        errors.append('|'.join(dict.fromkeys(row_errors)))

    out = df.copy()
    out['error_code'] = errors
    valid = out[out.error_code == ''].drop(columns='error_code')
    rejected = out[out.error_code != '']
    return valid, rejected
