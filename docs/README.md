# EasyReader 文档索引

更新时间：2026-06-11

## 推荐阅读顺序

1. `architecture.md`：整体架构、服务端架构、PWA 架构和共享 API 约束。
2. `phase1.md`：当前已完成部署、已完成功能和下一步方案。
3. `../e-link-client/docs/eink-client-plan.md`：墨水屏客户端架构。

## 维护规则

- 真实现状优先：未落地能力不得写成已完成。
- 契约先行：接口行为变更先更新 `architecture.md` 再改代码。
- 阶段推进：Phase1 状态或下一步方案变化先更新 `phase1.md`。
- 多端一致：服务端、PWA、墨水屏端对同一字段含义必须一致。
- 客户端专项架构变更先更新 `../e-link-client/docs/eink-client-plan.md`。

## 当前文档职责

- `architecture.md`：回答系统是什么、服务端和 PWA 怎么分层、共享 API 有什么约束。
- `phase1.md`：回答当前已经完成了什么、下一步做什么、如何验收。
- `../e-link-client/docs/eink-client-plan.md`：回答墨水屏客户端怎么分层、怎么运行、边界是什么。
- `client-server-contract.md` 与 `next-stage-execution-plan.md`：仅保留为旧路径迁移说明。

## 已清理的历史内容

本仓库已移除旧的 Claude 工作流与其遗留文档/脚本；后续开发以当前文档集和仓库内实现为准。