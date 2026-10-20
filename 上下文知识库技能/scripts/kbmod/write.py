# -*- coding: utf-8 -*-
"""写入：坑点 / 偏好 / 索引 / 铁律 / 段与封存"""
from .base import *  # noqa: F401,F403
from .base import _looks_like_code, segment_has_code
from .topics import *  # noqa: F401,F403
from .topics import _sync_topics_to_hot
import io, os, re, sys, json, datetime


def cmd_pitfall(a):
    if not a.symptom and not a.fix:
        print('[ X ] 至少要有 --symptom（症状）或 --fix（解法），否则这条坑点没用')
        sys.exit(2)
    rid = next_id('K')
    obj = {
        'id': rid,
        'title': a.title,
        'symptom': a.symptom,
        'cause': a.cause,
        'fix': a.fix,
        'tags': [t.strip() for t in (a.tags or '').split(',') if t.strip()],
        'files': [t.strip() for t in (a.files or '').split(',') if t.strip()],
        'hit': 0,
        'last': today(),
        'status': 'active',
        'superseded_by': None,
    }
    append(F_PIT, obj)
    print('[ OK ] 已记录 %s' % rid)
    print(fmt_pit(obj))
    sim = [r for r in load(F_PIT)
           if r['id'] != rid and len(set(r.get('tags') or []) & set(obj['tags'])) >= 2]
    if sim:
        print('[ ! ] 发现 %d 条 tag 高度重合的旧条目，检查是否重复：' % len(sim))
        for r in sim:
            print('      %s  %s' % (r['id'], r.get('title', '')))


def cmd_pref(a):
    rid = next_id('P')
    obj = {
        'id': rid,
        'text': a.text,
        'tags': [t.strip() for t in (a.tags or '').split(',') if t.strip()],
        'since': today(),
        'status': 'active',
        'superseded_by': None,
    }
    append(F_PREF, obj)
    ensure_talk()
    p = d(F_BOOK)
    with io.open(p, encoding='utf-8') as f:
        txt = f.read()
    marker = '## 用户偏好'
    add = '\n- %s　`%s`\n' % (a.text, rid)
    if marker in txt:
        i = txt.index(marker) + len(marker)
        j = txt.find('\n## ', i)
        j = j if j != -1 else len(txt)
        block = txt[i:j]
        block = re.sub(r'\n- （还没有[^\n]*）\n', '\n', block)
        txt = txt[:i] + block.rstrip() + '\n' + add.strip('\n') + '\n' + txt[j:]
    else:
        txt += '\n' + marker + add
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)
    print('[ OK ] 已记录 %s，并同步进热层 hot.md' % rid)


def cmd_index(a):
    rid = next_id('C')

    tags = [t.strip() for t in (a.tags or '').split(',') if t.strip()]

    # ── 前缀（符号）= 一个组，必须挂 ──
    # gist 开头的符号被剥出来，单独存到 sym 字段。
    # **主题名由符号映射给出**，gist 只写「符号 + 结论」。
    sym, rest = split_symbol(a.gist)
    if not sym and a.sym:
        sym = a.sym.strip()
    syms = load_symbols()
    if sym and sym not in syms:
        print('[ ! ] 符号「%s」不在前缀表里。' % sym)
        print('      现有前缀：%s'
              % ('、'.join('%s(%s)' % (k, v['name']) for k, v in syms.items())
                 or '（表是空的）'))
        print('      新建一个组：kb.py symbol --add "%s" --name "组名" '
              '--desc "说明"' % sym)
        sys.exit(2)

    # 组键 = 符号。没符号就用 --topic 或老格式切。
    top, how = '', ''
    if sym:
        top, how = sym, '前缀符号'
    elif a.topic:
        top, how = a.topic, '手动指定'
    elif topic_of(rest):
        top, how = topic_of(rest), '取自名字前缀'

    # 代码类：程序看这条索引指到的地方有没有代码。AI 不用额外说。
    # 看的是 --lines 指到的那几行（没指就看整段）——
    # 一段里既有代码又有结论很正常，不能整段一刀切。
    subs_list = [x.strip() for x in (a.subs or '').split(';') if x.strip()]
    blob = rest + ' ' + ' '.join(subs_list)
    if not sym and (bool(a.code) or _looks_like_code(blob)
                    or segment_has_code(a.ref, a.lines)):
        sym = '$'
        how = '程序按内容认出是代码'
    if not sym:
        print('[ ! ] 这条还没有前缀（前缀一定要加——没前缀就没法被检索到）。')
        print('      现有前缀：')
        for k, v in sorted(syms.items(), key=lambda x: x[0]):
            print('        %-4s %-10s %s' % (k, v['name'], v['desc']))
        print('      挑一个，写在 gist 开头就行，比如：')
        print('        kb.py index --gist "$结论" --ref <段名>')
        print('      没有合适的就新建一个组：'
              'kb.py symbol --add "@" --name "待办" --desc "要做的事"')
        sys.exit(2)

    # --summary：AI 顺手写的这段摘要（「比较近」那档要用）
    if a.summary:
        ref = a.ref
        rows = [x for x in load(F_SUM) if x.get('ref') != ref]
        rows.append({'ref': ref, 'sid': cur_talk_id(),
                     'text': a.summary.strip(), 'date': today(), 'auto': False})
        rewrite(F_SUM, rows)

    obj = {
        'id': rid,
        'gist': a.gist,
        'sym': sym,
        'topic': top,
        'ref': a.ref,
        'lines': a.lines,
        'subs': subs_list,
        'tags': tags,
        'date': today(),
    }
    append(F_IDX, obj)
    print('[ OK ] 已记录 %s' % rid)
    print('[%s] %s\n      -> %s' % (rid, obj['gist'], ref_to_path(obj['ref'], obj['lines'])))
    for sub in obj['subs']:
        print('      ├ %s' % sub)
    if a.summary:
        print('      [摘要已记：%s]' % a.summary.strip())

    if sym:
        v = load_symbols().get(sym, {})
        print('      [前缀：%s = %s%s]'
              % (sym, v.get('name', '?'),
                 ('（%s）' % how) if how else ''))
    if sym:
        v = load_symbols().get(sym, {})
        nm = v.get('name', '?')
        print('      [组：%s = %s（%d 条，线 %d）]'
              % (sym, nm,
                 sum(1 for r in load(F_IDX) if row_topic(r) == sym),
                 hot_threshold(nm)))
    elif top:
        print('      [组：%s（%d 条，线 %d）]'
              % (top, sum(1 for r in load(F_IDX) if row_topic(r) == top),
                 hot_threshold(top)))
    else:
        print('[ ! ] 没认出组名。用 --topic "组名" 明确指定。')
    if not a.lines and not obj['subs']:
        print('提示：加 --lines "5-12" 钉到段内某几行；段内多主题用 --subs "5-40 甲;41-80 乙"')


# ── 短期层：原文先落盘，任务结束再归纳 ──────────────

def cur_segment():
    """返回当前未封存的段 (tid, part, path)；需要时自动建库/开新段。

    **每开一场对话就建一个独立的短期库**：
      .context-kb/talks/<对话id>/{session,archive,index.jsonl,…}
    库建好后 .context-kb/current 指向它，close 之后清掉（下次 log 建新的一场）。
    """
    tid = cur_talk_id()
    if tid and not talk_read().get('cur_closed'):
        t = talk_read()
        part = t.get('cur_part') or 1
        p = os.path.join(talk_dir(tid), DIR_SESS, '%s-p%d.md' % (tid, part))
        if os.path.exists(p):
            return tid, part, p

    # 没有进行中的段 → 开新的一场对话（= 新建一个短期库）
    tid = next_id('T')
    tdir = talk_dir(tid)
    os.makedirs(os.path.join(tdir, DIR_SESS), exist_ok=True)
    os.makedirs(os.path.join(tdir, DIR_ARCH), exist_ok=True)
    for f in (F_PIT, F_PREF, F_IDX, F_CAN, F_DIG, F_SUM, F_GROW):
        p = os.path.join(tdir, f)
        if not os.path.exists(p):
            with io.open(p, 'w', encoding='utf-8'):
                pass
    hp = os.path.join(tdir, F_BOOK)
    if not os.path.exists(hp):
        from .hot import _write_hot
        _write_hot(hp)
    set_cur_talk(tid)
    talk_write({'cur_part': 1, 'cur_closed': False, 'started': today()})

    part = 1
    p = os.path.join(tdir, DIR_SESS, '%s-p%d.md' % (tid, part))
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# %s · 第 %d 段 · %s\n\n' % (tid, part, today()))
        f.write('> 短期原文。这一段聊完就 seal，别攒到整场对话结束。\n\n')
    return tid, part, p


def _seal_current(final=False):
    """封存当前段：从 session/ 移到 archive/。原文只有一份，不复制。"""
    sid = cur_talk_id()
    if not sid:
        return None
    t = talk_read()
    part = t.get('cur_part') or 1
    src = os.path.join(talk_dir(sid), DIR_SESS, '%s-p%d.md' % (sid, part))
    if not os.path.exists(src):
        return None
    os.makedirs(os.path.join(talk_dir(sid), DIR_ARCH), exist_ok=True)
    dst = os.path.join(talk_dir(sid), DIR_ARCH, '%s-p%d.md' % (sid, part))
    os.replace(src, dst)
    t['cur_closed'] = bool(final)
    if not final:
        t['cur_part'] = part + 1
    talk_write(t)
    with io.open(dst, encoding='utf-8') as f:
        n = len([x for x in f.read().split('\n') if x.startswith('- ')])
    return sid, part, dst, n


def cmd_log(a):
    sid, part, p = cur_segment()
    raw = a.text.strip()
    # 代码保留原样换行（缩进是代码的一部分，压成一行就废了）；
    # 普通文本压成一行，省得占行数。
    if _looks_like_code(raw):
        body = raw.replace('\r\n', '\n')
        block = '\n'.join('    ' + l for l in body.split('\n'))
        with io.open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.write('- %s [%s] ```\n%s\n    ```\n' % (now_hm(), a.who, block))
    else:
        text = raw.replace('\n', ' ').strip()
        with io.open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.write('- %s [%s] %s\n' % (now_hm(), a.who, text))
    with io.open(p, encoding='utf-8') as f:
        n = len(f.read().split('\n'))
    print('[ OK ] 已记入 %s 第 %d 段（%d 行）' % (sid, part, n))
    if _looks_like_code(raw):
        print('[ ! ] 这段像代码。代码已原样存进原文层（缩进保留）。')
        print('     索引层别放代码原文，写你分析出来的结论：')
        print('     --gist "白名单：校验必须在 open_app 之前" --tags "白名单校验,open_app"')
    if n > MAX_RAW_LINES:
        print('[ ! ] 这一段已经 %d 行，太长了，该 seal：python scripts/kb.py seal' % n)


def cmd_seal(a):
    r = _seal_current(final=False)
    if not r:
        print('当前没有进行中的段。')
        return
    sid, part, dst, n = r
    print('[ OK ] %s 第 %d 段已封存（%d 条原文）' % (sid, part, n))
    print('       .context-kb/%s/%s-p%d.md' % (DIR_ARCH, sid, part))
    ref = '%s-p%d' % (sid, part)
    print('')
    print('归纳这一段（用 AI，1-2 条就够）：')
    print('  python scripts/kb.py index --gist "这一段聊出了什么结论" '
          '--summary "这段聊了什么，一句话" --ref "%s"' % ref)
    print('  （--summary 是这段的摘要，后面"比较近"那档要用；顺手写上就行）')
    print('有踩坑就再补一条：')
    print('  python scripts/kb.py pitfall --title "..." --symptom "..." --fix "..." --tags "..."')
    print('')
    print('下一条 log 会自动开新段（%s 第 %d 段）。' % (sid, part + 1))


def cmd_close(a):
    """结束这场对话：封最后一段 + 清本次约束 + **直接并入长期库**。

    **不管对话多短都并入** —— 就算只聊了两句，产生的坑点/偏好/经验也要留下。
    """
    r = _seal_current(final=True)
    t = talk_read()
    tid = cur_talk_id()
    if not r:
        if t.get('cur_closed'):
            print('当前对话已经关闭过了。')
        elif not tid:
            print('当前没有打开的对话。')
        else:
            t['cur_closed'] = True
            talk_write(t)
            print('[ OK ] 对话 %s 已结束（当前段已封存）' % tid)
    else:
        sid, part, dst, n = r
        print('[ OK ] 对话 %s 已结束，最后一段（%d 条）封存到：' % (sid, n))
        print('       %s' % os.path.join(talk_dir(sid), DIR_ARCH,
                                       '%s-p%d.md' % (sid, part)))
        # 本次对话约束清出热层（内容留进本段原文，不丢）
        hot = os.path.join(talk_dir(sid), F_BOOK)
        if os.path.exists(hot):
            with io.open(hot, encoding='utf-8') as f:
                txt = f.read()
            key = '## 本次对话约束'
            if key in txt:
                i2 = txt.index(key)
                j2 = txt.find('\n## ', i2 + len(key))
                j2 = j2 if j2 != -1 else len(txt)
                body = txt[i2:j2].replace(key, '').strip()
                body = body.replace('（close 时自动清出热层）', '').strip()
                if body and body not in ('（无）', ''):
                    with io.open(dst, 'a', encoding='utf-8',
                                 newline='\n') as f:
                        f.write('\n> 本场对话的临时约束（已清出热层，仅作记录）：\n')
                        f.write(body + '\n')
                    txt = txt[:i2] + key + '（close 时自动清出热层）\n\n（无）\n' + txt[j2:]
                    with io.open(hot, 'w', encoding='utf-8',
                                 newline='\n') as f:
                        f.write(txt)
                    print('[ OK ] 本次对话的临时约束已清出热层（内容留在本段原文里）')

    print('')
    print('把这场的成果并入长期库（不管多短都要并）：')
    print('  python scripts/kb.py merge')
    print('')
    print('最后记一条「这个工具怎么用才对」——它进长期热层，以后每次开场都带着：')
    print('  python scripts/kb.py growth --text "xxx工具要yyy才对"')
    print('')
    print('下次 log 会自动开新的一场对话（新库）。')


def cmd_rule(a):
    """铁律分长期（写进 hot.md 顶部区块）和短期（本次任务内有效）"""
    ensure_talk()
    p = d(F_BOOK)
    with io.open(p, encoding='utf-8') as f:
        txt = f.read()
    if a.short:
        marker = '## 本次对话约束'
        if marker in txt:
            i = txt.index(marker) + len(marker)
            j = txt.find('\n## ', i)
            j = j if j != -1 else len(txt)
            block = re.sub(r'\n（无）\n?', '\n', txt[i:j])
            txt = txt[:i] + block.rstrip() + '\n- %s\n' % a.text + txt[j:]
        else:
            txt = txt.rstrip() + '\n\n' + marker + '\n\n- %s\n' % a.text
    else:
        marker = '## 长期铁律'
        add = '\n- %s\n' % a.text
        if marker in txt:
            i = txt.index(marker) + len(marker)
            j = txt.find('\n## ', i)
            j = j if j != -1 else len(txt)
            block = re.sub(r'\n- （还没有[^\n]*）\n', '\n', txt[i:j])
            txt = txt[:i] + block.rstrip() + '\n' + add.strip('\n') + '\n' + txt[j:]
        else:
            txt = txt.rstrip() + '\n\n' + marker + add
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)
    print('[ OK ] 已写入热层：%s' % ('短期约束' if a.short else '长期铁律'))
