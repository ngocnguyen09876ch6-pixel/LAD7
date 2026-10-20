import pandas as pd
from sqlalchemy import text

PK = {
    'categories': 'category_id',
    'customers': 'customer_id',
    'products': 'product_id',
    'orders': 'order_id',
    'order_items': 'order_item_id',
    'payments': 'payment_id',
}

FK_RULES = {
    'products': [('category_id', 'categories', 'FK_CATEGORY_NOT_FOUND')],
    'orders': [('customer_id', 'customers', 'FK_CUSTOMER_NOT_FOUND')],
    'order_items': [
        ('order_id', 'orders', 'FK_ORDER_NOT_FOUND'),
        ('product_id', 'products', 'FK_PRODUCT_NOT_FOUND'),
    ],
    'payments': [('order_id', 'orders', 'FK_ORDER_NOT_FOUND')],
}

def split_cross_table_invalid(name: str, df: pd.DataFrame, reference_ids=None, order_dates=None):
    """Kiểm tra toàn vẹn khóa ngoại (FK) và logic chronology payment_date >= order_date."""
    reference_ids = dict(reference_ids or {})
    errors = [[] for _ in range(len(df))]

    # 1. Foreign Key checks
    for col, parent, code in FK_RULES.get(name, []):
        allowed = reference_ids.get(parent)
        if allowed is None:
            from load.database import engine
            pk = PK[parent]
            with engine.connect() as conn:
                allowed = set(map(str, conn.execute(text(f'SELECT {pk} FROM core.{parent}')).scalars().all()))
        else:
            allowed = set(map(str, allowed))

        for pos, val in enumerate(df[col].astype(str).tolist()):
            if val not in allowed:
                errors[pos].append(code)

    # 2. Chronology check: payment_date >= order_date
    if name == 'payments' and 'payment_date' in df.columns:
        if order_dates is None:
            from ..database import engine
            with engine.connect() as conn:
                rows = conn.execute(text('SELECT order_id, order_date FROM core.orders')).all()
            order_dates = {str(r[0]): pd.Timestamp(r[1]) for r in rows}
        
        for pos, row in enumerate(df.itertuples(index=False)):
            o_id = str(getattr(row, 'order_id'))
            p_date = getattr(row, 'payment_date')
            o_date = order_dates.get(o_id)
            if o_date is not None and pd.notna(p_date):
                if pd.Timestamp(p_date) < o_date:
                    errors[pos].append('PAYMENT_BEFORE_ORDER')

    out = df.copy()
    out['error_code'] = ['|'.join(dict.fromkeys(e)) for e in errors]
    valid = out[out.error_code == ''].drop(columns='error_code')
    rejected = out[out.error_code != '']
    return valid, rejected
