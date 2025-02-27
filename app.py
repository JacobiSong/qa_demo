import re
from typing import List, Any, Optional
from datetime import datetime
import textwrap
import streamlit as st
from streamlit.external.langchain import StreamlitCallbackHandler

from utils.chat_utils import *
from utils.str_utils import *
from utils.data_utils import *
from prompts import *


def is_db_related_question(messages: Messages, database_path: str) -> bool:
    """
    检查问题是否与数据库有关
    """
    history, question = chat_history_formatter(messages[:-1]), messages[-1]["content"]
    messages = [
        {
            "role": "system",
            "content": DB_RELATED_QUESTION_PROMPT,
        },
        {
            "role": "user",
            "content": f"Database Schema:\n{get_create_statements(database_path)}\n\nChat history:\n{history}\n\nUser's Question: \"{question}\"\nLet's think step by step."
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Is DB related question**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Is DB related question**: **Complete!**"
    response = extract_xml(chat(messages), "response").lower()
    if response not in ["yes", "no"]:
        return "yes" in response
    else:
        return response == "yes"


def rewrite_question(messages: Messages, database_path: str) -> Optional[str]:
    """
    重写与数据库相关的问题
    """
    history, question = chat_history_formatter(messages[:-1]), messages[-1]["content"]
    messages = [
        {
            "role": "system",
            "content": REWRITE_QUESTION_PROMPT,
        },
        {
            "role": "user",
            "content": f"Database Schema:\n{get_create_statements(database_path)}\n\nChat history:\n{history}\n\nUser's Question: \"{question}\"\nLet's think step by step."
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Rewrite question**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Rewrite question**: **Complete!**"
    return extract_xml(chat(messages), "rewritten_question")


def planning(question: str, database_path: str) -> Optional[Any]:
    """
    指定计划
    """
    messages = [
        {
            "role": "system",
            "content": PLANNING_PROMPT,
        },
        {
            "role": "user",
            "content": f"{get_create_statements(database_path)}\n\"{question}\"\nLet's think step by step.",
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Make a plan**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Make a plan**: **Complete!**"
    jsons = extract_json_strings(chat(messages))
    plan = jsons[-1] if jsons else None
    if plan and "plan" in plan:
        plan["question"] = question
        if not isinstance(plan["plan"], list):
            plan["plan"] = []
        has_summary = False
        for step in plan["plan"]:
            if not isinstance(step, dict):
                continue
            operation = step.get("operation", "")
            if not isinstance(operation, str):
                step["operation"] = "error"
                continue
            operation = operation.lower().strip()
            if operation not in ["sql_gen", "visualization", "summary"]:
                step["operation"] = "error"
                continue
            step["operation"] = operation

            step_number = step.get("step", 0)
            if isinstance(step_number, str):
                try:
                    step_number = int(step_number)
                except:
                    step_number = 0
            if not isinstance(step_number, int) or step_number < 1:
                step["operation"] = "error"
                continue
            step["step"] = step_number
            
            params = step.get("parameters", {})
            if operation == "sql_gen":
                if "question" not in params or not isinstance(params["question"], str) or not params["question"].strip():
                    step["operation"] = "error"
                    continue
                params["question"] = params["question"].strip()
            elif operation == "visualization":
                chart_type = params.get("chart_type", "")
                data_source = params.get("data_source", [])
                title = params.get("title", "")
                if not isinstance(chart_type, str) or not isinstance(data_source, list) or not isinstance(title, str):
                    step["operation"] = "error"
                    continue
                chart_type = chart_type.lower().strip()
                title = title.strip()
                for i in range(len(data_source)):
                    if isinstance(data_source[i], str):
                        try:
                            data_source[i] = int(data_source[i])
                        except:
                            data_source[i] = 0
                data_source = [i for i in data_source if isinstance(i, int) and i > 0 and i < step["step"] and plan["plan"][i - 1]["operation"] == "sql_gen"]
                if not chart_type or not data_source or not title or chart_type not in ["line", "bar", "area", "scatter"]:
                    step["operation"] = "error"
                    continue
                params["chart_type"] = chart_type
                params["title"] = title
                params["data_source"] = data_source
            else:
                has_summary = True
        if has_summary:
            plan["plan"] = [step for step in plan["plan"] if isinstance(step, dict) and step["operation"] != "error"]
            return plan


def generate_sql(question: str, database_path: str) -> Optional[str]:
    """
    根据自然语言问题生成sql
    """
    messages = [
        {
            "role": "system",
            "content": GENERATE_SQL_PROMPT,
        },
        {
            "role": "user",
            "content": f"{get_create_statements(database_path)}\n\"{question}\"\nLet's think step by step.",
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Generate a SQL**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Generate a SQL**: **Complete!**"
    codes = extract_code(chat(messages), "sql")
    if codes:
        return codes[-1]


def draw_chart(chart_type: str, data_source: List[int], title: str, database_path: str, plan: Any) -> Optional[str]:
    """
    画图
    """
    dfs = [step["query_result"] for step in plan["plan"] if step["step"] in data_source and step["result"]]
    messages = [
        {
            "role": "system",
            "content": DRAW_CHART_PROMPT,
        },
        {
            "role": "user",
            "content": f"Dataframe preview:\n{pd_df_formatter(dfs)}\nChart type: {chart_type}\nTitle: \"{title}\"\nLet's think step by step.",
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Draw a chart**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Draw a chart**: **Complete!**"
    codes = extract_code(chat(messages), "python")
    if codes:
        return codes[-1]


def summary(plan: Any, database_path: str) -> Optional[str]:
    """
    总结
    """
    plan, question = plan["plan"], plan["question"]
    relevant_queries = [step for step in plan if step["operation"] == "sql_gen" and step["result"]]
    relevant_queries = '\n'.join(
        [f"**Query {idx + 1}**\n```sql\n-- {step["parameters"]["question"]}\n{step["result"]}\n```\n**Result {idx + 1}**\n{pd_df_formatter(step["query_result"], head=False)}"
            for idx, step in enumerate(relevant_queries)])
    if not relevant_queries:
        relevant_queries = "No Relevant Queries"

    relevant_charts = [step for step in plan if step["operation"] == "visualization" and step["result"]]
    relevant_charts = '\n'.join([f"**Chart {idx + 1}**\n```python\n# Title: \"{step["parameters"]["title"]}\"\n{step["result"]}\n```"
                                    for idx, step in enumerate(relevant_charts)])
    if not relevant_charts:
        relevant_charts = "No Relevant Charts"

    messages = [
        {
            "role": "system",
            "content": SUMMARY_PROMPT,
        },
        {
            "role": "user",
            "content": f"Database Schema:\n{get_create_statements(database_path)}\n\nRelevant queries:\n{relevant_queries}\n\nRelevant charts:\n{relevant_charts}\n\nUser's question: \"{question}\"\nLet's think step by step.",
        },
    ]
    st.session_state["handler"]._thought_labeler.get_initial_label = lambda: "**Summary**: Thinking..."
    st.session_state["handler"]._thought_labeler.get_final_agent_thought_label = lambda: "**Summary**: **Complete!**"
    response = extract_xml(chat(messages), "response")
    return response


def execute_plan(plan: Optional[Any], database_path: str) -> Optional[str]:
    """
    执行规划
    """
    if not plan:
        return None
    for step in plan["plan"]:
        operation = step["operation"]
        params = step.get("parameters", {})
        if operation == "sql_gen":
            sql = generate_sql(params["question"], database_path)
            step["result"] = sql
            step["query_result"] = execute_sql(sql, database_path)
        elif operation == "visualization":
            code = draw_chart(params["chart_type"], params["data_source"], params["title"], database_path, plan)
            step["result"] = code
        else:
            response = summary(plan, database_path)
            step["result"] = response
            return response


def chart(type: str, data: pd.DataFrame, x: str, y: Union[str, List[str]], horizontal: bool=False, stack: Optional[Union[bool, str]]=None) -> None:
    """
    图渲染
    """
    if type == "line":
        st.line_chart(data, x=x, y=y)
    elif type == "bar":
        st.bar_chart(data, x=x, y=y, horizontal=horizontal, stack=stack)
    elif type == "scatter":
        st.scatter_chart(data, x=x, y=y)
    elif type == "area":
        st.area_chart(data, x=x, y=y, stack=stack)


def write_response(response: str, plan: Any) -> str:
    """
    渲染模型输出
    """
    plan = plan["plan"]
    relevant_queries = [step for step in plan if step["operation"] == "sql_gen" and step["result"]]
    relevant_charts = [step for step in plan if step["operation"] == "visualization" and step["result"]]
    response = response.split('\n')
    with st.chat_message("assistant"):
        all_ = set()
        all_buffer = []
        buffer = []
        for line in response:
            all_buffer.append(line)
            buffer.append(line)
            pattern = r'\*\*(Query|Chart)\s*\d+\*\*'
            matches = re.finditer(pattern, line, flags=re.IGNORECASE)
            for match in matches:
                tmp = match.group().strip("*").lower()
                t = "query" if tmp.startswith("query") else "chart"
                n = int(tmp[5:])
                if t + str(n) in all_:
                    continue
                all_.add(t + str(n))
                st.write('\n'.join(buffer))
                buffer = []
                if t == "query":
                    step = relevant_queries[n - 1]
                    all_buffer.append(f"**Query {n}:**\n```sql\n{step["result"]}\n```\n**Result {n}:**\n{pd_df_formatter(step["query_result"], head=False)}")
                    st.write(f"**Query {n}:**\n```sql\n{step["result"]}\n```\n**Result {n}:**")
                    st.table(step["query_result"])
                else:
                    step = relevant_charts[n - 1]
                    dfs = [s["query_result"] for s in plan if s["step"] in step["parameters"]["data_source"] and s["result"]]
                    dfs_preview = '\n'.join(["# " + line for line in pd_df_formatter(dfs).split('\n')])
                    all_buffer.append(f"**Chart {n}:** {step["parameters"]["title"]}\n```python\n{dfs_preview}\n{step["result"]}\n```")
                    st.write(f"**Chart {n}:** {step["parameters"]["title"]}\n")
                    local_vars = {f"df{i + 1}": df for i, df in enumerate(dfs)}
                    local_vars["chart"] = chart
                    exec(step["result"], {}, local_vars)
        if buffer:
            st.write('\n'.join(buffer))
            buffer = []
    return '\n'.join(all_buffer)


@st.dialog("Settings")
def settings() -> None:
    """
    设置页面
    """
    base_url = st.text_input("base_url", st.session_state.settings["base_url"])
    api_key = st.text_input("api_key", st.session_state.settings["api_key"])
    model = st.text_input("model", st.session_state.settings["model"])
    temperature = st.slider("temperature", 0.0, 2.0, st.session_state.settings["temperature"], .05)
    if st.button("Confirm", type="primary"):
        st.session_state["settings"] = {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
        }
        st.rerun()


if __name__ == "__main__":
    if "settings" not in st.session_state:
        st.session_state["settings"] = {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "",
            "model": "deepseek-v3",
            "temperature": 0.0,
        }

    if "histories" not in st.session_state:
        st.session_state["histories"] = []
    histories = st.session_state["histories"]

    if "curr_idx" not in st.session_state:
        st.session_state["curr_idx"] = -1

    with st.sidebar:
        if st.button("New Chat", icon=":material/forum:", use_container_width=True, type="primary"):
            st.session_state["messages"] = []
            st.session_state["curr_idx"] = -1
        if histories:
            st.text("Chat History")
            for i, history in enumerate(histories):
                if st.button(textwrap.shorten(history[0], width=25, placeholder="..."), key=history[2], use_container_width=True):
                    if i != st.session_state.curr_idx:
                        st.session_state["messages"] = history[1]
                        st.session_state.curr_idx = i
        st.text("Settings")
        st.button("Settings", icon=":material/settings:", use_container_width=True, on_click=settings)

    if not st.session_state["settings"]["api_key"]:
        st.warning("Please enter your api_key")
        st.stop()

    uploaded_file = st.file_uploader(
        "Upload a Data file",
        type=list(["csv", "xls", "xlsx", "xlsm", "xlsb", "sqlite", "db"]),
        help="Various File formats are Support",
    )

    if uploaded_file:
        filename = load_data(uploaded_file)
        database_path = f"./tmp/{filename}.sqlite"

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state.messages:
        if "render" in msg:
            write_response(msg["render"]["response"], msg["render"]["plan"])
        else:
            st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input(placeholder="Ask me anything!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        st.session_state["handler"] = StreamlitCallbackHandler(st.container(),
            max_thought_containers=100,
            expand_new_thoughts=True,
            collapse_completed_thoughts=True,
        )
        db_related = False
        if uploaded_file and is_db_related_question(st.session_state.messages, database_path):
            question = rewrite_question(st.session_state.messages, database_path)
            if not question:
                question = prompt
            plan = planning(question, database_path)
            response = execute_plan(plan, database_path)
            if response:
                db_related = True
                plain_text = write_response(response, plan)
                st.session_state.messages.append({"role": "assistant", "content": plain_text, "render": {"response": response, "plan": plan}})
        if not db_related:
            stream = chat_stream(st.session_state.messages)
            with st.chat_message("assistant"):
                response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response})
        curr_idx = st.session_state.curr_idx
        if curr_idx == -1:
            st.session_state.histories.insert(0, (prompt.replace("\n", " "), st.session_state.messages, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            st.session_state.curr_idx = 0
