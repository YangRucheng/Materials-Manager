# AGENTS.md — 面向 AI 编程智能体的项目约定

本文档约束在 `Materials-Manager`（电气车间备件管理系统）仓库内工作的 AI 编程智能体。
与 `README.md`（面向人类开发者）互补，此处聚焦「如何改代码、如何提交、如何上线」。

## 项目概况

- 前端：Vue 3 + TypeScript + Vite + Naive UI + Pinia，位于 `frontend/`。
- 后端：Go + Gin（GORM），位于 `server/`。
- 小程序：微信小程序，位于 `miniprogram/`。
- 前后端契约统一维护在 `docs/openapi.yaml`，前端类型由它生成（`src/api/generated.raw.ts`、`src/api/generated.ts`），**禁止手改生成文件**。
- 部署：Docker Compose（后端 + nginx 托管前端静态产物）。前端/后端镜像由 CI 在合并后构建。
- 默认工作目录：仓库根目录 `/workspace/备件管理系统`。

## 必读先做

动手改代码前，先阅读并遵守：

- `docs/openapi.yaml` — 接口契约；改后端接口时同步契约，并用 `pnpm generate:api`（frontend）重新生成前端类型。
- `docs/ui-design-guidelines.md` — UI 组件与样式约定。
- `docs/api-error-conventions.md` — 后端错误约定。
- `.github/workflows/` — CI 流水线（契约一致性校验 / 接口测试 / 构建镜像）。

## 验证命令（提交前必须通过）

在 `frontend/` 目录执行：

```bash
npx vue-tsc -b            # TypeScript 类型检查
npx eslint <改动的文件>    # 或 cd frontend && npm run lint（全量）
npm run test              # vitest 单测（如有涉及组件）
npm run build             # 类型检查 + 生产构建
```

后端在 `server/` 目录：`go test ./...`。
注意 CI 含「校验 openapi / generated.ts 未漂移」：契约源为 `docs/openapi.yaml`，改动后需同步 `server/internal/openapi/openapi.yaml`（跑 `TestOpenAPIContractDrift` 校验），并重新生成前端类型。

## 代码与提交规范

- **提交信息**：中文 + Conventional Commits 前缀（`feat` / `fix` / `style` / `chore` / `ci` / `docs` / `refactor` / `test`），一行简洁标题 + 空行 + 详细说明（可选列点）。
- **分功能点提交**：一个逻辑改动（一个功能/一个修复）对应一个 commit；不要把无关改动混进同一 commit。
- **分支命名**：`<type>/<kebab-case-描述>`，如 `fix/export-total-display`、`feat/share-link-columns`。
- **模板 vs JS 中 ref 的差异**：`<script setup>` 里从 composable 解构出的 `ref` 只在模板中自动解包；在 computed / 普通 JS / 模板字符串中必须写 `.value`（否则显示 `[object Object]`）。

## 标准开发与发布工作流（必须遵守）

> 目标：每个功能点独立成 PR，合并后不留残余分支。所有操作在仓库根目录执行。

### 1. 从最新 main 开功能分支

```bash
git checkout main && git pull
git checkout -b <type>/<描述>
```

### 2. 分功能点提交

```bash
git add <本次功能点涉及的文件>
git commit -m "type: 中文标题"
```

确认 `git status` 干净、无本功能点之外的改动。

### 3. 推送并创建 PR

```bash
git push -u origin <分支名>
gh pr create --title "type: 中文标题" --body "<问题/原因/改动/验证>"
```

PR 标题与 commit 标题一致（squash 后作为最终 commit 标题）。

### 4. 检查通过后才合并

- 本地验证通过（见「验证命令」）。
- `gh pr checks <编号> --watch` 等 CI 全部通过（含契约一致性校验、接口测试、构建镜像）。
- 自查 `gh pr diff <编号>` 确认改动只涉及本功能点。
- 通过后合并：本仓库只允许 squash：

```bash
gh pr merge <编号> --squash --delete-branch
```

`--delete-branch` 会同时删除本地和远端的功能分支。

### 5. 回到 main 并同步

```bash
git checkout main && git pull
```

### 6. 清理多余分支

- 合并后功能分支已由 `--delete-branch` 删除。
- 定期清理远端孤立/已关闭 PR 的分支：

```bash
git fetch --prune
gh pr list --state all   # 找出 CLOSED 且未合并的分支
git push origin --delete <多余分支名>
git branch -D <多余分支名>  # 如需删除本地对应分支
```

## 注意事项

- 不直接提交到 `main`：所有改动经功能分支 + PR 合并（squash）。
- 不修改 CI / 契约生成文件以外的受保护文件；生成文件（`generated.*`、`openapi.yaml` 派生内容）通过脚本再生成，不手改。
- PR 描述遵循「问题 / 原因 / 改动 / 验证」结构，便于 review 与回溯。
- 涉及接口或 Excel 模板变更时，同步更新 `docs/openapi.yaml` 与对应模板，并在 PR 描述中说明。
