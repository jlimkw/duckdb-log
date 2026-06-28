import duckdb


def parse_normal_log():
    parsed_query = duckdb.sql("""
        SELECT
            column0 AS ip,
            regexp_extract(column3, '[0-9].+$') AS date_time,
            regexp_extract(column5, '^[A-Z]+') AS rest_method,
            regexp_extract(column5, '/.+ ') AS rest_path,
            column6 AS return_status,
            column7 AS bytes
        FROM read_csv('nginx_log', delim=' ')
    """)

    duckdb.sql("""
        SELECT * EXCLUDE(date_time,bytes), COUNT(*) AS count
        FROM parsed_query
        GROUP BY ALL
        ORDER BY count DESC
        LIMIT 10
        """).show()
    # duckdb.sql("SELECT * FROM read_csv('nginx_log', delim=' ')").show()


def parse_jsonl_log():
    parsed_query = duckdb.sql("""
        SELECT
            remote_ip AS ip,
            time AS date_time,
            regexp_extract(request, '^[A-Z]+') AS rest_method,
            regexp_extract(request, '/.+ ') AS rest_path,
            response AS return_status,
            bytes AS bytes
        FROM read_json('nginx_log.jsonl')
    """)

    duckdb.sql("""
        SELECT * EXCLUDE(date_time, bytes), COUNT(*) AS count
        FROM parsed_query
        GROUP BY ALL
        ORDER BY count DESC
        LIMIT 10
        """).show()


if __name__ == "__main__":
    parse_normal_log()
    parse_jsonl_log()
