# context-kb

**AI 会忘，它不会。**

一个本地、纯文本、平台无关的上下文知识库，专治长对话压缩后「AI 忘了，但你看不出来」。
原文永远留在磁盘上；发进 AI 上下文的永远是压缩版；AI 需要细节时，顺着索引回到具体某一行。

不需要服务器、不需要数据库、不需要 API key、不联网。只有 Markdown + JSONL + 一个零依赖的 Python 文件。

---

## 它解决什么问题

长对话会被压缩。AI 悄悄丢掉了中间的内容，**而你看不出来**——它照样自信地回答，只是不再知道细节。摘要会丢掉行号、丢掉原话、丢掉你已经找到的解法。下周遇到同一个 bug，再吵一遍。

context-kb 用三层结构解决：

| 层 | 装什么 | 进不进 AI 上下文 |
|---|---|---|
| **热层** `hot.md` | 用户偏好、铁律、一行一条的经验 | 每轮都进——必须小 |
| **索引层** `index.jsonl`、`symbols.jsonl` | 每个话题一句话结论，指到具体行 | 压缩后进 |
| **原文层** `session/`、`archive/` | 每一句原话，逐字保留 | 不进——AI 按需回查 |

> **原文只留一份，永远在库里；发给 AI 的永远是压缩过的；AI 需要细节时按索引回库里翻。**

---

## 快速开始（60 秒）

要求：Python 3.7+（已在 3.7.9 和 3.12 实测）。不需要 `pip install` 任何东西。

```bash
# 1. 在项目里初始化短期库
python scripts/kb.py init

# 2. 记录对话（命令会自动建这场对话的库）
python scripts/kb.py log "用户：为什么我改完没生效"
python scripts/kb.py log "AI：进程缓存了配置，要重启" --who AI

# 3. 一个话题聊完了 → 封段，然后建索引（指到具体行）
python scripts/kb.py seal
python scripts/kb.py index --gist "!配置文件改完要重启才生效" \
    --ref "S-20261020-001-p1" --lines "3-4" --summary "配置缓存问题"

# 4. 把下一轮该带的全部内容组装出来
python scripts/kb.py context

# 5. 整场聊完 → 并入长期库
python scripts/kb.py close
python scripts/kb.py merge
```

下次对话，AI 这样翻旧账：

```bash
python scripts/kb.py search "改完没生效"        # 搜短期库
python scripts/kb.py search "缓存" --long       # 搜长期库
python scripts/kb.py read archive/S-20261020-001-p1.md:3-4   # 读回那几行原文
```

这就是全部循环。

---

## 能得到什么

- **原文永远在**——每句话都留着，不会被摘要覆盖。
- **按话题封段**——话题结束时就封，不用等整场对话结束；一段 = 一条索引。
- **索引指到行**——每条都带 `ref:起-止`，AI 能引用原话，而不是猜。
- **前缀分组**——`$代码`、`!坑点`、`?疑问`、`*关键`，还能自定义；不用先想分类体系，条目自己成组。
- **两个库**——每场对话一个短期库（可多开并行），一个全局长期库（跨项目累积）。
- **坑点 / 偏好 / 铁律 / 工具经验**——四种熬过任何上下文窗口的知识。
- **候选区**——AI 提议，你拍板（`review` → `promote`）；没点头的东西进不了正式库。
- **体检**——`check` 查漏索引/摘要/解法，`gc` 查超期和重复坑点（只报告，从不删除）。

### 主要命令

| 命令 | 作用 |
|---|---|
| `init` / `init --long` | 建短期库 / 全局长期库 |
| `log "文字" [--who AI]` | 追加一条原文 |
| `seal` | 封存当前段，并提示怎么建索引 |
| `index --gist ... --ref ...` | 建一条索引，指到具体行 |
| `search <词> [--long] [--deep]` | 检索索引；`--deep` 下探原文 |
| `when <词>` / `read <段:行>` | 按时间检索 / 读回具体原文行 |
| `context` | 组装：热层 + 摘要 + 索引 + 最近消息 |
| `pitfall` / `pref` / `rule` / `growth` | 记坑点 / 偏好 / 铁律 / 工具经验 |
| `session` / `hot` | 列所有段 / 看热层 |
| `close` / `merge` | 结束本场 / 并入长期库 |
| `check` / `gc` / `stats` | 体检（默认只读） |
| `rm <键>` | 删除匹配的东西（先列清单，要 `--yes`） |

完整说明和设计思路见 **[SKILL.md](SKILL.md)**（这份文件同时是 AI 技能说明）。

---

## 配合 AI 使用

context-kb 的定位是一个 **skill**：AI 判断对话变长时加载这份说明，然后自己调用 CLI。

1. 把这个目录放到 agent 找技能的位置，例如：
   - Claude Code：`~/.claude/skills/context-kb/`
   - 其他 agent：把 `SKILL.md` 放进 system prompt 或项目规则
2. 在项目里能跑 `python scripts/kb.py`（拷进去，或用绝对路径调用）
3. AI 会自己初始化、记原文、封段、建索引，并在回答前组装 `context`

任何能执行 shell 命令的 agent 都能用——Claude Code、Codex、Cursor、Gemini CLI、自建的循环都行。

---

## 目录结构

```
.context-kb/                      # 短期库（一场对话一个）
├── talks/<对话id>/
│   ├── session/                  # 正在写的段
│   ├── archive/                  # 封存后的原文段
│   ├── hot.md                    # 热层：偏好、铁律、一行一条的经验
│   ├── talk.json                 # 这场对话的元数据
│   ├── index.jsonl               # 索引（C-…）
│   ├── summaries.jsonl           # 段级摘要
│   ├── digests.jsonl             # 会话级摘要
│   ├── pitfalls.jsonl            # 坑点（K-…）
│   ├── prefs.jsonl               # 偏好（P-…）
│   ├── candidates.jsonl          # 候选区（等用户确认）
│   └── growth.jsonl              # 工具经验
├── current                       # 当前是哪一场
└── symbols.jsonl                 # 前缀表（项目级共用）

~/.context-kb/                    # 全局长期库，结构相同
```

全是 UTF-8 文本。任何编辑器能看，`grep` 能搜，能进版本管理，能打包备份。

---

## 设计原则

1. **原文是唯一真相。** 索引是派生的，可以重建；原文层永远不删。
2. **为 AI 压缩，不为磁盘压缩。** 磁盘便宜，上下文不便宜。
3. **指路，而不是全量摘要。** 索引指到 `ref:起-止`，需要时读回原话。
4. **AI 提议，人拍板。** 新知识先落候选区，用户点头才进正式库和热层。
5. **默认只读。** `gc`、`rm` 先列清单；删除必须 `--yes`；不自动清理。
6. **没有魔法。** 不用向量库、不调模型、不需要 API——就是文本文件 + 确定性的 Python。

---

## 隐私

一切都在本地。工具**不联网**，**零依赖**。对话原文不会离开你的机器，除非你自己拷走。
把 `.context-kb/` 加进 `.gitignore`，它就不会被提交。

---

## 环境要求

- Python 3.7+（只用标准库；已在 3.7.9 和 3.12 实测）
- Windows / macOS / Linux
- Git（只在你想给知识库做版本管理时需要）

## 开发

```bash
python tests/smoke_test.py
```

冒烟测试会在临时目录里建隔离的库，跑完整流程（init → log → seal → index →
search/read/deep → pitfall/growth → context → check → close → merge），
**不会碰你真实的 `~/.context-kb`**。

CI 在 Linux / Windows / macOS 上都会跑：见
[`.github/workflows/smoke.yml`](.github/workflows/smoke.yml)。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
