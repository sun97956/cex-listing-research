# CEX Listing Research Dashboard — Requirements (MVP)

## 1. 项目目标

追踪主流中心化交易所（CEX）2026 年的新币上线情况，构建本地可视化 dashboard，用于投研参考。

---

## 2. 数据来源

**来源**：[listedon.org](https://listedon.org)

**爬取 URL**：
```
https://listedon.org/?page=N&sort=date&order=desc
```

**只抓取 `New listing` 类型**（首次上币），忽略 `New pair`（已有币新增交易对）。

**每条记录字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `listing_date` | 上币日期 | 2026-03-15 |
| `ticker` | 代币符号 | BTC |
| `exchange` | 交易所名称 | Binance |
| `trading_pair` | 交易对 | BTC/USDT |

---

## 3. 爬虫策略

### 运行模式

| 模式 | 说明 |
|------|------|
| 测试模式 | 只爬前 3 页，验证解析正确，不写入正式数据库 |
| 正式模式 | 首次全量爬取 2026 年所有数据 |
| 更新模式 | 日常增量，遇到停止条件自动终止 |

### 停止条件（满足任一即停止）

- **条件 1**：当前页出现 2025 年及以前的记录
- **条件 2**：连续遇到 10 条数据库已有记录（增量更新时提前终止）

### 反爬措施（由代码内部处理，无需手动配置）

- 每次请求随机 sleep 1-3 秒
- 模拟浏览器 headers（User-Agent、Referer 等）
- 失败自动 retry 最多 3 次，间隔递增（5s / 10s / 20s）
- 遇到 429 / 403 立即停止

---

## 4. 交易所范围

只保留以下 10 家主流交易所：

```
Binance, OKX, Bybit, Coinbase, Gate.io,
Bitget, KuCoin, MEXC, Kraken, Upbit
```

---

## 5. 数据存储

- SQLite 本地单文件，路径：项目目录下 `listings.db`
- 唯一索引防重复，重跑自动增量
- 全量数据存库，不做裁剪

---

## 6. 文件结构

```
listing-research/
├── scraper.py          # 爬取 listedon.org，写入 SQLite
├── database.py         # 数据库读写封装
├── dashboard.py        # Streamlit 可视化 dashboard
├── listings.db         # SQLite 本地数据库（运行后自动生成）
├── requirements.md     # 本文件
└── requirements.txt    # Python 依赖
```

---

## 7. Dashboard 设计

**技术栈**：Streamlit + Plotly + Pandas

**数据刷新**：手动重跑 `scraper.py` 后刷新浏览器页面即可（MVP 不做自动刷新）。

### 侧边栏筛选器
- 交易所多选（默认全选）
- 日期范围选择

### 主界面模块

| 模块 | 图表类型 | 说明 |
|------|---------|------|
| 总览指标 | 数字卡片 | 总上币数、覆盖交易所数、本月新增数 |
| 月度趋势 | 折线图 | 各交易所每月新增上币数量 |
| 交易所对比 | 横向柱状图 | 10 家交易所累计上币数排名 |
| 多交易所上线 Token | 表格 | 被 2 家及以上交易所同时上线的 token，按覆盖数排序，展示 Top 50 |
| 原始数据 | 可筛选表格 | 全量数据，支持导出 CSV |

---

## 8. 运行方式

```bash
# 首次全量爬取
python scraper.py

# 日常增量更新（重跑即可，自动跳过已有数据）
python scraper.py

# 启动 dashboard（浏览器打开 localhost:8501）
streamlit run dashboard.py
```

---

## 9. Python 依赖

```
requests
beautifulsoup4
streamlit
plotly
pandas
```
