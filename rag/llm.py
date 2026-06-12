# -*-coding: utf-8 -*-
"""
通义千问调用封装，与 1-情感分析-Qwen.py 保持一致。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import dashscope
from dashscope import Generation

def normalize_api_key(raw: str) -> str:
    """从环境变量值中提取 sk- 密钥，去掉中文说明、引号、BOM 等。"""
    if not raw:
        return ""
    text = raw.strip().strip('"').strip("'").replace("\ufeff", "").replace("\r", "")
    m = re.search(r"(sk-[A-Za-z0-9_-]+)", text)
    if m:
        return m.group(1)
    return text


def ensure_api_key() -> str:
    """每次从环境变量读取密钥（支持 Mac ~/.zshrc 已配置的情况）。"""
    raw = os.getenv("DASHSCOPE_API_KEY", "")
    key = normalize_api_key(raw)
    if not key:
        raise RuntimeError(
            "未设置 DASHSCOPE_API_KEY。\n"
            "请在 ~/.zshrc 中加入一行（仅英文密钥，不要中文）：\n"
            "  export DASHSCOPE_API_KEY=sk-xxxxxxxx\n"
            "然后执行: source ~/.zshrc"
        )
    if not key.startswith("sk-"):
        raise RuntimeError(
            "DASHSCOPE_API_KEY 中未找到 sk- 开头的密钥。\n"
            "请打开 ~/.zshrc，把该行改成只有密钥，例如：\n"
            "  export DASHSCOPE_API_KEY=sk-你的密钥\n"
            "不要写：export DASHSCOPE_API_KEY=阿里云密钥sk-xxx"
        )
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 仍含非法字符。请编辑 ~/.zshrc，"
            "确保等号后面只有 sk- 开头的英文密钥。"
        ) from None
    if key != raw.strip():
        os.environ["DASHSCOPE_API_KEY"] = key
    dashscope.api_key = key
    return key


def get_response(
    messages: list[dict[str, str]],
    model: str = "qwen-turbo",
    *,
    stream: bool = False,
    **kwargs: Any,
):
    """调用 dashscope Generation.call，result_format=message。"""
    return Generation.call(
        model=model,
        messages=messages,
        result_format="message",
        stream=stream,
        **kwargs,
    )


def chat_text(
    messages: list[dict[str, str]],
    model: str = "qwen-turbo",
) -> str:
    ensure_api_key()
    resp = get_response(messages, model=model)
    if resp.status_code != 200:
        raise RuntimeError(f"DashScope 错误: {resp.code} {resp.message}")
    return resp.output.choices[0].message.content


def chat_json(
    messages: list[dict[str, str]],
    model: str = "qwen-turbo",
) -> dict:
    text = chat_text(messages, model=model)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)
