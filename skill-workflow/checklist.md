# 发版前自检清单（逐项过，全绿再发）

## 结构
- [ ] SKILL.md ≤150 行，只含 What/When/路由，不含流程细节
- [ ] frontmatter：name/version/platforms/prerequisites/aliases(中文触发词)/description 含 "Use when"
- [ ] 四层分离：SKILL.md / references / templates / scripts，无跨界内容
- [ ] 所有用户参数来自 config.json，代码与提示词模板中无硬编码

## 安全
- [ ] 有外发能力的脚本只到"草稿"，无群发/发布函数
- [ ] 凭证读取只从 ~/.config/，日志与台账中无凭证回显
- [ ] 外部写操作带归属参数（folder_id 等）
- [ ] 质检规则含一票否决项，规则以 JSON 落盘

## 可靠性
- [ ] 每步产物落盘且主控 Read 验证，不信子代理口头回报
- [ ] _status.json 断点续跑，重跑不覆盖已验证产物
- [ ] 每个外部依赖有降级路径且简报会标注降级
- [ ] 子代理失败补 spawn ≤1 次，QA 打回 ≤2 次（防循环）
- [ ] 日期用 date 实测

## 体验
- [ ] setup_wizard.py 一条命令完成配置，diagnose.py 一条命令排障
- [ ] SKILL.md 故障速查表覆盖已知错误码（40164 等）
- [ ] 台账初始化模板随技能分发，首跑即建
- [ ] check_drift.sh 通过

## 文档
- [ ] README 一页讲清价值与快速开始
- [ ] SETUP.md 面向小白，含凭证获取截图路径级指引
- [ ] API 踩坑结论（静默 no-op/不存在端点）已写入 references/*-mechanics.md
