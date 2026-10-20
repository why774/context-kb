# A two-minute demo

This is what using context-kb looks like from the AI's side. The user never
types any of these commands — the AI runs them.

## 1. The user asks something; the AI starts recording

```
$ python scripts/kb.py init
[ OK ] 已初始化 .context-kb/

$ python scripts/kb.py log "用户：为什么我改了配置文件，程序还是旧行为"
$ python scripts/kb.py log "AI：进程启动时把配置读进内存了，改文件不会热加载，要重启" --who AI
[ OK ] 已记录（当前段 T-20261020-001-p1）
```

## 2. The topic ends; seal the segment

```
$ python scripts/kb.py seal
[ OK ] T-20261020-001 第 1 段已封存（2 条原文）
       下一步：给这一段写索引
         python scripts/kb.py index --gist "!改完配置要重启" --ref "T-20261020-001-p1" --lines "1-2"
```

## 3. Index it — point at the exact lines

```
$ python scripts/kb.py index --gist "!配置文件改完要重启才生效" \
      --ref "T-20261020-001-p1" --lines "2" --summary "配置缓存问题"
[ OK ] 索引 C-20261020-001 已记录 -> archive/T-20261020-001-p1.md:2
```

## 4. Next turn: ask for everything that should go into context

```
$ python scripts/kb.py context
== 热层 ==
  （用户偏好 / 铁律 / 一行经验）

== 很近 · 原文（最近 10 条消息） ==
--- T-20261020-001-p1 ---
- [用户] 为什么我改了配置文件，程序还是旧行为
- [AI] 进程启动时把配置读进内存了……

== 比较远 · 索引 ==
  [C-20261020-001] 配置文件改完要重启才生效   -> T-20261020-001-p1

粗估 180 token（汉字按 1 算，偏保守）
```

The AI now has the gist plus a pointer. If it needs the exact wording it runs
`read T-20261020-001-p1:2` — it never has to guess.

## 5. Two weeks later, in another project

The user hits the same kind of bug again.

```
$ python scripts/kb.py search "改完没生效" --long
[ ! ] 坑点 · K-001
   [K-001] 配置缓存
      症状：改完文件没生效
      解法：重启进程
   (踩过 3 次)

看某处前后文：python scripts/kb.py read archive/T-20261020-001-p1.md:2
```

The answer that was almost lost is one search away.
