# -*- coding: utf-8 -*-
"""上下文知识库 · kb（入口薄壳）

代码按功能拆在同目录的 kbmod/ 里：
    base      底层：常量、路径、读写、匹配、坐标
    hot       初始化与热层
    topics    主题层：前缀切分、主题匹配、分组显示、词频
    search    检索：主题检索 / 时间检索 / 总检索 / 原文下探
    write     写入：坑点、偏好、索引、铁律、段与封存
    session   会话层：段列表、会话摘要、context 组装
    maintain  维护：删除、建议、候选区、清理、统计

本文件只负责文档与参数解析（main）。要改逻辑，去对应分区文件。

平台无关的本地知识库。数据就是项目根下的 .context-kb/ 目录，纯文本，任何编辑器都能看。

用法：
    python kb.py init                      在当前目录初始化

  短期层（原文，聊完一段就 seal，不用等整场对话结束）
    python kb.py log "用户说的话"           记一条原文
    python kb.py seal                     封存当前段，提示做归纳
    python kb.py close                    整场结束（封存最后一段）
    python kb.py session [id]             列出所有段 / 看某段原文

  会话层（对话很长时，把 N 段压成一段摘要）
    python kb.py digest                   列本场各段索引，让你去写摘要
    python kb.py digest --text "总结"      写入会话摘要

  出口（组装这一次该带进上下文的全部内容）
    python kb.py context [--recent 10]    热层 + 会话摘要 + 段索引 + 最近N条

  长期层①：坑点
    python kb.py pitfall --title "..." --symptom "..." --cause "..." --fix "..." --tags a,b

  长期层②：对话索引（任务结束后从原文归纳出来）
    python kb.py index --gist "结论一句话" --tags a,b --ref "C-20261019-001"

  热层（每次对话都带）
    python kb.py pref --text "..."                      用户偏好
    python kb.py rule --text "..."                      项目铁律（永久）
    python kb.py rule --text "..." --short              本次任务约束（临时）
    python kb.py hot                                    打印热层

  查询（三段式：线索词 → 索引 → 原文所在行）
    python kb.py search 关键词 [--deep]     搜索引；索引零命中会自动下探原文
    python kb.py read archive/x.md:47        按坐标读那一行前后文

  其它
    python kb.py review                    看候选区
    python kb.py promote K-003             候选转正
    python kb.py drop K-003                丢弃候选
    python kb.py rm S-...-p1 [--yes]       删除（不加 --yes 只列清单）
    python kb.py gc [--apply]              清理（超期 + 重复提示）
    python kb.py stats                     统计

设计原则：
  1. 编号永不复用、永不重排。存 meta.json 里递增。
  2. 坑点必须带 symptom（症状），否则检索命中率极低。
  3. AI 的提议先落 candidates.jsonl，人工 promote 才进正式库。
  4. 原文只在短期层，长期层只存路牌（索引），不复制原文。
  5. 只追加，不重写历史；冲突用 superseded_by 标记，不删。
  6. 命名规范只有一条：`主题[/子主题]：结论`。冒号前那段就是分组键。

代码分区（实现按功能拆在同目录 kbmod/，一个功能一个文件）：
  kb.py                入口薄壳：只放文档 + argparse（main）
  kbmod/base.py        底层    常量/路径/load/append/meta/next_id/hit/ref_to_path/日期解析
  kbmod/hot.py         热层    cmd_init / cmd_hot
  kbmod/topics.py      主题层  topic_of / match_topic / cmd_topic / keywords / 分组显示
  kbmod/search.py      检索    cmd_when（时间）/ cmd_search（主体）/ cmd_read / _scan_raw
  kbmod/write.py       写入    cmd_log / cmd_seal / cmd_close / cmd_index / 坑点 / 偏好 / 铁律
  kbmod/session.py     会话层  cmd_session / cmd_digest / cmd_context
  kbmod/maintain.py    维护    cmd_rm / cmd_suggest / 候选区 / cmd_gc / cmd_stats
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kbmod.hot import *# noqa: F401,F403
from kbmod.write import *      # noqa: F401,F403
from kbmod.session import *   # noqa: F401,F403
from kbmod.search import *    # noqa: F401,F403
from kbmod.topics import *    # noqa: F401,F403
from kbmod.maintain import *  # noqa: F401,F403
from kbmod.lib import *     # noqa: F401,F403
from kbmod.check import *   # noqa: F401,F403


# 这些命令会自动建库，不用先 init
AUTOINIT = ('log', 'pref', 'rule', 'pitfall', 'index', 'growth', 'symbol',
            'seal', 'check', 'merge')


def main():
    if (not os.path.isdir(KB) and (len(sys.argv) < 2
                                   or sys.argv[1] not in
                                   ('init', '-h', '--help') + AUTOINIT)):
        print('[ X ] 当前目录没有 .context-kb/，先跑：python scripts/kb.py init',
              file=sys.stderr)
        sys.exit(2)

    ap = argparse.ArgumentParser(description='上下文知识库')
    sub = ap.add_subparsers(dest='cmd')

    s = sub.add_parser('init')
    s.add_argument('--long', action='store_true',
                   help='建/操作长期库（全局唯一一个）')
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser('hot')
    s.add_argument('--long', action='store_true', help='看长期热层')
    s.set_defaults(fn=cmd_hot)

    s = sub.add_parser('search')
    s.add_argument('keyword', nargs='+', help='一个或多个词；多个词是交叉（AND）')
    s.add_argument('--deep', action='store_true', help='索引层有命中时也继续搜原文')
    s.add_argument('--limit', type=int, default=40, help='原文最多返回几处，默认 40')
    s.add_argument('--long', action='store_true', help='查长期库（跨所有对话）')
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser('when', help='时间检索：不按词，按日期翻')
    s.add_argument('keyword', nargs='*',
                   help='可选。加上就只翻这段时间里提到这些词的东西')
    s.add_argument('--day', help='精确某一天，如 2026-10-15')
    s.add_argument('--since', help='起始，如 2026 或 2026-10')
    s.add_argument('--until', help='结束，如 2026-12 或 2026-10-15')
    s.add_argument('--days', type=int, help='最近几天（含今天），如 --days 7')
    s.add_argument('--long', action='store_true', help='查长期库（跨所有对话）')
    s.set_defaults(fn=cmd_when)

    s = sub.add_parser('read')
    s.add_argument('loc', help='坐标，如 archive/S-20261019-001-p1.md:47')
    s.add_argument('--around', type=int, default=5, help='前后各看几行，默认 5')
    s.set_defaults(fn=cmd_read)

    s = sub.add_parser('pitfall')
    s.add_argument('--title', required=True)
    s.add_argument('--symptom', default='')
    s.add_argument('--cause', default='')
    s.add_argument('--fix', default='')
    s.add_argument('--tags', default='')
    s.add_argument('--files', default='')
    s.set_defaults(fn=cmd_pitfall)

    s = sub.add_parser('pref')
    s.add_argument('--text', required=True)
    s.add_argument('--tags', default='')
    s.set_defaults(fn=cmd_pref)

    s = sub.add_parser('index')
    s.add_argument('--gist', required=True)
    s.add_argument('--ref', required=True, help='段名，如 S-20261019-001-p1')
    s.add_argument('--topic', default='', help='主题键；不填则程序按词表从结论里自动认')
    s.add_argument('--lines', default='', help='段内行范围，如 5-12（精确到那一处）')
    s.add_argument('--subs', default='', help='段内小节，分号隔开："5-40 甲;41-80 乙;81-120 丙"（数量不限）')
    s.add_argument('--tags', default='')
    s.add_argument('--code', action='store_true',
                   help='这是代码类内容：挂「代码」前缀（中文结论前缀同时保留）')
    s.add_argument('--summary', default='',
                   help='这一段的一句话摘要（AI 写；「比较近」那档要用）')
    s.add_argument('--sym', default='',
                   help='符号前缀（类型标记），如 $ 代码 / ! 坑点；也可直接写在 gist 开头')
    s.set_defaults(fn=cmd_index)

    # 短期层
    s = sub.add_parser('log')
    s.add_argument('text')
    s.add_argument('--who', default='用户')
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser('seal')
    s.add_argument('--gist', default='', help='顺手写一条索引结论')
    s.set_defaults(fn=cmd_seal)

    sub.add_parser('close').set_defaults(fn=cmd_close)

    s = sub.add_parser('rule')
    s.add_argument('--text', required=True)
    s.add_argument('--short', action='store_true', help='本次任务内有效，不是永久铁律')
    s.set_defaults(fn=cmd_rule)

    s = sub.add_parser('session')
    s.add_argument('id', nargs='?', default='')
    s.set_defaults(fn=cmd_session)

    s = sub.add_parser('digest')
    s.add_argument('--text', default='', help='写入会话摘要；不带则输出材料让你去写')
    s.set_defaults(fn=cmd_digest)

    s = sub.add_parser('context', help='分级压缩：近的给原文，中间的给摘要，远的只留提示')
    s.add_argument('--raw-lines', type=int, default=60,
                   help='很近：最近几条消息给原文，默认 60')
    s.add_argument('--sum-segs', type=int, default=3,
                   help='比较近：再往前几段给摘要，默认 3')
    s.add_argument('--recent', type=int, default=10, help='当前段带最近几条原文，默认 10')
    s.add_argument('--digest', action='store_true', help='额外带上本场总摘要')
    s.add_argument('--raw', default='', help='只看内容，不要提示')
    s.set_defaults(fn=cmd_context)

    sub.add_parser('suggest').set_defaults(fn=cmd_suggest)

    sub.add_parser('keywords').set_defaults(fn=cmd_keywords)

    s = sub.add_parser('topic', help='看组：一个组 = 一个前缀符号')
    s.add_argument('--show', default='', help='展开某个组，看它下面挂了哪些索引')
    s.set_defaults(fn=cmd_topic)

    s = sub.add_parser('check', help='检查：这段有没有写索引')
    s.add_argument('--ref', default='', help='查指定的段，如 S-20261020-001-p1')
    s.add_argument('--long', action='store_true', help='查长期库')
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser('merge', help='把短期库并入长期库')
    s.set_defaults(fn=cmd_merge)

    s = sub.add_parser('unmerge', help='把当前项目从长期库踢出去')
    s.add_argument('--project', default='', help='项目名（默认用当前目录名）')
    s.set_defaults(fn=cmd_unmerge)

    s = sub.add_parser('libs', help='列出所有库：短期库（多开）+ 长期库（一个）')
    s.set_defaults(fn=cmd_libs)

    s = sub.add_parser('growth', help='工具/操作经验：记一句「这个工具怎么用才对」')
    s.add_argument('--text', default='', help='记一句；不带则看用法')
    s.add_argument('--list', action='store_true', help='看已有的经验')
    s.add_argument('--kind', default='', help='分类，如 工具 / 操作 / 坑')
    s.set_defaults(fn=cmd_growth)

    s = sub.add_parser('symbol', help='符号表：符号 ↔ 名字（类型维度）')
    s.add_argument('--add', default='', help='加一个符号，如 --add "$"')
    s.add_argument('--name', default='', help='这个符号对应什么名字，如 --name "代码"')
    s.add_argument('--desc', default='', help='一句话说明')
    s.add_argument('--remove', default='', help='删一个符号')
    s.set_defaults(fn=cmd_symbol)

    sub.add_parser('review').set_defaults(fn=cmd_review)

    s = sub.add_parser('promote'); s.add_argument('id'); s.set_defaults(fn=cmd_promote)
    s = sub.add_parser('drop'); s.add_argument('id'); s.set_defaults(fn=cmd_drop)

    s = sub.add_parser('gc')
    s.add_argument('--apply', action='store_true')
    s.set_defaults(fn=cmd_gc)

    s = sub.add_parser('rm')
    s.add_argument('key')
    s.add_argument('--yes', action='store_true', help='确认真的删（不加只列清单）')
    s.set_defaults(fn=cmd_rm)

    sub.add_parser('stats').set_defaults(fn=cmd_stats)

    a = ap.parse_args()
    if not getattr(a, 'fn', None):
        ap.print_help()
        sys.exit(0)
    a.fn(a)


if __name__ == '__main__':
    main()
