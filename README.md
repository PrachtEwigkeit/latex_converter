# ChatGPT LaTeX Cleaner

把网页版 ChatGPT 复制出来的文本清洗成更适合 Markdown + LaTeX 的格式。本工程按系统拆成两个平级版本目录：

- `ubuntu_version/`：Ubuntu 版，包含 Bash 安装和启动脚本
- `windows_version/`：Windows 版，包含 `.bat` 一键启动脚本

两个版本的核心功能一致，主要区别在启动方式、Python 环境管理和系统剪贴板读写。

## 主要功能

适合处理 ChatGPT 网页端复制时常见的公式格式问题：

- 单独一行的 `[` / `]` 包围块公式转换为 `$$...$$`
- 疑似行内公式的 `(f(q)=y)` 转换为 `$f(q)=y$`
- 修复部分下标损坏，例如 `{q_i}*{i=1}^N` 转为 `{q_i}_{i=1}^N`
- 修复 KaTeX 不接受的未转义 `^#`，例如 `J(q)^#` 转为 `J(q)^{\#}`
- 修复集合定界符，例如 `\left{...\right}` 转为 `\left\{...\right\}`
- 保护代码块、行内代码、Markdown 链接，避免误转换

## 目录结构

```text
.
├── README.md
├── ubuntu_version/
│   ├── app.py                    # Streamlit 图形界面
│   ├── chatgpt_latex_cleaner.py  # 核心转换逻辑和命令行入口
│   ├── requirements.txt          # Ubuntu 版 Python 依赖
│   ├── install_ubuntu.sh         # 创建 .venv 并安装依赖
│   └── start_latex_cleaner.sh    # Ubuntu 一键启动脚本
└── windows_version/
    ├── app.py                    # Streamlit 图形界面
    ├── chatgpt_latex_cleaner.py  # 核心转换逻辑和命令行入口
    ├── requirements.txt          # Windows 版 Python 依赖
    └── start_latex_cleaner.bat   # Windows 一键启动脚本
```

## Ubuntu 快速开始

### 环境要求

- Ubuntu 20.04 或更高版本
- Python 3.8 或更高版本
- 推荐使用 `ubuntu_version/.venv`

安装基础 Python 环境：

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

剪贴板支持按桌面环境选择安装：

```bash
# Wayland 桌面常用
sudo apt install wl-clipboard

# X11 桌面常用
sudo apt install xclip xsel
```

如果不确定当前是 Wayland 还是 X11，把 `wl-clipboard xclip xsel` 都装上也可以。

### 安装和启动

```bash
cd ubuntu_version
chmod +x install_ubuntu.sh start_latex_cleaner.sh
./install_ubuntu.sh
./start_latex_cleaner.sh
```

只检查环境、不启动服务：

```bash
./start_latex_cleaner.sh --dry-run
```

如果还没安装依赖，也可以让启动脚本顺手安装：

```bash
./start_latex_cleaner.sh --install
```

指定端口起点或不自动打开浏览器：

```bash
./start_latex_cleaner.sh --port 8600
./start_latex_cleaner.sh --no-browser
```

手动启动：

```bash
source .venv/bin/activate
python -m streamlit run app.py --server.headless true
```

## Windows 快速开始

### 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- 推荐使用 Anaconda 或普通 Python 虚拟环境

### 安装和启动

```bat
cd windows_version
python -m pip install -r requirements.txt
start_latex_cleaner.bat
```

如果使用 Anaconda，可以先创建独立环境：

```bat
conda create -n latex-cleaner python=3.12
conda activate latex-cleaner
python -m pip install -r requirements.txt
start_latex_cleaner.bat
```

只检查环境、不启动服务：

```bat
start_latex_cleaner.bat --dry-run
```

手动启动：

```bat
python -m streamlit run app.py
```

## 图形界面用法

启动后浏览器会打开本地网页，默认地址通常是：

```text
http://localhost:8501
```

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

先进入对应系统目录：

```bash
cd ubuntu_version
```

或：

```bat
cd windows_version
```

从文件转换：

```bash
python chatgpt_latex_cleaner.py input.txt -o output.md
```

从标准输入转换，Ubuntu：

```bash
cat input.txt | python chatgpt_latex_cleaner.py > output.md
```

从标准输入转换，Windows：

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

- Ubuntu 版会依次尝试 `wl-paste` / `wl-copy`、`xclip`、`xsel`、`pyperclip`、`tkinter`
- Windows 版优先使用系统自带的 PowerShell `Get-Clipboard` 和 `Set-Clipboard`

如果一键使用没有写回剪贴板，页面会显示警告。此时可以先使用右侧文本框手动复制结果，或改用命令行文件输入输出。

## 常见问题

### Ubuntu 提示 Streamlit 未安装

进入 Ubuntu 版本目录后运行：

```bash
./install_ubuntu.sh
```

或：

```bash
./start_latex_cleaner.sh --install
```

### Ubuntu 提示 venv 模块不可用

安装系统包：

```bash
sudo apt install python3-venv
```

然后重新运行 `./install_ubuntu.sh`。

### Ubuntu 一键使用无法读写剪贴板

先确认桌面协议：

```bash
echo "$XDG_SESSION_TYPE"
```

Wayland 安装：

```bash
sudo apt install wl-clipboard
```

X11 安装：

```bash
sudo apt install xclip xsel
```

### Windows 双击 bat 后打开的不是最新页面

可能是旧的 Streamlit 服务仍在运行。关闭旧的命令行窗口，或者重新双击 `start_latex_cleaner.bat`。脚本会自动选择一个可用端口。

### Windows 安装依赖失败

确认当前终端使用的是你想要的 Python：

```bat
where python
python --version
```

然后重新安装：

```bat
python -m pip install -r requirements.txt
```
