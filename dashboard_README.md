# Personal Dashboard

一个自动更新、纯静态的个人仪表盘。

架构：**GitHub Actions 定时采集数据 → 生成 JSON → FTP 推送到虚拟主机 → 浏览器访问看到实时信息**

整个站点只有 HTML + CSS + JS + JSON，对 100MB 的静态主机毫无压力。

---

## 它展示什么

| 模块 | 数据来源 | 更新频率 |
|------|----------|----------|
| 实时时钟 & 问候 | 浏览器本地 | 每秒 |
| 重庆天气 | wttr.in（免费，无需 API Key） | 每天 9:00 |
| GitHub 仓库动态 | GitHub API | 每天 9:00 |
| arXiv 论文（你研究方向） | arXiv API（免费） | 每天 9:00 |
| 每日一句 | 内置引文库（按天数轮换） | 每天 |
| 今日鸟类 | 内置重庆常见鸟种列表（按天数轮换） | 每天 |

---

## 部署到你自己的虚拟主机

### 1. 创建 GitHub 仓库

把整个 `personal-dashboard/` 目录推到你 GitHub 上的一个新仓库（公开或私有均可）。

### 2. 在仓库里设置 Secrets

去 GitHub 仓库 Settings → Secrets and variables → Actions，添加以下 secrets：

| Secret | 说明 | 示例 |
|--------|------|------|
| `FTP_HOST` | FTP 服务器地址 | `ftp.yourhost.com` |
| `FTP_USERNAME` | FTP 用户名 | `u123456` |
| `FTP_PASSWORD` | FTP 密码 | `your-password` |
| `FTP_TARGET_DIR` | 目标路径 | `/public_html` 或 `/www` 或 `/` |

### 3. （可选）配置 GitHub 用户名

在同一个页面的 **Variables** 中，添加：

| Variable | 说明 | 默认值 |
|----------|------|--------|
| `GH_USER` | 你的 GitHub 用户名 | `Jacken-Wu` |

### 4. 手动触发一次

去 Actions 页面，找到 **Update Dashboard** 工作流，点 **Run workflow** → 选分支 → 绿色按钮。

第一次运行后，访问你的虚拟主机域名，应该就能看到仪表盘了。

### 5. 等着它自动更新

以后每天北京时间 9:00，GitHub Actions 会自动采集新数据并推送到你的主机。你也可以随时手动触发、或者每次推代码时自动更新。

---

## 本地预览

如果你在本地想先看看效果，可以手动运行数据采集脚本：

```bash
# Mac / Linux
python3 scripts/fetch-data.py

# Windows
python scripts/fetch-data.py
```

然后用任意静态服务器预览：

```bash
# Python 自带
cd site && python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

---

## 定制指南

### 修改 arXiv 搜索关键词

编辑 `scripts/fetch-data.py` 里 `fetch_arxiv()` 函数的 `queries` 列表，改成你关注的研究方向关键词。

### 修改每日引文库

编辑同一文件里 `fetch_daily()` 函数的 `quotes` 列表。格式：`("引文", "作者")`。

### 修改每日鸟类

编辑 `fetch_daily()` 函数的 `birds` 列表，换成你所在地区能见到的鸟种。

### 修改更新频率

编辑 `.github/workflows/deploy.yml` 里 schedule 的 cron 表达式。当前是 `0 1 * * *`（每天北京时间 9:00）。

### 修改外观

直接改 `site/style.css`，主题变量都在 `:root` 里，改动主题色很直观。

---

## 文件结构

```
personal-dashboard/
├── .github/workflows/deploy.yml     # GitHub Actions 工作流
├── scripts/
│   └── fetch-data.py                # 数据采集脚本
├── site/
│   ├── index.html                   # 仪表盘页面
│   ├── style.css                    # 样式
│   ├── app.js                       # 前端逻辑
│   └── data/                        # 生成的 JSON 文件（gitignore）
├── .gitignore
└── README.md
```

---

## 为什么这样设计

- **纯静态**：虚拟主机只存文件，零后端开销，100MB 用不完
- **GitHub Actions 做"大脑"**：Python 脚本在 CI 环境运行，可以调用任何 API、处理任何数据格式
- **FTP 推送**：不要求主机支持 SSH/Node/PHP，20 块钱的主机也毫无压力
- **前端只读 JSON**：页面启动时加载本机 JSON 文件，没有运行时后端依赖

---

## License

MIT
