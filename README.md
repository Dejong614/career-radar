# Career Radar · 职位与技能观察站

交通工程 **Internship / Co-op**、保险公司研发（研究 / 数据科学 / 精算 / 风险与定价建模）和自动驾驶研究相关岗位。保险和自动驾驶默认包含全职与实习，可在页面选择「只看实习」。

**网站：** https://Dejong614.github.io/career-radar/

## 功能

- 七个美国都会区与周边：Seattle、Portland、Los Angeles、San Francisco Bay Area、Raleigh–Durham、New York、Washington DC。Remote 独立收录、默认隐藏。
- 搜索、城市、实习筛选、方向切换、发布日期/首次发现排序、分页及直达雇主申请页。
- 每方向 Top 5 / 10 技能、技能证据、跨方向共享技能与 Jaccard 共现排名。
- GitHub Actions 每 12 小时抓取；SQLite 记录职位发布日期（若公开）、首次/末次发现、方向、技能、来源及 URL。数据库不参与公开 Pages 部署；公开仓库内的数据库本身仍可下载。
- 无 API 密钥、无第三方前端依赖、无付费数据库。Python 标准库采集；浏览器端原生 JavaScript 分析。

## 部署

1. 将整个项目放入公开仓库 `career-radar` 的 `main` 分支。
2. Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。
3. Actions → **Collect jobs and publish** → **Run workflow**。首次源代码推送也会触发。
4. 成功后访问 GitHub Pages 地址。计划时间为 **UTC 00:17 / 12:17**（纽约冬令时前一天 19:17 / 当天 07:17，夏令时前一天 20:17 / 当天 08:17）。调度可能延迟。

如果通过网页首传 `career-radar-source.zip`，工作流首次会自动解包，将普通源码和数据提交到仓库并移除首传压缩包；之后就是正常源码仓库。压缩包不含工作流，工作流文件独立提交在 `.github/workflows/update.yml`。

公开仓库计划任务在 60 天没有仓库活动时可能暂停；本项目正常运行时的定时数据提交属于仓库活动。仍请留意 Actions 状态与网页来源状态。运行额度和平台政策以 GitHub 当前规则为准。

## 本地运行

需要 Python 3.10+；测试需要 Node.js 18+。

```sh
python scripts/collect.py
python -m http.server 8765
```

访问 http://localhost:8765 。也可以直接打开 `index.html`；内嵌真实快照支持离线查看，但应保留 `web/` 文件夹。在线页面每 5 分钟检查新 JSON，数据采集本身仍每 12 小时运行。

```sh
python -m unittest discover -s tests -p 'test_*.py'
node tests/analytics.test.js
node --check web/app.js
```

修改模板 `web/index.template.html` 后运行 `python scripts/collect.py --export-only` 重建首页。

## 数据口径与限制

- **不是全网职位索引。** 仅覆盖 `config/sources.json` 中的雇主。初始来源：Fehr & Peers、AECOM、Waymo、Zoox、Aurora、Nuro、Waabi、GEICO、At-Bay、Travelers。未接入 LinkedIn / Indeed，也不绕过登录、验证码或反爬措施。Root 与 Coalition 的旧接口已迁移，未将失效源作为有效覆盖。
- 交通只收录标题涉及交通/运输、并且职位名称或类型是实习/co-op 的岗位。保险包括研究/科学/精算/风险和定价建模；自动驾驶包括研究与机器学习，以及感知、预测、规划、仿真、机器人方向的工程职位。后者包含研究相邻工程岗位，标题规则可能产生漏检或误检。
- 采集源：Greenhouse、Lever、Ashby、SmartRecruiters 公开招聘接口以及 Workday 招聘站公开 JSON。雇主或接口变更会显示为失败，不保证覆盖连续。
- 原站发布日期不公开时为 `null`，页面显示「未公开」。`first_seen` 是本系统首次发现，不能当成发布时间。Greenhouse `updated_at` 单独保留；Lever `createdAt` 不用作发布日期；Ashby `publishedAt` 是最近一次发布时间（可能是重发）。Workday `startDate` 为原站提供的职位开始公开日期。
- 同一个来源的所有列表分页、所需详情均读取成功后才整批写入 SQLite。网络错误不移除旧岗位；连续两次成功抓取缺失才关闭。第一次缺失仍展示并标记待确认。
- 每条职位对同一技能只计一次；技能率分母为该方向筛选后全部职位（含未命中技能者）。搜索、城市、实习筛选更新所有分析；方向标签只筛选职位列表，保留三方向对比。
- 技能是规则匹配结果，不是人工确认的硬性要求。`level` 来自最近的资格/优先段落标题推断；证据保留短句，申请前核对原文。
- 跨方向技能先按覆盖方向数，再按各非空方向平均提及率（包含零值）排序。共现对必须至少 3 个职位同时提及，且出现在至少 2 个方向；按 `intersection / union` 排名。不是因果、岗位适配评分或统计显著性检验。
- 都会区是可读城市别名映射，未进行地理编码；保留原始地点文本，避免把都会区标记误作岗位实际办公地址。Remote 标签没有国家时，保留为 US employer board remote，须核对雇佣资格。
- 数据仅保留结构化字段和技能短证据，不保存完整 JD；关闭岗位在最后发现后 180 天清理。Git 历史仍保留旧版本，SQLite 是当前轻量账本，不是完整审计系统。
- 首页超过 36 小时未成功更新的来源会标记过期。JSON 拉取失败时保留内嵌快照，并提示状态。SQL 数据库通常几百 KB，规模随岗位数量变化。

## 扩展公司与技能

`config/sources.json` 中每个雇主配置唯一 `id`、`company`、`provider`、`board`、`track`、`homepage`；`track` 为 `traffic`、`insurance`、`av`。Workday 还需 `host`、`tenant`、`queries`。保险和自动驾驶来源可添加 `"intern_only": true`。配置变更会在下次工作流应用。

技能词典位于 `config/skills.json`；城市别名与职位标题规则位于 `scripts/collect.py`。原始数据在 `data/jobs.json`，账本在 `data/jobs.sqlite`。

## 官方接口参考

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board)
- [Lever Postings API](https://github.com/lever/postings-api)
- [Ashby public posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [SmartRecruiters public posting endpoints](https://developers.smartrecruiters.com/docs/endpoints)
- [GitHub Actions schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 文件

`scripts/collect.py` 采集/归一化/持久化/导出；`web/index.template.html` 模板；`web/analytics.js` 纯分析函数；`web/app.js` 页面交互；`.github/workflows/update.yml` 计划任务和发布。
