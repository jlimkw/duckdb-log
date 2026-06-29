import os
from sre_parse import parse

import duckdb
import plotly.express as px
import polars as pl
import streamlit as st


class LogAnalyzer:
    def __init__(self, log_path):
        self.log_path = log_path
        self.conn = duckdb.connect()

    def parse_log(self) -> duckdb.DuckDBPyRelation:
        return self.conn.sql(f"""
        SELECT
            column0 AS ip,
            regexp_extract(column3, '[0-9].+$') AS date_time,
            regexp_extract(column5, '^[A-Z]+') AS rest_method,
            regexp_extract(column5, '/.+ ') AS rest_path,
            column6 AS return_status,
            column7 AS bytes
        FROM read_csv('{self.log_path}', delim=' ')
    """)

    def get_top_requests(self) -> pl.DataFrame:
        parsed_query = self.parse_log()
        return self.conn.sql("""
            SELECT * EXCLUDE(date_time,bytes), COUNT(*) AS count
            FROM parsed_query
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 10
            """).pl()


class JsonLogAnalyzer:
    def __init__(self, log_path):
        self.log_path = log_path
        self.conn = duckdb.connect()

    def parse_log(self) -> duckdb.DuckDBPyRelation:
        return self.conn.sql(f"""
            SELECT
                remote_ip AS ip,
                time AS date_time,
                regexp_extract(request, '^[A-Z]+') AS rest_method,
                regexp_extract(request, '/.+ ') AS rest_path,
                response AS return_status,
                bytes AS bytes
            FROM read_json('{self.log_path}')
        """)

    def get_top_requests(self) -> pl.DataFrame:
        parsed_query = self.parse_log()
        return self.conn.sql("""
            SELECT * EXCLUDE(date_time, bytes), COUNT(*) AS count
            FROM parsed_query
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()

    def get_top_rest_path_status(self) -> pl.DataFrame:
        parsed_query = self.parse_log()
        return self.conn.sql("""
            SELECT CONCAT(rest_method, ' ', rest_path) AS rest_path_status, return_status, COUNT(*) AS count
            FROM parsed_query
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()

    def get_top_errors_by_ip(self) -> pl.DataFrame:
        parsed_query = self.parse_log()
        return self.conn.sql("""
            SELECT ip, return_status, COUNT(*) AS count
            FROM parsed_query
            WHERE return_status >= 400 AND return_status < 600
            GROUP BY ALL
            ORDER BY count DESC
            LIMIT 5
            """).pl()

    def get_top_errors_by_rest_path(self) -> pl.DataFrame:
        parsed_query = self.parse_log()
        return self.conn.sql("""
            SELECT CONCAT(rest_method, ' ', rest_path) AS rest_path_status, return_status, COUNT(*) AS count
            FROM parsed_query
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

                st.subheader("Bar Chart")
                st.write("**Option 1: Plotly (ordered)**")
                fig = px.bar(top_errors_by_ip, x="ip", y="count")
                st.plotly_chart(fig, use_container_width=True)
            case _:
                st.write("Unsupported file format")


if __name__ == "__main__":
    frontend()
