import streamlit as st
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk
from .type_utils import *

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def chat(messages: Messages) -> str:
    """
    与llm对话
    """
    client = OpenAI(
        api_key=st.session_state.settings["api_key"],
        base_url=st.session_state.settings["base_url"],
    )
    messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    handler = st.session_state.get("handler", None)
    if handler:
        handler.on_llm_start(None, None)
    completion = client.chat.completions.create(
        model=st.session_state.settings["model"],
        messages=messages,
        temperature=st.session_state.settings["temperature"],
        stream=True,
    )
    collected_messages = []
    for chunk in completion:
        chunk_message = chunk.choices[0].delta.content
        if chunk_message:
            collected_messages.append(chunk_message)
            handler.on_llm_new_token(chunk_message)
    if handler:
        handler.on_llm_end(None)
        handler.on_agent_finish(None)
    response = ''.join(collected_messages)
    logger.info("User:\n" + messages[-1]["content"])
    logger.info("Assistant:\n" + response)
    return response


def chat_stream(messages: Messages) -> Stream[ChatCompletionChunk]:
    """
    流式对话
    """
    client = OpenAI(
        api_key=st.session_state.settings["api_key"],
        base_url=st.session_state.settings["base_url"],
    )
    messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    completion = client.chat.completions.create(
        model=st.session_state.settings["model"],
        messages=messages,
        temperature=st.session_state.settings["temperature"],
        stream=True,
    )
    return completion
