import os

import duckdb
import plotly.express as px
import polars as pl
import streamlit as st


class LogAnalyzer:
    def __init__(self, log_path):
        self.log_path = log_path
        self.conn = duckdb.connect()

        self.conn.sql(f"""
            CREATE OR REPLACE TEMP VIEW parsed_logs AS
            SELECT
                column0 AS ip,
                strptime(regexp_replace(column3, ' \\+\\d{4}$', ''), '%d/%b/%Y:%H:%M:%S') AS date_time
                regexp_extract(column5, '^[A-Z]+') AS rest_method,
                regexp_extract(column5, '/.+ ') AS rest_path,
                column6 AS return_status,
                column7 AS bytes
            FROM read_csv('{self.log_path}', delim=' ')
            """)

    def get_top_requests(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT * EXCLUDE(date_time,bytes), COUNT(*) AS count
            FROM parsed_logs
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 10
            """).pl()


class JsonLogAnalyzer:
    def __init__(self, log_path):
        self.log_path = log_path
        self.conn = duckdb.connect()
        self.conn.sql(f"""
            CREATE OR REPLACE TEMP VIEW parsed_logs AS
            SELECT
                remote_ip AS ip,
                strptime(time, '%d/%b/%Y:%H:%M:%S %z') AS date_time,
                regexp_extract(request, '^[A-Z]+') AS rest_method,
                regexp_extract(request, '/.+ ') AS rest_path,
                response AS return_status,
                bytes AS bytes
            FROM read_json('{self.log_path}')
        """)

    def get_daily_info(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT DATE(date_time) AS date,
            COUNT(*) AS total_requests,
            COUNT(DISTINCT ip) AS unique_ips,
            COUNT(DISTINCT rest_path) AS unique_paths,
            SUM(bytes) AS total_bytes
            FROM parsed_logs
            GROUP BY ALL
            ORDER BY ALL
            """).pl()

    def get_top_requests(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT * EXCLUDE(date_time, bytes), COUNT(*) AS count
            FROM parsed_logs
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()

    def get_top_rest_path_status(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT CONCAT(rest_method, ' ', rest_path) AS rest_path_status, return_status, COUNT(*) AS count
            FROM parsed_logs
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()

    def get_top_errors_by_ip(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT ip, return_status, COUNT(*) AS count
            FROM parsed_logs
            WHERE return_status >= 400 AND return_status < 600
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 10
            """).pl()

    def get_top_errors_by_rest_path(self) -> pl.DataFrame:
        return self.conn.sql("""
            SELECT CONCAT(rest_method, ' ', rest_path) AS rest_path_status, return_status, COUNT(*) AS count
            FROM parsed_logs
            WHERE return_status >= 400 AND return_status < 600
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()


def frontend():
    st.title("DuckDB Log Analysis")
    LOG_DIR = "."
    log_files = []
    if os.path.exists(LOG_DIR):
        log_files = [f for f in os.listdir(LOG_DIR)]
    selected_filename = None
    if log_files:
        selected_filename = st.selectbox("Select a file", log_files, index=None)
    if selected_filename:
        file_path = os.path.join(LOG_DIR, selected_filename)
        match os.path.splitext(file_path)[-1]:
            case "csv" | "":
                log_analyzer = LogAnalyzer(file_path)
                top_10_requests = log_analyzer.get_top_requests()
                st.write("Top 10 Requests:")
                st.dataframe(top_10_requests)
            case ".jsonl":
                log_analyzer = JsonLogAnalyzer(file_path)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if total := log_analyzer.conn.sql(
                        f"SELECT count(*) FROM '{file_path}'"
                    ).fetchone():
                        st.metric("Total Requests", f"{total[0]}")
                with col2:
                    if errors := log_analyzer.conn.sql(
                        f"SELECT count(*) FROM '{file_path}' WHERE response >= 400 AND response < 600"
                    ).fetchone():
                        st.metric("Errors", f"{errors[0]}")
                with col3:
                    if ip_count := log_analyzer.conn.sql(
                        f"SELECT count(distinct remote_ip) FROM '{file_path}'"
                    ).fetchone():
                        st.metric("IP Count", f"{ip_count[0]}")
                top_10_requests = log_analyzer.get_top_requests()
                st.write("Top 10 Requests:")
                st.dataframe(top_10_requests)
                st.write("Top 5 Rest Path Status:")
                top_rest_path_status = log_analyzer.get_top_rest_path_status()
                st.dataframe(top_rest_path_status)
                st.write("Top Errors by IP:")
                top_errors_by_ip = log_analyzer.get_top_errors_by_ip()
                st.dataframe(top_errors_by_ip)
                st.write("Top Errors by Rest Path:")
                top_errors_by_rest_path = log_analyzer.get_top_errors_by_rest_path()
                st.dataframe(top_errors_by_rest_path)
                st.write("Daily Info:")
                daily_info = log_analyzer.get_daily_info()
                st.write("Daily Info")
                fig = px.line(
                    daily_info,
                    x="date",
                    y=["total_requests", "unique_ips"],
                    title="Daily Traffic Trend",
                    labels={"date": "Date", "total_requests": "Total Requests"},
                    markers=True,  # Adds distinct dots to each day's data point
                )
                st.plotly_chart(fig, width="stretch")

                st.write("Top Errors by IP")
                fig = px.bar(
                    top_errors_by_ip,
                    x="ip",
                    y="count",
                    labels={"ip": "IP Address", "count": "Error Count"},
                )
                st.plotly_chart(fig, width="stretch")
            case _:
                st.write("Unsupported file format")


if __name__ == "__main__":
    frontend()
