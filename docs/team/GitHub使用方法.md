# GitHub 使用方法

## 基本概念

- Git：本地版本控制工具，用于记录代码和文档变更。
- GitHub：远程代码托管平台，用于多人协作、Issue 管理和 Pull Request 审查。
- Repository：仓库，一个项目对应一个仓库。
- Commit：一次提交，记录一组修改。
- Branch：分支，用于隔离不同任务。
- Issue：问题或任务记录。
- Pull Request：合并请求，用于把分支修改合并到主分支。

## 常用命令

克隆仓库：

```bash
git clone 仓库地址
```

查看当前状态：

```bash
git status
```

创建并切换分支：

```bash
git switch -c 分支名
```

添加修改：

```bash
git add 文件路径
```

提交修改：

```bash
git commit -m "提交说明"
```

推送分支：

```bash
git push origin 分支名
```

拉取远程更新：

```bash
git pull
```

## 推荐协作流程

1. 从 GitHub 上查看或创建 Issue。
2. 根据 Issue 创建新分支，例如 `docs/course-summary` 或 `feat/simulated-node`。
3. 在本地完成修改。
4. 使用 `git status` 检查修改范围。
5. 使用 `git add` 和 `git commit` 提交。
6. 使用 `git push origin 分支名` 推送到 GitHub。
7. 在 GitHub 上创建 Pull Request。
8. 说明本次修改内容、测试结果和关联 Issue。
9. 经确认后合并到 `main` 分支。

## 提交信息规范

建议格式：

```text
类型: 简短说明
```

常用类型：

- `docs`：文档修改。
- `feat`：新增功能。
- `fix`：问题修复。
- `test`：测试相关。
- `refactor`：代码重构。
- `chore`：项目配置、目录结构、依赖等维护。

示例：

```text
docs: add mqtt knowledge summary
feat: add simulated temperature node
fix: handle broker reconnect failure
test: add qos delivery test records
chore: initialize project structure
```

## 冲突处理建议

出现冲突时不要慌，先确认冲突文件内容，再和相关成员沟通。

基本步骤：

1. 执行 `git status` 查看冲突文件。
2. 打开冲突文件，找到 `<<<<<<<`、`=======`、`>>>>>>>` 标记。
3. 保留正确内容，删除冲突标记。
4. 重新执行 `git add 冲突文件`。
5. 执行 `git commit` 或继续合并流程。

## 注意事项

- 不要直接把未确认的大量修改提交到 `main`。
- 每次提交尽量只解决一个问题。
- 提交前先运行能运行的测试或检查。
- 文档、代码、测试证据应和 Issue 或 PR 内容对应。
- 不要上传账号密码、Token、Wi-Fi 密码等敏感信息。

