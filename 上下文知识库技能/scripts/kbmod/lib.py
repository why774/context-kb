# -*- coding: utf-8 -*-
"""库管理：短期库 ↔ 长期库的并入与踢出。

模型：
  · 短期库 —— 一个项目一个，可以多开（项目目录下的 .context-kb/）
  · 长期库 —— 全局只有一个（~/.context-kb/），跨所有项目
  · 两层功能完全一样，就是数据位置不同
  · 项目结束 → merge（并入长期库）
  · 项目被删  → unmerge（从长期库踢掉这个项目带来的东西）

并入时要记「这条是哪个项目带来的」，否则踢不干净。
"""
from .base import *  # noqa: F401,F403
from .base import (F_PIT, F_PREF, F_IDX, F_DIG, F_SYM, F_GROW,
                   F_BOOK, F_META, F_SUM, DIR_ARCH, DIR_SESS)
from .topics import _sync_topics_to_hot
import io, os, re, sys, json


def _proj_name():
    """当前短期库属于哪个项目——用项目目录名。"""
    p = os.path.abspath(os.getcwd())
    return os.path.basename(p) or 'unnamed'


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with io.open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def _write_jsonl(path, rows):
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def cmd_merge(a):
    """把当前这场对话并入长期库。

    **不管对话多短都并** —— 就算只聊了两句，产生的坑点/偏好/经验也要留下来。
    """
    long_ = lib_path('long')
    short = lib_path('short')
    tid = cur_talk_id()
    if not tid:
        print('[ ! ] 当前没有打开的对话，没什么可并的。')
        return
    src = talk_dir(tid)
    if not os.path.isdir(src):
        print('[ ! ] 找不到这场对话的库：%s' % src)
        return
    os.makedirs(long_, exist_ok=True)
    for sub in (DIR_SESS, DIR_ARCH):
        os.makedirs(os.path.join(long_, sub), exist_ok=True)
    for f in (F_PIT, F_PREF, F_IDX, F_CAN, F_DIG, F_SUM, F_SYM, F_GROW,
              F_BOOK, F_META):
        p = os.path.join(long_, f)
        if not os.path.exists(p):
            if f == F_BOOK:
                with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write('# 热层 · 长期库\n\n')
            else:
                io.open(p, 'w', encoding='utf-8').close()

    proj = _proj_name()
    mp = os.path.join(long_, 'projects.json')
    m = {}
    if os.path.exists(mp):
        with io.open(mp, encoding='utf-8') as f:
            try:
                m = json.load(f)
            except ValueError:
                m = {}
    m.setdefault(proj, {'name': proj, 'path': os.path.abspath(short),
                         'merged': today(), 'items': {}, 'talks': []})
    m[proj]['merged'] = today()
    m[proj]['path'] = os.path.abspath(short)
    if tid not in m[proj].setdefault('talks', []):
        m[proj]['talks'].append(tid)

    moved = 0
    # 只并这场对话产生的东西；前缀表两边共用，不并
    for fname, keyname in ((F_PIT, 'pitfalls'), (F_PREF, 'prefs'),
                           (F_GROW, 'growth'),
                           (F_IDX, 'index'), (F_DIG, 'digests'),
                           (F_SUM, 'summaries')):
        sp = os.path.join(src, fname)
        if not os.path.exists(sp):
            continue
        rows_s = _read_jsonl(sp)
        if not rows_s:
            continue
        dp = os.path.join(long_, fname)
        rows_l = _read_jsonl(dp)
        have = set(str(r.get('id') or r.get('sym') or r.get('ref') or '')
                   for r in rows_l)
        added = []
        for r in rows_s:
            r = dict(r)
            r['from'] = proj
            r['talk'] = tid
            k = str(r.get('id') or r.get('sym') or r.get('ref') or '')
            if k in have:
                continue
            rows_l.append(r)
            added.append(k)
            have.add(k)
        _write_jsonl(dp, rows_l)
        if added:
            m[proj]['items'][keyname] = m[proj]['items'].get(keyname, []) + added
            moved += len(added)

    # 原文也拷过去
    ad = os.path.join(src, DIR_ARCH)
    if os.path.isdir(ad):
        for fn in sorted(os.listdir(ad)):
            if fn.endswith('.md'):
                dp = os.path.join(long_, DIR_ARCH, fn)
                if not os.path.exists(dp):
                    with io.open(os.path.join(ad, fn), encoding='utf-8') as f:
                        txt = f.read()
                    with io.open(dp, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(txt)

    with io.open(mp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(m, ensure_ascii=False, indent=2))

    # 检查漏网的段：封存了但没建索引的段，带不走
    idx_refs = set()
    for r in _read_jsonl(os.path.join(src, F_IDX)):
        idx_refs.add(str(r.get('ref') or '').split(':')[0])
    no_idx = []
    for fn in sorted(os.listdir(ad)) if os.path.isdir(ad) else []:
        if fn.endswith('.md'):
            ref = fn[:-3]
            if ref not in idx_refs:
                no_idx.append(ref)

    use_lib('long')
    _sync_topics_to_hot()

    print('[ OK ] 已并入长期库：%s' % os.path.abspath(long_))
    print('       对话 %s · 项目「%s」· 带过去 %d 条' % (tid, proj, moved))
    if no_idx:
        print('')
        print('[ ! ] 有 %d 段封存了但没建索引，**它们带不走**（没索引 = 搜不到）：'
              % len(no_idx))
        for ref in no_idx:
            print('       %s' % ref)
    print('')
    print('长期热层已更新。以后这个项目被删了：kb.py unmerge')


def cmd_unmerge(a):
    """把这个项目从长期库踢出去。"""
    long_ = lib_path('long')
    if os.path.abspath(lib_path('short')) == os.path.abspath(long_):
        print('已经在长期库里了，没什么可踢的。')
        return
    mp = os.path.join(long_, 'projects.json')
    if not os.path.exists(mp):
        print('[ X ] 长期库里没有项目记录（%s）' % mp)
        sys.exit(2)
    with io.open(mp, encoding='utf-8') as f:
        try:
            m = json.load(f)
        except ValueError:
            m = {}
    proj = a.project or _proj_name()
    if proj not in m:
        print('[ X ] 长期库里没有项目「%s」' % proj)
        print('      已并入的项目：%s' % ('、'.join(m.keys()) or '（无）'))
        sys.exit(2)

    items = m[proj].get('items') or {}
    removed = 0
    for fname, keyname in ((F_PIT, 'pitfalls'), (F_PREF, 'prefs'),
                           (F_GROW, 'growth'),
                           (F_IDX, 'index'), (F_DIG, 'digests'),
                           (F_SUM, 'summaries')):
        p = os.path.join(long_, fname)
        if not os.path.exists(p):
            continue
        rows = _read_jsonl(p)
        keep = [r for r in rows if r.get('from') != proj]
        if len(keep) != len(rows):
            removed += len(rows) - len(keep)
            _write_jsonl(p, keep)

    # 原文也删掉这个项目的
    for sub in (DIR_ARCH,):
        sd = os.path.join(long_, sub)
        if not os.path.isdir(sd):
            continue
        for fn in sorted(os.listdir(sd)):
            if fn.endswith('.md'):
                try:
                    with io.open(os.path.join(sd, fn), encoding='utf-8') as f:
                        txt = f.read()
                except IOError:
                    continue
                if ('from: %s' % proj) in txt or ('项目: %s' % proj) in txt:
                    os.remove(os.path.join(sd, fn))
                    removed += 1

    m.pop(proj, None)
    with io.open(mp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(m, ensure_ascii=False, indent=2))

    use_lib('long')
    _sync_topics_to_hot()
    print('[ OK ] 项目「%s」已从长期库踢出（清掉 %d 条）' % (proj, removed))
    print('       长期热层已更新。')


def cmd_libs(a):
    """列出所有库：短期库（多开）+ 长期库（一个）。"""
    print('库的情况：\n')
    print('【短期库】一个项目一个，可以多开')
    for p in (lib_path('short'),):
        if os.path.isdir(p):
            n = len(_read_jsonl(os.path.join(p, F_IDX)))
            print('  %-40s 索引 %d 条' % (os.path.abspath(p), n))
        else:
            print('  %-40s （当前目录还没有）' % os.path.abspath(p))
    print('')
    print('【长期库】全局只有一个')
    if os.path.isdir(lib_path('long')):
        n = len(_read_jsonl(os.path.join(lib_path('long'), F_IDX)))
        pit = len(_read_jsonl(os.path.join(lib_path('long'), F_PIT)))
        print('  %-40s 索引 %d 条 · 坑点 %d 条' % (lib_path('long'), n, pit))
        mp = os.path.join(lib_path('long'), 'projects.json')
        if os.path.exists(mp):
            with io.open(mp, encoding='utf-8') as f:
                try:
                    m = json.load(f)
                except ValueError:
                    m = {}
            if m:
                print('  已并入的项目：')
                for k, v in m.items():
                    print('    %-20s %d 条' % (k, sum(
                        len(x) for x in (v.get('items') or {}).values())))
    else:
        print('  %-40s （还没有，init --long 建一个）' % lib_path('long'))
    print('')
    print('常用：')
    print('  kb.py init --long              在长期库操作（建坑点、偏好、铁律）')
    print('  kb.py merge                    短期库 → 长期库')
    print('  kb.py unmerge                  长期库 → 踢掉当前项目')