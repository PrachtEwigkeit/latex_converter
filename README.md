# ChatGPT LaTeX Cleaner

把网页版 ChatGPT 复制出来的文本清洗成更适合 Markdown + LaTeX 的格式。

这个工具适合处理 ChatGPT 网页端复制时常见的公式格式问题，例如：

- 单独一行的 `[` / `]` 包围块公式转换为 `$$...$$`
- 疑似行内公式的 `(f(q)=y)` 转换为 `$f(q)=y$`
- 修复部分下标损坏，例如 `{q_i}*{i=1}^N` 转为 `{q_i}_{i=1}^N`
- 保护代码块、行内代码、Markdown 链接，避免误转换

## 文件说明

```text
.
├── app.py                    # Streamlit 图形界面
├── chatgpt_latex_cleaner.py  # 核心转换逻辑和命令行入口
├── requirements.txt          # Python 依赖
└── start_latex_cleaner.bat   # Windows 一键启动脚本
```

## 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- 推荐使用 Anaconda 或普通 Python 虚拟环境

## 安装

进入项目目录：

```bat
cd C:\Users\Sterben\Documents\VScode\latex_converter
```

安装依赖：

```bat
python -m pip install -r requirements.txt
```

如果你使用 Anaconda，也可以先创建独立环境：

```bat
conda create -n latex-cleaner python=3.12
conda activate latex-cleaner
python -m pip install -r requirements.txt
```

## Windows 一键启动

直接双击：

```text
start_latex_cleaner.bat
```

脚本会自动：

1. 切换到当前项目目录
2. 寻找可用的 Python
3. 检查是否已安装 Streamlit
4. 自动选择可用端口
5. 启动网页界面
6. 打开浏览器

关闭启动脚本的命令行窗口即可停止程序。

如果想只检查环境、不启动服务，可以运行：

```bat
start_latex_cleaner.bat --dry-run
```

## 手动启动

也可以在终端中运行：

```bat
python -m streamlit run app.py
```

启动后浏览器会打开本地网页。默认地址通常是：

```text
http://localhost:8501
```

## 图形界面用法

页面分为左右两栏：

- 左栏：原始文本
- 右栏：转换后的 Markdown + LaTeX 文本

常用按钮：

- `一键使用`：读取剪贴板内容，填入左栏，自动转换，并把右栏结果写回剪贴板
- `转换`：只转换左栏当前内容，不自动写回剪贴板
- `清空`：清空左右两栏

侧边栏设置：

- `严格模式`：关闭单字母变量的自动公式转换，减少误伤
- `修复公式内部损坏`：修复常见下标损坏
- `显示转换报告`：显示转换统计和低置信度提示

## 命令行用法

从文件转换：

```bat
python chatgpt_latex_cleaner.py input.txt -o output.md
```

从标准输入转换：

```bat
type input.txt | python chatgpt_latex_cleaner.py > output.md
```

从剪贴板读取并写回剪贴板：

```bat
python chatgpt_latex_cleaner.py --from-clipboard --to-clipboard
```

常用参数：

```text
--strict        严格模式，不自动转换 (q)、(M)、(y) 这类单字母括号
--no-repair     不修复公式内部疑似损坏的下标
--no-report     不输出转换报告
```

## 剪贴板说明

Windows 下剪贴板读写优先使用系统自带的 PowerShell `Get-Clipboard` 和 `Set-Clipboard`，不需要额外安装 `pyperclip`。

如果一键使用没有写回剪贴板，页面会显示警告。此时可以先使用右侧文本框手动复制结果，并检查是否有多个旧的 Streamlit 服务占用了不同端口。

## 常见问题

### 双击 bat 后打开的不是最新页面

可能是旧的 Streamlit 服务仍在运行。关闭旧的命令行窗口，或者重新双击 `start_latex_cleaner.bat`。脚本会自动选择一个可用端口。

### VS Code Git 面板显示了用户目录的更改

如果 `latex_converter` 目录里没有 `.git`，但父目录 `C:\Users\Sterben` 下有 `.git`，VS Code 会把整个用户目录识别成仓库。

解决方式是在项目目录初始化自己的仓库：

```bat
git init
```

或者确认 `C:\Users\Sterben\.git` 是误创建后，将其移除或改名备份。

### 安装依赖失败

确认当前终端使用的是你想要的 Python：

```bat
where python
python --version
```

然后重新安装：

```bat
python -m pip install -r requirements.txt
```
