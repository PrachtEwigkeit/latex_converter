#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ChatGPT 网页复制文本公式清洗脚本

功能：
1. 把单独一行的 [ ... ] 块公式转成 $$ ... $$。
2. 把疑似行内公式的 (...) 转成 $...$。
3. 保护代码块、行内代码、Markdown 链接、引用链接，避免误处理。
4. 修复部分 ChatGPT 复制时造成的公式损坏，例如：
   {q_i}*{i=1}^N  ->  {q_i}_{i=1}^N
   \\mathcal M*{y^*} -> \\mathcal M_{y^*}
5. 输出转换报告，方便人工检查。
"""

import argparse
import base64
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Stats:
    protected: Dict[str, int] = field(default_factory=dict)
    display_math_blocks: int = 0
    inline_math: int = 0
    low_confidence_inline: List[Tuple[str, str, float, str]] = field(default_factory=list)
    subscript_repairs: int = 0
    display_math_line_repairs: int = 0
    math_text_repairs: int = 0
    math_row_break_repairs: int = 0
    skipped_unclosed_display_blocks: int = 0

    def add_protected(self, kind: str) -> None:
        self.protected[kind] = self.protected.get(kind, 0) + 1


class PlaceholderManager:
    """
    用占位符临时保护不该被处理的区域。
    """

    def __init__(self, stats: Stats):
        self.stats = stats
        self.items: List[Tuple[str, str]] = []

    def add(self, text: str, kind: str) -> str:
        key = f"@@__CGPT_LATEX_{kind}_{len(self.items)}__@@"
        self.items.append((key, text))
        self.stats.add_protected(kind)
        return key

    def protect_regex(self, text: str, pattern: str, kind: str, flags: int = 0) -> str:
        regex = re.compile(pattern, flags)

        def repl(m: re.Match) -> str:
            return self.add(m.group(0), kind)

        return regex.sub(repl, text)

    def restore(self, text: str) -> str:
        for key, value in reversed(self.items):
            text = text.replace(key, value)
        return text


@dataclass
class MathDecision:
    ok: bool
    confidence: float = 0.0
    reason: str = ""


def normalize_text(text: str) -> str:
    """
    统一换行和行尾空格。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text


def protect_sensitive_regions(
    text: str,
    ph: PlaceholderManager,
    do_repair: bool = True,
) -> str:
    """
    保护不应该被公式转换器处理的区域：
    - fenced code block
    - 已存在的 LaTeX display/inline math
    - 行内代码
    - Markdown 引用链接定义
    - Markdown 链接
    - Markdown 引用链接
    - 原始 URL
    """

    # 代码块：```...``` 或 ~~~...~~~
    text = ph.protect_regex(
        text,
        r"(?ms)^([ \t]*(```|~~~)[^\n]*\n.*?\n[ \t]*\2[ \t]*)$",
        "CODE_BLOCK",
    )

    # 已经存在的 display math
    display_math_regex = re.compile(r"(?s)\$\$.*?\$\$")

    def protect_display_math(m: re.Match) -> str:
        block = m.group(0)
        if do_repair:
            inner = block[2:-2]
            inner = repair_copied_display_math_lines(inner, ph.stats)
            before_syntax_repair = inner
            inner = repair_latex_syntax(inner, ph.stats)
            if inner != before_syntax_repair:
                ph.stats.subscript_repairs += 1
            block = f"$${inner}$$"
        return ph.add(block, "EXISTING_DISPLAY_MATH")

    text = display_math_regex.sub(protect_display_math, text)

    # 已经存在的 inline math，避免匹配 $$
    inline_math_regex = re.compile(
        r"(?<!\$)\$(?!\$)(?:\\.|[^$\n])+(?<!\$)\$(?!\$)"
    )

    def protect_inline_math(m: re.Match) -> str:
        block = m.group(0)
        if do_repair:
            inner = block[1:-1]
            before_syntax_repair = inner
            inner = repair_latex_syntax(inner, ph.stats)
            if inner != before_syntax_repair:
                ph.stats.subscript_repairs += 1
            block = f"${inner}$"
        return ph.add(block, "EXISTING_INLINE_MATH")

    text = inline_math_regex.sub(
        protect_inline_math,
        text,
    )

    # 行内代码：`...`
    text = ph.protect_regex(
        text,
        r"`[^`\n]*`",
        "INLINE_CODE",
    )

    # Markdown 引用链接定义：[1]: https://...
    text = ph.protect_regex(
        text,
        r"(?m)^[ \t]*\[[^\]\n]+\]:[ \t]+\S.*$",
        "MD_REF_DEF",
    )

    # Markdown 行内链接：[text](url), ![alt](url)
    text = ph.protect_regex(
        text,
        r"!?\[[^\]\n]*\]\([^\)\n]*\)",
        "MD_INLINE_LINK",
    )

    # Markdown 引用链接：[arXiv][1]
    text = ph.protect_regex(
        text,
        r"\[[^\]\n]+\]\[[^\]\n]*\]",
        "MD_REF_LINK",
    )

    # 原始 URL
    text = ph.protect_regex(
        text,
        r"https?://[^\s<>()]+(?:\([^\s<>()]*\)[^\s<>()]*)*",
        "RAW_URL",
    )

    return text


def convert_display_math_blocks(text: str, stats: Stats, do_repair: bool = True) -> str:
    """
    把 ChatGPT 复制出来的：

    [
    formula
    ]

    转为：

    $$
    formula
    $$
    """

    lines = text.split("\n")
    out: List[str] = []

    i = 0

    while i < len(lines):
        if lines[i].strip() == "[":
            j = i + 1
            block: List[str] = []

            while j < len(lines) and lines[j].strip() != "]":
                block.append(lines[j])
                j += 1

            if j < len(lines) and lines[j].strip() == "]":
                content = "\n".join(block).strip("\n")

                if do_repair:
                    content = repair_copied_display_math_lines(content, stats)
                    content = repair_formula(content, stats)

                out.append("$$")
                out.extend(content.split("\n"))
                out.append("$$")

                stats.display_math_blocks += 1
                i = j + 1
                continue

            # 没找到闭合 ]，就原样保留
            if j >= len(lines):
                stats.skipped_unclosed_display_blocks += 1

        out.append(lines[i])
        i += 1

    return "\n".join(out)


def protect_display_math_after_conversion(text: str, ph: PlaceholderManager) -> str:
    """
    转换完 display math 后，保护 $$...$$。
    否则后续行内括号扫描器会把块公式内部的 (q)、(T^*) 等也处理一遍。
    """
    return ph.protect_regex(
        text,
        r"(?s)\$\$.*?\$\$",
        "GENERATED_DISPLAY_MATH",
    )


def decide_math_like(content: str, allow_single_letter: bool = True) -> MathDecision:
    """
    判断括号 (...) 内部是否像行内公式。
    """

    s = content.strip()

    if not s:
        return MathDecision(False, reason="empty")

    if "\n" in s:
        return MathDecision(False, reason="multiline")

    if "@@__CGPT_LATEX_" in s:
        return MathDecision(False, reason="placeholder")

    if "$" in s:
        return MathDecision(False, reason="already_math")

    if len(s) > 180 and "\\" not in s:
        return MathDecision(False, reason="too_long")

    if re.search(r"https?://|www\.|[\w.-]+@[\w.-]+", s):
        return MathDecision(False, reason="url_or_email")

    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return MathDecision(False, reason="plain_number")

    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", s))

    # 强特征 1：LaTeX 命令
    if "\\" in s:
        return MathDecision(True, 0.98, "latex_command")

    if "[" in s or "]" in s:
        return MathDecision(False, reason="markdown_link_like")

    # 强特征 2：数学符号、关系符号、上下标
    if any(ch in s for ch in "=<>^_∈∉⊂⊆≈≠≤≥→←↦±×·∂∑∫∞"):
        return MathDecision(True, 0.92, "math_symbol")

    # 含中文且没有强数学特征，一般不是公式
    if has_chinese:
        return MathDecision(False, reason="chinese_without_math_symbol")

    # 常见数学/机器人学对象或函数
    if re.search(r"\b(?:Null|Rank|dim|log|sin|cos|tan|exp|FK|IK)\s*\(", s):
        return MathDecision(True, 0.88, "known_function_call")

    # 一般函数调用：f(q), J(q_i), T(q)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\s*\(.+\)", s):
        return MathDecision(True, 0.80, "function_call")

    # 形如 J^#, q_i, y^*, T_ee
    if re.fullmatch(r"[A-Za-z](?:[A-Za-z0-9]*)?(?:[_^][A-Za-z0-9*#{}\\]+)+", s):
        return MathDecision(True, 0.86, "subscript_or_superscript")

    # 空间写法：SE3, SO3, R3
    if re.fullmatch(r"(?:SE|SO|R|N|Z|Q)\d+", s):
        return MathDecision(True, 0.70, "math_space_short")

    # 单字母变量：q, y, M, T, J, v, e...
    # 这是最容易误伤的规则，所以置信度较低。
    # 可以用 --strict 关闭。
    if allow_single_letter and re.fullmatch(r"[A-Za-z]", s):
        return MathDecision(True, 0.55, "single_letter_variable")

    # 少量希腊字母英文名，如果复制时没有反斜杠
    if re.fullmatch(r"(?:phi|theta|alpha|beta|gamma|lambda|epsilon|Delta)", s):
        return MathDecision(True, 0.65, "greek_name")

    return MathDecision(False, reason="not_math_like")


def find_matching_paren(text: str, start: int) -> int:
    """
    start 指向 '('。
    返回匹配 ')' 的 index。
    找不到则返回 -1。
    支持嵌套括号。
    """

    depth = 0

    for i in range(start, len(text)):
        ch = text[i]

        if ch == "(":
            depth += 1

        elif ch == ")":
            depth -= 1

            if depth == 0:
                return i

    return -1


def convert_inline_math_parentheses(
    text: str,
    stats: Stats,
    allow_single_letter: bool = True,
    do_repair: bool = True,
) -> str:
    """
    把形如：

    (f(q)=y)
    (q_i)
    (\\mathcal M_{y^*})

    转成：

    $f(q)=y$
    $q_i$
    $\\mathcal M_{y^*}$
    """

    out: List[str] = []

    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch == "(":
            end = find_matching_paren(text, i)

            if end != -1:
                content = text[i + 1 : end]
                decision = decide_math_like(
                    content,
                    allow_single_letter=allow_single_letter,
                )

                if decision.ok:
                    formula = content.strip()

                    if do_repair:
                        formula = repair_formula(formula, stats)

                    out.append(f"${formula}$")

                    stats.inline_math += 1

                    if decision.confidence < 0.70:
                        stats.low_confidence_inline.append(
                            (content, formula, decision.confidence, decision.reason)
                        )

                    i = end + 1
                    continue

        out.append(ch)
        i += 1

    return "".join(out)


def repair_formula(formula: str, stats: Stats) -> str:
    """
    只对已经识别出的公式内容做修复。

    主要修复 ChatGPT 复制时把下标 _ 复制成 * 的情况。
    """

    before = formula

    # {q_i}*{i=1}^N  ->  {q_i}_{i=1}^N
    formula = re.sub(
        r"\}\s*\*\s*\{",
        r"}_{",
        formula,
    )

    # \mathcal M*{y^*} -> \mathcal M_{y^*}
    # M*{y^*}          -> M_{y^*}
    formula = re.sub(
        r"(\\mathcal\s*\{?[A-Za-z]\}?|\\[A-Za-z]+|[A-Za-z])\s*\*\s*\{",
        r"\1_{",
        formula,
    )

    # J(q)^# -> J(q)^{\#}
    # KaTeX/LaTeX treats a raw # as a special character, so escape it.
    formula = repair_latex_syntax(formula, stats)

    # 清理多余空格
    formula = re.sub(r"[ \t]+", " ", formula).strip()

    if formula != before:
        stats.subscript_repairs += 1

    return formula


def repair_latex_syntax(formula: str, stats: Optional[Stats] = None) -> str:
    """
    修复常见的 KaTeX/LaTeX 语法错误。
    """

    formula, row_break_repairs = repair_multiline_math_row_breaks(formula)
    if stats is not None and row_break_repairs:
        stats.math_row_break_repairs += row_break_repairs

    formula, text_font_repairs = repair_nested_text_font_commands(formula)
    if stats is not None and text_font_repairs:
        stats.math_text_repairs += text_font_repairs

    formula, text_repairs = repair_math_text_segments(formula)
    if stats is not None and text_repairs:
        stats.math_text_repairs += text_repairs

    formula = re.sub(r"\^\s*#", r"^{\\#}", formula)
    formula = re.sub(r"(?<!\\)#", r"\\#", formula)

    # \left{ ... \right} -> \left\{ ... \right\}
    # 同时兼容 \bigl{、\bigr} 等可伸缩定界符命令。
    sized_delimiter = re.compile(
        r"\\(left|right|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr|big|Big|bigg|Bigg)\s*([{}])"
    )
    formula = sized_delimiter.sub(
        lambda match: f"\\{match.group(1)}\\{match.group(2)}",
        formula,
    )

    return formula


MULTILINE_MATH_ENVIRONMENT_RE = re.compile(
    r"\\begin\{(?P<env>"
    r"array|aligned|alignedat|gathered|split|cases|"
    r"matrix|pmatrix|bmatrix|Bmatrix|vmatrix|Vmatrix|smallmatrix"
    r")\}(?P<body>.*?)\\end\{(?P=env)\}",
    re.DOTALL,
)

TEXT_FONT_WRAPPER_RE = re.compile(r"\\(?P<cmd>textbf)\s*\{")

MATRIX_LIKE_ENVIRONMENTS = {
    "matrix",
    "pmatrix",
    "bmatrix",
    "Bmatrix",
    "vmatrix",
    "Vmatrix",
    "smallmatrix",
}

COMPACT_MATRIX_ROW_SEPARATOR_RE = re.compile(
    r"(?m)(?<=[A-Za-z0-9}_\]\)])\\[ \t]*(?=[A-Za-z](?=[_^])|\d)"
)


def repair_multiline_math_row_breaks(formula: str) -> Tuple[str, int]:
    r"""
    修复多行数学环境中被复制成单个反斜杠的行分隔符。

    只处理行尾、表格横线命令前或紧凑矩阵行之间的单个 ``\``。
    正确的 ``\\`` 和 ``\hline`` 等命令不受影响。
    """

    total_repairs = 0

    def repair_environment(match: re.Match) -> str:
        nonlocal total_repairs

        body = match.group("body")
        repaired_body, repairs_before_rule = re.subn(
            r"(?m)(?<!\\)\\(?=[ \t]*\\(?:hline|cline|toprule|midrule|bottomrule|cmidrule)\b)",
            r"\\\\",
            body,
        )
        repairs_compact_matrix = 0
        if match.group("env") in MATRIX_LIKE_ENVIRONMENTS:
            repaired_body, repairs_compact_matrix = COMPACT_MATRIX_ROW_SEPARATOR_RE.subn(
                lambda _match: "\\\\\n",
                repaired_body,
            )
        repaired_body, repairs_at_line_end = re.subn(
            r"(?m)(?<!\\)\\(?=[ \t]*(?:\n|\Z))",
            r"\\\\",
            repaired_body,
        )
        total_repairs += (
            repairs_before_rule + repairs_compact_matrix + repairs_at_line_end
        )

        return (
            rf"\begin{{{match.group('env')}}}"
            f"{repaired_body}"
            rf"\end{{{match.group('env')}}}"
        )

    repaired_formula = MULTILINE_MATH_ENVIRONMENT_RE.sub(
        repair_environment,
        formula,
    )
    return repaired_formula, total_repairs


def repair_nested_text_font_commands(formula: str) -> Tuple[str, int]:
    r"""
    修复 ``\textbf{\text{...}Word \text{...}}`` 这类混合文本。

    在数学环境里，纯文本优先整理成 ``\text{\textbf{...}}``。如果原内容
    跨多行，就使用 ``gathered`` 保留换行，避免在 ``\boxed`` 内出现裸换行文本。
    """

    out: List[str] = []
    repairs = 0
    i = 0

    while i < len(formula):
        match = TEXT_FONT_WRAPPER_RE.match(formula, i)

        if match:
            open_index = match.end() - 1
            close_index = find_matching_brace(formula, open_index)

            if close_index != -1:
                body = formula[open_index + 1 : close_index]
                flattened, text_chunks = flatten_text_command_body(body)

                if flattened is not None and text_chunks > 0:
                    out.append(format_text_font_replacement(match.group("cmd"), flattened))
                    repairs += 1
                    i = close_index + 1
                    continue

        out.append(formula[i])
        i += 1

    return "".join(out), repairs


def flatten_text_command_body(body: str) -> Tuple[Optional[str], int]:
    r"""
    展开文本字体命令内部的 ``\text{...}``。

    只允许 ``\text{...}`` 之间夹普通文本词和标点；遇到 ``_``、``^``、
    其他 LaTeX 命令等数学内容时放弃修复，避免把真实公式误压成文本。
    """

    out: List[str] = []
    text_chunks = 0
    i = 0

    while i < len(body):
        if body.startswith(r"\text{", i):
            close_index = find_matching_brace(body, i + len(r"\text"))
            if close_index == -1:
                return None, 0

            out.append(body[i + len(r"\text{") : close_index])
            text_chunks += 1
            i = close_index + 1
            continue

        ch = body[i]

        if ch == "\\" or ch in "_^&={}":
            return None, 0

        out.append(ch)
        i += 1

    return "".join(out), text_chunks


def format_text_font_replacement(command: str, text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    if not lines:
        return rf"\{command}{{}}"

    rows = [rf"\text{{\{command}{{{line}}}}}" for line in lines]

    if len(rows) == 1:
        return rows[0]

    return "\\begin{gathered}\n" + "\\\\\n".join(rows) + "\n\\end{gathered}"


def find_matching_brace(text: str, open_index: int) -> int:
    depth = 0

    for i in range(open_index, len(text)):
        ch = text[i]

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

            if depth == 0:
                return i

    return -1


def is_cjk_text_char(ch: str) -> bool:
    return (
        "\u4e00" <= ch <= "\u9fff"
        or ch in "，。！？、；：（）《》“”‘’…"
    )


def has_cjk_letter(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def should_consume_stray_text_brace(formula: str, brace_index: int, segment: str) -> bool:
    if not has_cjk_letter(segment):
        return False

    j = brace_index + 1
    while j < len(formula) and formula[j] in " \t":
        j += 1

    if j >= len(formula) or formula[j] in "\r\n}]":
        return False

    return formula[j].isalnum() or formula[j] in r"\({["


def repair_math_text_segments(formula: str) -> Tuple[str, int]:
    r"""
    修复数学模式中裸露的中文文本段。

    ChatGPT 网页复制有时会把：

        \text{幅度平方函数给的是 }H(s)H(-s)，不是直接给 }H(s)。

    复制成不合法的 LaTeX。这里把裸露中文重新包回 \text{...}，
    并只在后面紧跟数学项时吞掉那个多余的文本闭合括号。
    """

    out: List[str] = []
    repairs = 0
    i = 0

    while i < len(formula):
        if formula.startswith(r"\text{", i):
            close_index = find_matching_brace(formula, i + len(r"\text"))
            if close_index != -1:
                out.append(formula[i : close_index + 1])
                i = close_index + 1
                continue

        ch = formula[i]

        if is_cjk_text_char(ch):
            start = i
            i += 1

            while i < len(formula) and (
                is_cjk_text_char(formula[i]) or formula[i] in " \t"
            ):
                i += 1

            segment = formula[start:i]

            if i < len(formula) and formula[i] == "}" and should_consume_stray_text_brace(
                formula,
                i,
                segment,
            ):
                i += 1

            out.append(r"\text{" + segment + "}")
            repairs += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out), repairs


def operator_from_copied_rule_line(line: str) -> Optional[str]:
    stripped = line.strip()

    if len(stripped) < 3:
        return None

    if set(stripped) == {"="}:
        return "="

    if set(stripped) == {"-"}:
        return "-"

    return None


def repair_copied_display_math_lines(content: str, stats: Stats) -> str:
    r"""
    修复 ChatGPT 网页复制公式时出现的 Markdown setext 标题伪影，例如：

        \dot{\xi}
        =========

        # \hat f(\xi)

        \sum ...

    还原为：

        \dot{\xi} = \hat f(\xi) = \sum ...
    """

    lines = content.split("\n")
    out: List[str] = []
    repairs = 0
    carry_operator: Optional[str] = None

    i = 0

    def previous_non_empty_index() -> Optional[int]:
        for idx in range(len(out) - 1, -1, -1):
            if out[idx].strip():
                return idx
        return None

    while i < len(lines):
        line = lines[i]
        operator = operator_from_copied_rule_line(line)

        if operator:
            prev_idx = previous_non_empty_index()
            next_idx = i + 1

            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1

            if prev_idx is not None and next_idx < len(lines):
                next_term = lines[next_idx].strip()
                had_hash_prefix = next_term.startswith("#")

                if had_hash_prefix:
                    next_term = re.sub(r"^#+\s*", "", next_term).strip()

                while len(out) - 1 > prev_idx:
                    out.pop()

                out[prev_idx] = f"{out[prev_idx].rstrip()} {operator} {next_term}"
                repairs += 1
                carry_operator = operator if had_hash_prefix else None
                i = next_idx + 1
                continue

        if carry_operator and not line.strip():
            i += 1
            continue

        if carry_operator and line.strip():
            out[-1] = f"{out[-1].rstrip()} {carry_operator} {line.strip()}"
            repairs += 1
            carry_operator = None
            i += 1
            continue

        out.append(line)
        i += 1

    if repairs:
        stats.display_math_line_repairs += repairs

    return "\n".join(out)


def format_report(stats: Stats, max_low_confidence: int = 30) -> str:
    """
    生成转换报告。
    """

    lines = []

    lines.append("转换报告")
    lines.append("-" * 40)
    lines.append(f"块公式转换：{stats.display_math_blocks}")
    lines.append(f"行内公式转换：{stats.inline_math}")
    lines.append(f"公式内部修复：{stats.subscript_repairs}")
    lines.append(f"公式换行伪影修复：{stats.display_math_line_repairs}")
    lines.append(f"公式中文文本修复：{stats.math_text_repairs}")
    lines.append(f"多行公式行分隔符修复：{stats.math_row_break_repairs}")
    lines.append(f"未闭合块公式跳过：{stats.skipped_unclosed_display_blocks}")

    if stats.protected:
        lines.append("")
        lines.append("保护区域：")
        for k, v in sorted(stats.protected.items()):
            lines.append(f"- {k}: {v}")

    if stats.low_confidence_inline:
        lines.append("")
        lines.append("低置信度行内公式转换，请人工快速检查：")

        for idx, (src, dst, conf, reason) in enumerate(
            stats.low_confidence_inline[:max_low_confidence],
            1,
        ):
            lines.append(
                f"{idx}. ({src}) -> ${dst}$  confidence={conf:.2f}, reason={reason}"
            )

        remaining = len(stats.low_confidence_inline) - max_low_confidence
        if remaining > 0:
            lines.append(f"... 还有 {remaining} 条未显示")

    return "\n".join(lines)


def convert_text(
    text: str,
    allow_single_letter: bool = True,
    do_repair: bool = True,
) -> Tuple[str, Stats]:
    """
    总转换入口。
    """

    stats = Stats()
    ph = PlaceholderManager(stats)

    text = normalize_text(text)

    # 1. 保护代码、链接、已存在公式
    text = protect_sensitive_regions(text, ph, do_repair=do_repair)

    # 2. 转换块公式
    text = convert_display_math_blocks(
        text,
        stats,
        do_repair=do_repair,
    )

    # 3. 保护刚生成的 $$...$$，防止行内公式处理器误伤块公式内部
    text = protect_display_math_after_conversion(text, ph)

    # 4. 转换行内公式
    text = convert_inline_math_parentheses(
        text,
        stats,
        allow_single_letter=allow_single_letter,
        do_repair=do_repair,
    )

    # 5. 恢复被保护的区域
    text = ph.restore(text)

    return text, stats


def read_clipboard() -> str:
    """
    从剪贴板读取。
    优先使用 pyperclip；未安装时使用 tkinter 标准库兜底。
    """

    if sys.platform.startswith("win"):
        try:
            return _read_clipboard_windows()
        except RuntimeError:
            pass

    try:
        import pyperclip  # type: ignore
    except ImportError:
        pyperclip = None

    if pyperclip is not None:
        try:
            return pyperclip.paste()
        except Exception:
            pass

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.update()

        try:
            return root.clipboard_get()
        except tk.TclError:
            return ""
        finally:
            root.destroy()
    except Exception as e:
        raise RuntimeError(
            "无法读取剪贴板：请安装 pyperclip，或确认当前环境可以访问系统剪贴板。"
        ) from e


def write_clipboard(text: str) -> None:
    """
    写入剪贴板。
    优先使用 pyperclip；未安装时使用 tkinter 标准库兜底。
    """

    if sys.platform.startswith("win"):
        try:
            _write_clipboard_windows(text)
            return
        except RuntimeError:
            pass

    try:
        import pyperclip  # type: ignore
    except ImportError:
        pyperclip = None

    if pyperclip is not None:
        try:
            pyperclip.copy(text)
            return
        except Exception:
            pass

    try:
        import tkinter as tk

        root = tk.Tk()
        try:
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        finally:
            root.destroy()
    except Exception as e:
        raise RuntimeError(
            "无法写入剪贴板：请安装 pyperclip，或确认当前环境可以访问系统剪贴板。"
        ) from e


def _run_powershell(script: str, stdin: str = "") -> str:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    last_error = "PowerShell 不可用"

    for executable in ("powershell.exe", "pwsh.exe"):
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)
            continue

        if completed.returncode == 0:
            return completed.stdout

        last_error = completed.stderr.strip() or completed.stdout.strip()

    raise RuntimeError(last_error)


def _read_clipboard_windows() -> str:
    script = """
$ErrorActionPreference = 'Stop'
$text = Get-Clipboard -Raw
if ($null -eq $text) { $text = '' }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($text))
"""
    output = _run_powershell(script).strip()

    if not output:
        return ""

    try:
        return base64.b64decode(output).decode("utf-8")
    except Exception as e:
        raise RuntimeError("无法解析剪贴板内容") from e


def _write_clipboard_windows(text: str) -> None:
    script = """
$ErrorActionPreference = 'Stop'
$b64 = [Console]::In.ReadToEnd()
$text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
Set-Clipboard -Value $text
"""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    _run_powershell(script, stdin=encoded)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="把网页版 ChatGPT 复制出的半损坏公式文本转换为 Markdown + LaTeX。"
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="输入文本文件。省略时从 stdin 读取；配合 --from-clipboard 时从剪贴板读取。",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="输出 markdown 文件。省略时输出到 stdout。",
    )

    parser.add_argument(
        "--from-clipboard",
        action="store_true",
        help="从剪贴板读取输入。",
    )

    parser.add_argument(
        "--to-clipboard",
        action="store_true",
        help="把转换结果写回剪贴板。",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：不自动把 (q)、(M)、(y) 这类单字母括号转成公式。",
    )

    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="不修复公式内部疑似损坏的下标，例如 }*{ -> }_{。",
    )

    parser.add_argument(
        "--no-report",
        action="store_true",
        help="不在 stderr 输出转换报告。",
    )

    args = parser.parse_args()

    if args.from_clipboard:
        raw = read_clipboard()
    elif args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    converted, stats = convert_text(
        raw,
        allow_single_letter=not args.strict,
        do_repair=not args.no_repair,
    )

    if args.output:
        Path(args.output).write_text(converted, encoding="utf-8")
    else:
        print(converted)

    if args.to_clipboard:
        write_clipboard(converted)

    if not args.no_report:
        print("", file=sys.stderr)
        print(format_report(stats), file=sys.stderr)


if __name__ == "__main__":
    main()
