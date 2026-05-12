# Task Breakdown — CEX Listing Research Dashboard (MVP)

## Phase 1: 环境准备 ✅

- [x] 1.1 创建 `requirements.txt`
- [x] 1.2 安装依赖
- [x] 1.3 确认 Python 3.11 ✓

---

## Phase 2: 数据库模块（database.py）✅

- [x] 2.1 `init_db()`：建表 + 唯一索引
- [x] 2.2 `insert_listing()`：插入 / 跳过重复
- [x] 2.3 `get_all(filters)`：筛选查询，返回 DataFrame
- [x] 2.4 `get_stats()`：总数 + 各交易所统计

---

## Phase 3: 爬虫模块（scraper.py）✅

- [x] 3.1 配置请求 headers（User-Agent、Referer 等模拟浏览器）
- [x] 3.2 实现 `fetch_page(url)`：retry 3 次，遇到 429/403 停止
- [x] 3.3 实现 `parse_page(html)`：只保留 "Listed on" 类型，过滤 "trading pair"
- [x] 3.4 实现 `scrape_all(test_mode=False)`：两个停止条件，test_mode 限 3 页
- [x] 3.5 测试模式验证通过（3 页 / 25 条 / 日期格式正确）
- [x] 3.6 正式运行完成：69 页，共入库 802 条，止于 2025-12-31

---

## Phase 4: Dashboard 模块（dashboard.py）✅

- [x] 4.1 基础框架：页面标题、wide mode、侧边栏筛选器（交易所多选、日期范围）
- [x] 4.2 总览指标卡：总上币数 / 覆盖交易所数 / 本月新增数
- [x] 4.3 月度趋势折线图：各交易所每月新增上币数
- [x] 4.4 交易所对比柱状图：累计上币数横向排名
- [x] 4.5 多交易所上线 Token 表格：2 家以上 / 按覆盖数排序 / Top 50
- [x] 4.6 原始数据表格：全量展示，支持导出 CSV

---

## Phase 5: 联调测试

- [ ] 5.1 完整跑 `scraper.py`，确认数据入库
- [ ] 5.2 启动 dashboard，检查各图表
- [ ] 5.3 测试筛选器联动
- [ ] 5.4 测试 CSV 导出

---

## 执行顺序

```
Phase 1 ✅ → Phase 2 ✅ → Phase 3 → Phase 4 → Phase 5
```
