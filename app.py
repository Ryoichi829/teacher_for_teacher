from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import streamlit as st
from agents import Runner, SQLiteSession
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

try:
    from teacher_agent import teacher_agent

    AGENT_IMPORT_ERROR: Exception | None = None
except Exception as e:
    teacher_agent = None
    AGENT_IMPORT_ERROR = e


TOOL_LABELS = {
    "search_lesson_plan": "学習指導案",
    "search_slide_guide": "スライド・スピーチ原稿",
    "search_web_app_guide": "Webアプリガイド",
}


def _raw_value(raw_item: object, key: str) -> object | None:
    if isinstance(raw_item, dict):
        return raw_item.get(key)
    return getattr(raw_item, key, None)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def extract_tool_details(result: object) -> list[dict[str, str]]:
    """今回の実行で使われたTool名、入力、返却内容だけを取り出す。"""
    details: list[dict[str, str]] = []
    by_call_id: dict[str, dict[str, str]] = {}

    for item in getattr(result, "new_items", []):
        item_type = getattr(item, "type", "")
        raw_item = getattr(item, "raw_item", None)

        if item_type == "tool_call_item":
            call_id = str(getattr(item, "call_id", None) or "")
            tool_name = str(
                getattr(item, "tool_name", None)
                or _raw_value(raw_item, "name")
                or "unknown_tool"
            )
            arguments = _as_text(
                _raw_value(raw_item, "arguments")
                or _raw_value(raw_item, "input")
            )
            detail = {
                "tool_name": tool_name,
                "label": TOOL_LABELS.get(tool_name, tool_name),
                "arguments": arguments,
                "output": "",
            }
            details.append(detail)
            if call_id:
                by_call_id[call_id] = detail

        elif item_type == "tool_call_output_item":
            call_id = str(getattr(item, "call_id", None) or "")
            output = _as_text(getattr(item, "output", None))
            if call_id and call_id in by_call_id:
                by_call_id[call_id]["output"] = output
            else:
                details.append(
                    {
                        "tool_name": "tool_output",
                        "label": "参照結果",
                        "arguments": "",
                        "output": output,
                    }
                )

    return details


def show_tool_details(details: list[dict[str, str]]) -> None:
    if not details:
        return
    labels = "、".join(dict.fromkeys(d["label"] for d in details))
    with st.expander(f"今回参照した資料：{labels}"):
        st.caption("AIの非公開の思考過程ではなく、Toolに渡した条件とToolから返った資料です。")
        for index, detail in enumerate(details):
            if index:
                st.divider()
            st.markdown(f"**{detail['label']}**")
            if detail["arguments"]:
                st.caption("検索条件")
                st.code(detail["arguments"], language="json")
            if detail["output"]:
                st.caption("検索結果")
                st.text(detail["output"])


st.set_page_config(page_title="先生のための先生 mini v0.3", page_icon="🎓", layout="centered")

st.title("🎓 先生のための先生 mini v0.3")
st.caption("学習指導案、スライド、スピーチ原稿、Webアプリガイドに沿って、生成AI（自然言語）の100分授業を支援します")

api_key_ready = bool(os.getenv("OPENAI_API_KEY"))
agent_ready = teacher_agent is not None

if not api_key_ready:
    st.warning("OPENAI_API_KEY が設定されていません。.env にAPIキーを設定してから利用してください。")
if not agent_ready:
    st.error(
        "教材またはエージェントを読み込めませんでした。teacher_agent.py と "
        "knowledge/lesson_plan.json、knowledge/slide_guides.json、"
        "knowledge/web_apps/*.json の配置を確認してください。"
    )
    if AGENT_IMPORT_ERROR is not None:
        with st.expander("エラーの詳細"):
            st.code(f"{type(AGENT_IMPORT_ERROR).__name__}: {AGENT_IMPORT_ERROR}")

if "session_id" not in st.session_state:
    st.session_state.session_id = f"teacher-{uuid.uuid4().hex[:10]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

session = SQLiteSession(
    st.session_state.session_id,
    str(BASE_DIR / "conversation_history.db"),
)

with st.sidebar:
    st.header("v0.3 の範囲")
    st.write("- Agentは1人")
    st.write("- 学習指導案を検索するTool")
    st.write("- スライド・スピーチ原稿を検索するTool")
    st.write("- Webアプリガイドを検索するTool")
    st.write("- 会話はSQLite Sessionで保持")
    st.write("- ベクトルDB / 複数Agentはまだ導入しない")
    st.divider()
    st.write("**試してほしい質問**")
    examples = [
        "Word2Vecを生徒にどう説明すればいいですか？",
        "分かち書きアプリでは、何を入力させればよいですか？",
        "Word2Vecの単語のアナロジーは、どう進めればよいですか？",
        "Attentionのヒートマップは、どのように説明すればよいですか？",
        "スライド38のColab実習は、どのように進めればよいですか？",
        "スライド25では、どのように話せばよいですか？",
        "スライド12〜13のスピーチ原稿を確認したいです。",
        "lossを高校生にどう説明すればいいですか？",
        "前半のワークシートは何のために行いますか？",
    ]
    for q in examples:
        st.caption("・" + q)
    if st.button("新しい会話を開始"):
        st.session_state.session_id = f"teacher-{uuid.uuid4().hex[:10]}"
        st.session_state.messages = []
        st.rerun()
    st.caption("新しい会話を開始しても、過去のログはSQLiteに残ります。")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            show_tool_details(msg.get("tool_details", []))

prompt = st.chat_input(
    "授業について質問してください",
    disabled=not (api_key_ready and agent_ready),
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        tool_details: list[dict[str, str]] = []
        with st.spinner("指導案・スライド・スピーチ原稿・Webアプリガイドを確認しています…"):
            try:
                result = Runner.run_sync(
                    teacher_agent,
                    prompt,
                    session=session,
                )
                answer = str(result.final_output)
                tool_details = extract_tool_details(result)
            except Exception as e:
                answer = (
                    "実行時にエラーが発生しました。APIキー、ネットワーク、"
                    "openai-agents のインストール状況を確認してください。\n\n"
                    f"`{type(e).__name__}: {e}`"
                )
        st.markdown(answer)
        show_tool_details(tool_details)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "tool_details": tool_details}
    )
