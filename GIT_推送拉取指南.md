# GIT 推送拉取指南

> 本仓库远程地址：**https://github.com/bruceleeu-creator/He-Tongchaifen.git**
> 适用：首次把本项目推送到 GitHub、日常提交推送、以及其他电脑拉取继续开发。

---

## 一、重要前提（先读）

1. **本项目的运行数据不会进 Git**。`.gitignore` 已排除以下内容，推送前无需手动清理：
   - `runs/`、`uploads/`、`exports/`、`parsed/`（客户合同、运行结果等敏感资料）
   - `.ai_config.json`、`.env`（真实 API Key，绝不提交）
   - `app/node_modules/`、`api/venv/`、`app/dist/`、`__pycache__/`
2. **换电脑后这些内容需要手工处理**：API Key 在新电脑重新配置（见 `README.md` 部署指南）；历史运行数据如需迁移需手工拷贝 `runs/` 等目录。
3. **注意**：如果在家目录曾误执行过 `git init`（`git status` 出现整个用户目录的文件），不要在家目录直接操作。以下所有命令都在**项目根目录**（`Xiangmu-Chaifen-main/` 或 `He-Tongchaifen/`）内执行；在项目目录内 `git init` 会建立独立仓库，与外层互不影响。

---

## 二、首次推送（本机已有项目 → 推到 GitHub）

### 第 1 步：确认在项目根目录

```bash
cd /path/to/He-Tongchaifen   # 替换为你的项目路径
pwd                          # 确认当前目录
```

### 第 2 步：初始化仓库（项目内没有 .git 时）

```bash
git init
git branch -M main
```

> 若 `git init` 提示 `Reinitialized existing Git repository` 说明已有仓库，直接下一步。
> 若该仓库以前配置过别的远程地址（可用 `git remote -v` 查看），先移除：
> ```bash
> git remote remove origin
> ```

### 第 3 步：关联 GitHub 远程仓库

```bash
git remote add origin https://github.com/bruceleeu-creator/He-Tongchaifen.git
git remote -v   # 确认 origin 指向正确地址
```

### 第 4 步：检查将要提交的内容

```bash
git status
```

确认列表里**没有** `runs/`、`uploads/`、`.ai_config.json`、`.env`、`node_modules/`（已被 .gitignore 排除）。若出现，说明 `.gitignore` 缺失或文件已被跟踪，处理后（`git rm --cached <文件>`）再继续。

### 第 5 步：提交并推送

```bash
git add .
git commit -m "init: 合同拆分工作台（FastAPI + React）"
git push -u origin main
```

`-u` 会记住本地 main 与远程的对应关系，之后推送只需 `git push`。

---

## 三、GitHub 认证（HTTPS 推送被要求输入密码时）

GitHub 已不支持账号密码推送，HTTPS 方式需要任选其一：

**方式 A：Personal Access Token（PAT）—— 输入密码时填它**

1. 打开 https://github.com/settings/tokens → **Generate new token (classic)**
2. 勾选 `repo` 权限，生成后**立即复制**（只显示一次）
3. 推送时用户名填 GitHub 用户名，密码填该 Token
4. macOS 可让钥匙串记住：`git config --global credential.helper osxkeychain`

**方式 B：GitHub CLI（推荐，一次登录永久有效）**

```bash
brew install gh        # 未安装 gh 时
gh auth login          # 按提示选 GitHub.com → HTTPS → 浏览器登录
```

**方式 C：改用 SSH**

```bash
ssh-keygen -t ed25519 -C "你的邮箱"
cat ~/.ssh/id_ed25519.pub   # 复制内容到 GitHub → Settings → SSH Keys
git remote set-url origin git@github.com:bruceleeu-creator/He-Tongchaifen.git
ssh -T git@github.com       # 出现 "Hi bruceleeu-creator!" 即成功
```

---

## 四、日常开发：提交与推送

每次改完代码，在项目根目录执行：

```bash
git status                 # 看改了什么
git add .                  # 暂存全部改动（也可 git add <文件> 精确暂存）
git commit -m "说明这次改了什么"
git push                   # 推送到 GitHub
```

提交信息建议（中文即可，说清做了什么）：

| 场景 | 示例 |
|------|------|
| 新功能 | `feat: 任务表新增批量导入` |
| 修复 | `fix: 修正上传类型推断警告文案` |
| 文档 | `docs: 更新部署指南端口说明` |
| 其他 | `chore: 升级 vite 依赖` |

---

## 五、其他电脑拉取继续开发

### 场景 A：新电脑首次获取项目

```bash
git clone https://github.com/bruceleeu-creator/He-Tongchaifen.git
cd He-Tongchaifen
```

然后按 `README.md` 部署指南安装依赖、配置 `.ai_config.json`。

### 场景 B：已有本地仓库，同步最新代码

```bash
git pull                      # = git fetch + git merge
```

### 场景 C：两台电脑交替开发（推荐节奏）

```bash
# 开始工作前：先拉最新
git pull

# 结束工作后：提交并推送
git add .
git commit -m "..."
git push
```

---

## 六、常见问题排查

| 报错/现象 | 原因与处理 |
|-----------|-----------|
| `rejected - fetch first` / `non-fast-forward` | 远程有你本地没有的提交。先 `git pull` 合并（有冲突就解决后提交），再 `git push` |
| `merge conflict in <文件>` | 同一处被两边修改。打开冲突文件处理 `<<<<<<< ======= >>>>>>>` 标记 → `git add <文件>` → `git commit` → `git push` |
| `Authentication failed` / 403 | HTTPS 密码不能填账号密码，需 PAT / gh 登录 / SSH，见第三节 |
| `Permission denied (publickey)` | SSH 未配置或密钥未加到 GitHub，见第三节方式 C |
| 提示 LF/CRLF 警告 `warning: LF will be replaced by CRLF` | Windows 与 macOS 换行符差异，仅警告可忽略；想关闭：`git config --global core.autocrlf input`（macOS） |
| 误把敏感文件提交了 | 若未推送：`git rm --cached .ai_config.json && git commit -m "移除敏感文件"`；若已推送：立即作废该 Key 并考虑 `git filter-repo` 清理历史 |
| `git status` 显示项目外的家目录文件 | 你在家目录执行了 git 命令。`cd` 到项目根目录再操作；项目内已 `git init` 的话互不影响 |
| 推送大文件失败 | 检查是否误提交了 `node_modules`、运行数据或导出包；单文件超 100MB 需移除（GitHub 硬限制） |

---

## 七、速查卡

```bash
# 首次推送
git init && git branch -M main
git remote add origin https://github.com/bruceleeu-creator/He-Tongchaifen.git
git add . && git commit -m "init: 合同拆分工作台"
git push -u origin main

# 日常
git pull                 # 开工先拉
git add . && git commit -m "..." && git push    # 收工再推

# 新电脑
git clone https://github.com/bruceleeu-creator/He-Tongchaifen.git
```
