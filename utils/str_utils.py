import re
import json
import pandas as pd
from typing import Any, Optional, Union
from xml.etree import ElementTree
from .type_utils import *


def is_valid_json(s: str) -> bool:
    """
    判断字符串是不是json格式
    """
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False


def extract_json_strings(s: str) -> List[Any]:
    """
    提取字符串中的所有json串
    """
    result = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] in ('{', '['):
            stack = [s[i]]
            start = i
            max_j = -1
            in_string = False
            escaped = False
            j = i + 1
            while j < n:
                c = s[j]
                if not in_string:
                    if c == '"':
                        in_string = True
                        escaped = False
                    elif c in ('{', '['):
                        stack.append(c)
                    elif c == '}':
                        if stack and stack[-1] == '{':
                            stack.pop()
                        else:
                            break
                    elif c == ']':
                        if stack and stack[-1] == '[':
                            stack.pop()
                        else:
                            break
                else:
                    if escaped:
                        escaped = False
                    else:
                        if c == '\\':
                            escaped = True
                        elif c == '"':
                            in_string = False
                if not stack:
                    substr = s[start:j+1]
                    if is_valid_json(substr):
                        max_j = j
                j += 1
            if max_j != -1:
                result.append(s[start:max_j+1])
                i = max_j + 1
            else:
                i += 1
        else:
            i += 1
    result = [json.loads(j) for j in result]
    return result


def extract_xml(s: str, label: str) -> Optional[str]:
    """
    提取字符串中的xml块
    """
    try:
        root = ElementTree.fromstring(f"<root>{s}</root>")
        res = root.find(label).text.strip()
    except ElementTree.ParseError:
        match = re.search(re.escape(f"<{label}>") + r'\n?(.*?)\n?' + re.escape(f"</{label}>"), s, re.DOTALL | re.IGNORECASE)
        res = match.group(1).strip() if match else None
    return res


def extract_code(markdown_str: str, code_language: str) -> List[str]:
    """
    提取Markdown中的代码块
    """
    pattern = r"```" + re.escape(code_language) + r"\s*(.*?)\s*```"
    matches = re.findall(pattern, markdown_str, re.DOTALL | re.IGNORECASE)
    code_blocks = [block.strip() for block in matches]
    return code_blocks


def chat_history_formatter(messages: Messages) -> str:
    """
    格式化聊天记录
    """
    return '\n'.join([f"{message["role"][0].upper() + message["role"][1:]}: \"{message["content"]}\"" for message in messages]) or "Empty Chat History"


def pd_df_formatter(dfs: Union[pd.DataFrame, List[pd.DataFrame]], head: bool=True) -> str:
    """
    格式化pandas DataFrame
    """
    if isinstance(dfs, list):
        mds = [pd_df_formatter(df, head=head) for df in dfs]
        dfs_preview = []
        for i, md in enumerate(mds):
            if head:
                dfs_preview.append(f"df{i + 1}.head().to_markdown():\n{md}")
            else:
                dfs_preview.append(f"df{i + 1}.to_markdown():\n{md}")
        return '\n'.join(dfs_preview)
    if head:
        dfs = dfs.head()
    return dfs.to_markdown(index=False).replace("|:", "|-").replace(":|", "-|") or "Empty DataFrame"
