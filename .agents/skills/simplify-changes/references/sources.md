# 来源与本地适配

查阅日期：2026-10-23（Asia/Taipei）。本 skill 是结合下述公开工作流和本地实践写成的原创指令，没有复制上游整份内容或代码。热度只是选材线索，不代表效果验证。

## 公开来源

| 来源 | 当日可见热度 | 采纳 | 不采纳及原因 |
| --- | --- | --- | --- |
| [Anthropic 官方 code-simplifier agent 源文件](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md) | [仓库](https://github.com/anthropics/claude-plugins-official)页面显示 43.9k stars | 保持行为、围绕最近变更、可读性优先于压缩行数、保留有用抽象 | 它是 plugin 内的 agent，并非同格式 SKILL.md。不继承固定 JS/React 风格、模型选择或每次写代码后都主动改写的触发方式，避免扩大适用范围。 |
| [Sentry code-simplifier SKILL.md](https://github.com/getsentry/skills/blob/main/skills/code-simplifier/SKILL.md) | [skills.sh 单项](https://www.skills.sh/getsentry/skills/code-simplifier)显示 8.6K installs；[仓库](https://github.com/getsentry/skills)显示 1.1k stars | 面向明确化简请求、使用项目已有规范、清理没有贡献的转发抽象 | 不硬编码函数写法或将链式表达式一律展开；不把短小等同于低复杂度。这些选择依赖当前语言和上下文。 |

GitHub stars 是整个仓库的关注度，不是某个 skill 的使用量。skills.sh 的 installs 是其目录展示的安装指标，不代表独立用户数、活跃度或质量。以上数值是页面的四舍五入显示；上游 main 和安装量会变化。Sentry 与 Anthropic 的文本相近，不把它们当作两份独立的有效性实验。

## 本地实践如何改变设计

依据用户在 2026-10-23 提供的历史复盘，而非重新声称审阅全部会话：

- devcloud 会话 `01a13932-7891-7603-9a49-fcd27da77c00`（2026-10-14）：重复追问 logger 传递、回调绕回 adapter、冗余解析。转化为针对本次 diff 的复杂度检查，未推广成“所有参数或回调都要删除”。
- local 会话 `01a14b38-6f7a-7d10-9cfa-be39ca9e6dcd`（2026-10-18）：先证明废弃、修复真实 bug、保留有效覆盖。转化为删分支、兼容逻辑和测试前需要证据。
- local 会话 `01a13333-2dd7-7111-8d81-35cb01476efc`（2026-10-13）：同工作区有其他会话修改。转化为按任务和 hunk 识别范围，不重置或吞并其他改动。

这些记录支持用户偏好，不能证明当前项目某段代码可删。实际执行仍须读当前代码、契约和支持版本。
