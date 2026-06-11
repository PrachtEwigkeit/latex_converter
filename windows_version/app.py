# -*- coding: utf-8 -*-

import streamlit as st

from chatgpt_latex_cleaner import (
    convert_text,
    format_report,
    read_clipboard,
    write_clipboard,
)


st.set_page_config(
    page_title="ChatGPT LaTeX Cleaner",
    page_icon="🧮",
    layout="wide",
)


st.title("ChatGPT 网页复制文本 LaTeX 清洗器")

st.caption(
    "左侧粘贴从网页版 ChatGPT 复制出来的原始文本，点击转换后，右侧输出适配 Markdown + LaTeX 的文本。"
)


# -----------------------------
# 侧边栏设置
# -----------------------------

with st.sidebar:
    st.header("转换设置")

    strict_mode = st.checkbox(
        "严格模式",
        value=False,
        help="开启后，不会自动把 (q)、(M)、(y) 这类单字母括号转换为公式。",
    )

    repair_formula = st.checkbox(
        "修复公式内部损坏",
        value=True,
        help="例如把 {q_i}*{i=1}^N 修复为 {q_i}_{i=1}^N。",
    )

    show_report = st.checkbox(
        "显示转换报告",
        value=True,
    )

    st.divider()

    st.markdown(
        """
        **主要转换规则**

        - 单独一行的 `[` / `]` 包围内容 → `$$...$$`
        - 疑似公式的 `(f(q)=y)` → `$f(q)=y$`
        - 保护代码块、行内代码、Markdown 链接
        """
    )


# -----------------------------
# 初始化 session state
# -----------------------------

if "converted_text" not in st.session_state:
    st.session_state.converted_text = ""

if "report_text" not in st.session_state:
    st.session_state.report_text = ""

if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""

if "raw_text_input" not in st.session_state:
    st.session_state.raw_text_input = st.session_state.raw_text

if "converted_text_area" not in st.session_state:
    st.session_state.converted_text_area = st.session_state.converted_text

if "status_message" not in st.session_state:
    st.session_state.status_message = ""

if "status_kind" not in st.session_state:
    st.session_state.status_kind = "info"


def run_conversion(raw: str) -> str:
    converted, stats = convert_text(
        raw,
        allow_single_letter=not strict_mode,
        do_repair=repair_formula,
    )

    st.session_state.raw_text = raw
    st.session_state.converted_text = converted
    st.session_state.report_text = format_report(stats)
    st.session_state.raw_text_input = raw
    st.session_state.converted_text_area = converted

    return converted


def set_status(message: str, kind: str = "info") -> None:
    st.session_state.status_message = message
    st.session_state.status_kind = kind


# -----------------------------
# 顶部操作按钮
# -----------------------------

button_col1, button_col2, button_col3, _ = st.columns([1, 1, 1, 5])

with button_col1:
    one_click_clicked = st.button("一键使用", type="primary", use_container_width=True)

with button_col2:
    convert_clicked = st.button("转换", use_container_width=True)

with button_col3:
    clear_clicked = st.button("清空", use_container_width=True)


if clear_clicked:
    st.session_state.raw_text = ""
    st.session_state.converted_text = ""
    st.session_state.report_text = ""
    st.session_state.raw_text_input = ""
    st.session_state.converted_text_area = ""
    set_status("")

elif one_click_clicked:
    try:
        clipboard_text = read_clipboard()
        converted_text = run_conversion(clipboard_text)
        write_clipboard(converted_text)
        copied_ok = read_clipboard() == converted_text

        if clipboard_text:
            if copied_ok:
                set_status("已从剪贴板读取内容，完成转换，并把结果复制回剪贴板。", "success")
            else:
                set_status("转换已完成，但剪贴板写入校验失败。请先使用右侧文本框手动复制结果。", "warning")
        else:
            set_status("剪贴板为空，已清空左右两栏。", "warning")

    except RuntimeError as exc:
        set_status(str(exc), "error")

elif convert_clicked:
    run_conversion(st.session_state.raw_text_input)
    set_status("已完成转换。", "success")

if st.session_state.status_message:
    if st.session_state.status_kind == "success":
        st.success(st.session_state.status_message)
    elif st.session_state.status_kind == "warning":
        st.warning(st.session_state.status_message)
    elif st.session_state.status_kind == "error":
        st.error(st.session_state.status_message)
    else:
        st.info(st.session_state.status_message)


# -----------------------------
# 左右两栏
# -----------------------------

left_col, right_col = st.columns(2, gap="large")

with left_col:
    st.subheader("原始文本")

    raw_text = st.text_area(
        label="在这里粘贴从网页版 ChatGPT 复制出来的内容",
        height=650,
        key="raw_text_input",
        label_visibility="collapsed",
    )

with right_col:
    st.subheader("转换结果")

    st.text_area(
        label="转换后的 Markdown + LaTeX 文本",
        height=650,
        key="converted_text_area",
        label_visibility="collapsed",
    )

st.session_state.raw_text = raw_text
st.session_state.converted_text = st.session_state.converted_text_area


# -----------------------------
# 下载按钮与报告
# -----------------------------

st.divider()

download_col1, download_col2, _ = st.columns([1.5, 1.5, 5])

with download_col1:
    st.download_button(
        label="下载转换结果 .md",
        data=st.session_state.converted_text,
        file_name="chatgpt_latex_cleaned.md",
        mime="text/markdown",
        use_container_width=True,
        disabled=not bool(st.session_state.converted_text),
    )

with download_col2:
    st.download_button(
        label="下载转换报告 .txt",
        data=st.session_state.report_text,
        file_name="conversion_report.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not bool(st.session_state.report_text),
    )

if show_report and st.session_state.report_text:
    st.subheader("转换报告")
    st.code(st.session_state.report_text, language="text")
