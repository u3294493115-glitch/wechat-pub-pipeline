# skill-workflow — 自动化 Skill 制作规则与经验

> 从 rsi-wechat-publisher（WorkBuddy 公众号流水线技能）等实战项目中沉淀的方法论。
> 用途：下次做任何"多步骤自动化技能"时，照此检查清单执行，少踩坑。

## 目录

| 文件 | 内容 | 何时读 |
|------|------|--------|
| [rules.md](rules.md) | 硬性规则（结构/安全/可靠性），违反必出事故 | 动手写技能**之前** |
| [recipes.md](recipes.md) | 实战经验与踩坑记录（按主题速查） | 写到对应环节时 |
| [checklist.md](checklist.md) | 发版前自检清单 | 发布**之前**逐项过 |

## 一句话总纲

**SKILL.md 只做路由，流程细节放 references/，可执行逻辑放 scripts/，个人配置只进 config.json——四层分离，永不互相污染。**
