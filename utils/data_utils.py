import os
import sqlite3
import pandas as pd
import streamlit as st


def excel2sqlite(filename: str, df: pd.DataFrame) -> None:
    """
    将excel转换为sqlite
    """
    conn = sqlite3.connect(f"./tmp/{filename}.sqlite")
    df.to_sql(filename, conn, if_exists='replace', index=False)
    conn.close()


@st.cache_data(ttl="2h")
def load_data(uploaded_file: str) -> str:
    """
    读取数据源
    """
    try:
        filename, ext = os.path.splitext(uploaded_file.name)
        ext = ext[1:].lower()
    except:
        filename = uploaded_file.name[::-1].split('.', 1)[-1][::-1]
        ext = uploaded_file.name.split('.')[-1]
    if not os.path.isdir("./tmp"):
        os.mkdir("./tmp")
    if ext in ["csv", "xls", "xlsx", "xlsm", "xlsb"]:
        df = pd.read_csv(uploaded_file) if ext == "csv" else pd.read_excel(uploaded_file)
        excel2sqlite(filename, df)
        return filename
    elif ext in ["sqlite", "db"]:
        with open(f"./tmp/{filename}.sqlite", "wb") as fp:
            fp.write(uploaded_file.getvalue())
        return filename
    else:
        st.error(f"Unsupported file format: {ext}")
        return None


def get_create_statements(database_path: str) -> str:
    """
    获取数据库schema
    """
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cursor.fetchall()
    conn.close()
    return "```sql\n" + "\n\n".join(create_sql for _, create_sql in tables) + "\n```"


def execute_sql(query: str, database_path: str) -> pd.DataFrame:
    """
    执行sql语句
    """
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return pd.DataFrame([list(row) for row in result], columns=columns)
    except:
        return pd.DataFrame()
