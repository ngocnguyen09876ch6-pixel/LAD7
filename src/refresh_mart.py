import csv
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from src.load_postgres import engine
from src.logger import get_logger

log = get_logger(__name__)
ROOT = Path(__file__).parent.parent

def get_kpi(conn):
    sql = """
    SELECT 
        COALESCE(SUM(net_amount), 0) AS total_revenue,
        COALESCE(COUNT(DISTINCT order_id), 0) AS order_count,
        COALESCE(COUNT(DISTINCT CASE WHEN order_status = 'completed' THEN order_id END), 0) AS completed_orders,
        COALESCE(SUM(quantity), 0) AS total_items_sold
    FROM mart.fact_sales
    JOIN mart.dim_order_status USING (order_status_sk);
    """
    try:
        row = conn.execute(text(sql)).fetchone()
        return [float(x) for x in row] if row else [0.0, 0.0, 0.0, 0.0]
    except ProgrammingError:
        return [0.0, 0.0, 0.0, 0.0]

def run_refresh():
    log.info("[7/8] Bắt đầu làm mới Data Mart và tính toán KPI...")
    
    with engine.connect() as conn:
        log.info("Đang truy vấn KPI Before...")
        kpi_before = get_kpi(conn)
        conn.commit() 
        
        sql_file = ROOT / "sql" / "solutions" / "12_load_data_mart.sql"
        sql_content = sql_file.read_text(encoding="utf-8")
        
        with conn.begin():
            statements = sql_content.split(';')
            for i, stmt in enumerate(statements):
                if stmt.strip(): 
                    log.info(f"Đang thực thi lệnh SQL số {i+1}...")
                    conn.execute(text(stmt))
        log.info("Thực thi SQL Data Mart thành công.")
        
        log.info("Đang truy vấn KPI After...")
        kpi_after = get_kpi(conn)
    
    kpi_names = ["total_revenue", "order_count", "completed_orders", "total_items_sold"]
    csv_path = ROOT / "docs" / "kpi_comparison.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["kpi", "before", "after", "diff"])
        for i, name in enumerate(kpi_names):
            diff = kpi_after[i] - kpi_before[i]
            writer.writerow([name, kpi_before[i], kpi_after[i], diff])
            
    log.info("Đã xuất báo cáo KPI so sánh tại %s", csv_path)

if __name__ == "__main__":
    run_refresh()