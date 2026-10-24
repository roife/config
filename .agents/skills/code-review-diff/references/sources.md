# 来源与设计取舍

检索/核对日期：2026-10-23（Asia/Taipei）。这是一份结合本地使用记录重新编写的 skill，没有安装上游工作流，也没有复制上游正文。来源用于维护时追溯，不是日常执行依赖。

## 网络参考

### 热门相邻参考：obra/superpowers

- [仓库](https://github.com/obra/superpowers)：当日 GitHub 页面 Stars 区显示约 **303.9k stars**（顶部取整为 304k）。这是整个仓库的热度，不是某个 skill 的安装量或使用人数；GitHub API 当时返回限流，未声称获取精确计数。
- [receiving-code-review 源文件](https://github.com/obra/superpowers/blob/main/skills/receiving-code-review/SKILL.md)：采纳先理解反馈、结合实际代码核实、技术判断需要证据。没有继承其固定话术、遇到任意不清楚条目就全局停止、默认转入修改等流程。
- [requesting-code-review 源文件](https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md)：采纳明确 review 的代码范围、基线与需求。没有继承自动派发 reviewer、每个实现任务强制 review 或严重级别驱动修复等流程。
- 两者是接受反馈/发起自动审查的相邻参考，并不是逐段带用户读 diff 的现成方案。仓库标注 MIT；本地 skill 为原创流程，未复制模板。

### 教学风格补充：zeufack/coding-tutor

- [仓库](https://github.com/zeufack/coding-tutor)：当日 GitHub 页面显示 **8 stars**。相关但不热门，不能以此证明广泛采用。
- [reviewer 原始源文件](https://raw.githubusercontent.com/zeufack/coding-tutor/main/reviewer/skill.md)：参考具体定位问题并解释原因、教学时不默认替用户重写。没有采用强制表扬、固定严重性报告格式、强制要求用户回传修改稿。
- [explainer 原始源文件](https://raw.githubusercontent.com/zeufack/coding-tutor/main/explainer/skill.md)：参考从入口和数据流建立上下文、按理解程度调节深度。没有采用必问背景、必做类比或每段强制让用户复述。
- 这两个文件的名称是小写 `skill.md`；已读取维护者仓库原文。没有确认到与本地引导审阅完全一致且独立热度可验证的热门 skill，因此不声称直接复刻成熟的同类产品。

## 本地依据

依据本轮已有的 `outputs/agent-usage-review.md` 分析报告；没有把这份二手复盘当作本次重新检查所有原始会话。

- 2026-10-21 的引导 review 纠偏：用户要理解和审阅，反馈讲解跳跃，随后逐段解释、按已 review 范围暂存。
- 2026-10-20 的相似反馈：需要连续的局部背景和解释，不能跨过关键概念。
- 报告给出的锁与句柄案例：应解释资源身份、引用与释放责任，并读到清理实现后再判断；这是场景验证依据，不是对所有项目都适用的固定讲解内容。
- 本地需求进一步补充：区分讲解、用户判断和验证；保留进度锚点；已有暂存授权按原条件执行，不额外要求逐段认可。
