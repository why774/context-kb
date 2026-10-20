# -*- coding: utf-8 -*-
"""check：查漏。哪段没写索引、哪段没写摘要、哪个坑点没解法。

**这是唯一的「检查」工具**，不改别的工具。配合铁律用：
写完一段对话，AI 自己跑一次 check，看有没有漏的。
"""
import io, os, re, sys, json
from .base import *  # noqa: F401,F403
from .base import (F_PIT, F_IDX, F_SUM, F_BOOK, F_META, F_SYM, F_GROW,
                   F_PREF, DIR_ARCH, DIR_SESS)


def _read(path):
    if not os.path.exists(path):
        return []
    out = []
    with io.open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _all_segments(which):
    """库里所有的段（按时间顺序）。"""
    segs = []
    for d in lib_dirs(which):
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.md'):
                ref = fn[:-3]
                if ref not in segs:
                    segs.append(ref)
    return segs


def cmd_check(a):
    """检查「这个段有没有写索引」。

    带 --ref 查指定的段；不带就查全库，列出所有漏的段。
    """
    which_lib = 'long' if getattr(a, 'long', False) else 'short'
    root = lib_path(which_lib)
    which = '长期' if which_lib == 'long' else '短期'
    if not os.path.isdir(root):
        print('[ X ] %s库不存在：%s' % (which, root))
        sys.exit(2)
    data_root = lib_root(which_lib)
    if not os.path.isdir(data_root):
        data_root = root

    idx = load(F_IDX, which_lib)
    sums = load(F_SUM, which_lib)
    segs = _all_segments(which_lib)

    # ── 查指定的段：有没有写索引 ──
    if a.ref:
        ref = a.ref.strip()
        hits = [r for r in idx if str(r.get('ref') or '').startswith(ref)]
        s_hit = [x for x in sums if str(x.get('ref') or '') == ref]
        print('%s 段「%s」' % ('长期' if getattr(a, 'long', False) else '短期',
                              ref))
        if hits:
            print('  [ OK ] 有索引（%d 条）：' % len(hits))
            for r in hits:
                print('     [%s] %s   -> %s'
                      % (r.get('id', ''), r.get('gist', ''), r.get('ref', '')))
        else:
            print('  [ ! ] **没有索引** → 搜不到它，合并到长期库也带不走。')
            print('     补一条：')
            print('     kb.py index --gist "这段聊出了什么结论" '
                  '--summary "这段聊了什么，一句话" --ref "%s"' % ref)
        if s_hit:
            print('  [ OK ] 有摘要：%s' % s_hit[-1].get('text', ''))
        else:
            print('  [ ! ] 没有摘要 → 「比较近」那档会显示「（还没写摘要）」')
        if not hits:
            sys.exit(1)
        return

    idx_refs = set()
    for r in idx:
        ref = str(r.get('ref') or '').split(':')[0]
        if ref:
            idx_refs.add(ref)
    sum_refs = set(str(x.get('ref') or '') for x in sums)

    no_idx = [s for s in segs if s not in idx_refs]
    no_sum = [s for s in segs if s not in sum_refs]

    print('检查 %s库：%s' % (which, data_root))
    print('  段 %d 个 · 索引 %d 条 · 摘要 %d 条\n'
          % (len(segs), len(idx), len(sums)))

    if no_idx:
        print('[ ! ] %d 段没建索引 —— 搜不到它们，合并到长期库也带不走：'
              % len(no_idx))
        for s in no_idx:
            print('     %s' % s)
        print('     补一条：kb.py index --gist "这段聊出了什么结论" '
              '--summary "一段话" --ref "%s"' % (no_idx[0] if no_idx else ''))
        print('')
    else:
        print('[ OK ] 每段都有索引')

    if no_sum:
        print('[ ! ] %d 段没写摘要 —— 「比较近」那档会显示「（还没写摘要）」：'
              % len(no_sum))
        for s in no_sum[:8]:
            print('     %s' % s)
        if len(no_sum) > 8:
            print('     ... 还有 %d 段' % (len(no_sum) - 8))
        print('     补一句：kb.py index --gist "..." --summary "..." '
              '--ref "<段名>"')
        print('')
    else:
        print('[ OK ] 每段都有摘要')

    # 坑点：没写解法的没用
    pits = [x for x in load(F_PIT, which_lib)
            if x.get('status', 'active') == 'active']
    bad_pit = [x for x in pits if not (x.get('fix') or '').strip()]
    if bad_pit:
        print('[ ! ] %d 个坑点没写解法（fix）：' % len(bad_pit))
        for x in bad_pit[:6]:
            print('     %s %s' % (x.get('id', ''), x.get('title', '')))
        print('')

    # 长期库该有的东西
    if which == '长期':
        grow = load(F_GROW, which_lib)
        if not grow:
            print('[ ! ] 还没有工具/操作经验。记一条：'
                  'kb.py growth --text "xxx工具要yyy才对"')
        else:
            print('[ OK ] 工具/操作经验 %d 条' % len(grow))

    if not no_idx and not no_sum and not bad_pit:
        print('')
        print('（没查出漏的。）')