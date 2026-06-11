# EasyReader 文档索引

更新时间：2026-06-11

## 推荐阅读顺序

1. `architecture.md`：系统边界、当前实现状态、阶段目标。
2. `client-server-contract.md`：当前 API 字段与行为契约。
3. `next-stage-execution-plan.md`：下一阶段执行步骤与验收标准。
4. `../e-link-client/docs/eink-client-plan.md`：墨水屏客户端专项方案。

## 维护规则

- 真实现状优先：未落地能力不得写成已完成。
- 契约先行：接口行为变更先更新契约文档再改代码。
- 阶段推进：新阶段任务先更新执行计划再进入实现。
- 多端一致：服务端、PWA、墨水屏端对同一字段含义必须一致。

## 当前文档职责

- `architecture.md`：回答系统是什么、边界是什么、当前到哪一步。
- `client-server-contract.md`：回答 API 现在到底怎么用、有什么限制。
- `next-stage-execution-plan.md`：回答下一步按什么顺序做、如何验收。

## 已清理的历史内容

本仓库已移除旧的 Claude 工作流与其遗留文档/脚本；后续开发以当前文档集和仓库内实现为准。