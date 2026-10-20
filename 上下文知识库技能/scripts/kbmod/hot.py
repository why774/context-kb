# -*- coding: utf-8 -*-
"""初始化与热层"""
from .base import *  # noqa: F401,F403
from .topics import _sync_topics_to_hot
import io, os, re, sys, json, datetime


def _read_syms(root):
    """读某个库里的前缀表。"""
    p = os.path.join(root, F_SYM)
    if not os.path.exists(p):
        return []
    out = []
    with io.open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def cmd_init(a):
    """建库。

    短期库：`init` → 建 talks 容器（每场对话一个子库）
    长期库：`init --long` → 建全局那一个
    """
    which = 'long' if a.long else 'short'
    root = lib_path(which)
    use_lib(which)

    if which == 'long':
        # 长期库：就是一个目录，功能跟短期库一样
        os.makedirs(root, exist_ok=True)
        os.makedirs(os.path.join(root, DIR_SESS), exist_ok=True)
        os.makedirs(os.path.join(root, DIR_ARCH), exist_ok=True)
        for f in (F_PIT, F_PREF, F_IDX, F_CAN, F_DIG, F_SUM, F_SYM, F_GROW):
            p = os.path.join(root, f)
            if not os.path.exists(p):
                with io.open(p, 'w', encoding='utf-8'):
                    pass
        if not os.path.exists(os.path.join(root, F_BOOK)):
            _write_hot(os.path.join(root, F_BOOK), long_lib=True)
        mp = os.path.join(root, F_META)
        if not os.path.exists(mp):
            with io.open(mp, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'seq': {'K': 0, 'P': 0, 'C': 0}, 'day': ''}))
        _preset_symbols(root)
        _sync_topics_to_hot()
        print('[ OK ] 已初始化长期库：%s' % os.path.abspath(root))
        print('       全局只有一个，所有对话的长期记忆都在这。')
        return

    # 短期库：只建 talks 容器（每场对话一个子库由 log 自动建）
    os.makedirs(os.path.join(root, DIR_TALK), exist_ok=True)
    mp = os.path.join(root, F_META)
    if not os.path.exists(mp):
        with io.open(mp, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'seq': {'K': 0, 'P': 0, 'C': 0, 'T': 0},
                                'day': ''}))
    _preset_symbols(root)
    print('[ OK ] 已初始化短期库容器：%s' % os.path.abspath(root))
    print('       每开一场对话会自动建一个独立的小库：')
    print('         %s/%s/<对话id>/' % (root, DIR_TALK))
    print('       现在这场对话的库：%s' % os.path.join(root, DIR_TALK, '<对话id>'))
    print('')
    print('       下一条 log 会自动建第一场对话的库。')
    print('       建议把 .context-kb/ 提交进 git（这是项目记忆，要跟着代码走）')


def _write_hot(path, long_lib=False):
    """写一份热层模板。"""
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        if long_lib:
            f.write('# 热层 · 长期库\n\n')
            f.write('> 长期层的记忆，跨所有对话累积：用户偏好、长期铁律、前缀表、长期经验、工具经验。\n')
            f.write('> 全部内容会进每一次请求——别塞细节，细节去坑点库。\n\n')
        else:
            f.write('# 热层 · 这场对话\n\n')
            f.write('> 这一场对话的临时记忆。对话结束（close）就并入长期库。\n\n')
        f.write('## 用户偏好\n\n- （还没有，用 `python scripts/kb.py pref --text "..."` 添加）\n\n')
        f.write('## 长期铁律（跨对话永久有效）\n\n')
        f.write('- （还没有，用 `python scripts/kb.py rule --text "..."` 添加）\n')
        f.write('\n## 本次对话约束（close 时自动清出热层）\n\n（无）\n')
        f.write('\n## 前缀表（写索引时从这里挑；没有就新建一个组）\n\n')
        f.write('（还没有，先 kb.py symbol --add "$" --name "代码"）\n')


def _preset_symbols(root):
    """预置前缀表（长期库那份是权威的）。"""
    syms = _read_syms(root)
    if syms:
        return
    builtin = [
        {'sym': '$', 'name': '代码', 'desc': '这段是代码相关的内容'},
        {'sym': '!', 'name': '坑点', 'desc': '这是踩过的坑'},
        {'sym': '?', 'name': '疑问', 'desc': '还没定论的事'},
        {'sym': '*', 'name': '关键', 'desc': '重要结论'},
    ]
    for b in builtin:
        b['date'] = today()
    with io.open(os.path.join(root, F_SYM), 'w', encoding='utf-8',
                 newline='\n') as f:
        for b in builtin:
            f.write(json.dumps(b, ensure_ascii=False) + '\n')
    print('       已预置前缀表：$ 代码 / ! 坑点 / ? 疑问 / * 关键')


def _read_syms(root):
    """读某个库里的前缀表。"""
    p = os.path.join(root, F_SYM)
    if not os.path.exists(p):
        return []
    out = []
    with io.open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def cmd_hot(a):
    p = d(F_BOOK)
    txt = ''
    if os.path.exists(p):
        with io.open(p, encoding='utf-8') as f:
            txt = f.read()
    pits = load(F_PIT)
    print('=' * 56)
    print(txt.rstrip())
    print('=' * 56)
    m = meta_read()
    cur = m.get('cur_session')
    ns = 0
    for sd in lib_dirs():
        if not seg_is_arch(sd):
            ns += len([x for x in os.listdir(sd) if x.endswith('.md')])
    print('\n长期层：坑点 %d 条 · 偏好 %d 条 · 索引 %d 条 · 工具经验 %d 条'
          % (len(pits), len(load(F_PREF)), len(load(F_IDX)), len(load(F_GROW))))
    print('短期层：会话原文 %d 个 · 候选 %d 条' % (ns, len(load(F_CAN))))
    if cur and not m.get('cur_closed'):
        print('当前进行中：%s（结束任务记得 close）' % cur)
