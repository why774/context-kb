# -*- coding: utf-8 -*-
"""会话层：段列表 / 会话摘要 / context 组装"""
from .base import *  # noqa: F401,F403
import io, os, re, sys, json, datetime


def cmd_session(a):
    """列出所有对话（按会话分组），或查看某段原文。
    a.id 可以是段名 S-20261019-001-p2，也可以是会话名 S-20261019-001（列出全部段）
    """
    if a.id:
        exact = []
        for sd in lib_dirs():
            p = os.path.join(sd, a.id + '.md')
            if os.path.exists(p):
                exact.append(p)
        if exact:
            for p in exact:
                with io.open(p, encoding='utf-8') as f:
                    print(f.read())
            return
        hits = []
        for sd in lib_dirs():
            for f in sorted(os.listdir(sd)):
                if f.startswith(a.id + '-p') and f.endswith('.md'):
                    hits.append(os.path.join(sd, f))
        if not hits:
            print('[ X ] 没有 %s' % a.id)
            sys.exit(2)
        for p in hits:
            with io.open(p, encoding='utf-8') as f:
                print(f.read())
            print('')
        return

    # 按会话分组
    groups = {}
    for sd in lib_dirs():
        for f in sorted(os.listdir(sd)):
            if not f.endswith('.md'):
                continue
            name = f[:-3]
            m = re.match(r'^(S-\d+-\d+)-p(\d+)$', name)
            sid, part = (m.group(1), int(m.group(2))) if m else ('其它', 0)
            p = os.path.join(sd, f)
            with io.open(p, encoding='utf-8') as fh:
                n = len([x for x in fh.read().split('\n') if x.startswith('- ')])
            groups.setdefault(sid, []).append(
                (part, n, f, os.path.basename(sd)))

    if not groups:
        print('还没有任何对话记录。')
        return

    print('共 %d 个对话：' % len(groups))
    digs = {}
    for r in load(F_DIG):
        digs[r.get('sid')] = r.get('text', '')

    for sid in sorted(groups, reverse=True):
        items = sorted(groups[sid])
        has_dig = '· 有摘要' if sid in digs else ''
        print('\n%s（%d 段）%s' % (sid, len(items), has_dig))
        if sid in digs:
            print('   摘要：%s' % digs[sid][:70])
        for part, n, f, sub_ in items:
            flag = '进行中' if sub_ == DIR_SESS else '已封存'
            print('   p%-2d  %3d 条   %-14s [%s]' % (part, n, f, flag))


# ── 会话级：把 N 段压成一段摘要，再组装成「该带进上下文的东西」 ──

def _cur():
    t = talk_read()
    return cur_talk_id(), (t.get('cur_part') or 1)


def session_index_rows(sid):
    return [r for r in load(F_IDX) if str(r.get('ref', '')).startswith(sid)]


def cmd_digest(a):
    sid, part = _cur()
    if not sid:
        print('当前没有进行中的会话。')
        return
    rows = session_index_rows(sid)
    if a.text:
        append(F_DIG, {'sid': sid, 'text': a.text,
                       'segs': len(rows), 'date': today()})
        print('[ OK ] 已写入 %s 的会话摘要（覆盖 %d 段）' % (sid, len(rows)))
        return
    print('%s 目前 %d 段，索引如下：\n' % (sid, len(rows)))
    for r in rows:
        print('  [%s] %s   -> %s' % (r['id'], r.get('gist', ''), r.get('ref', '')))
    if not rows:
        print('  （还没有索引，先把段 seal 掉）')
    print('')
    print('让 AI 读完上面这些，写一句总结这场对话干了什么，然后：')
    print('  python scripts/kb.py digest --text "这场对话解决了什么"')


def cmd_growth(a):
    """工具/操作经验：记一句「这个工具怎么用才对」。

    跨所有对话累积，是长期热层的一部分——AI 每次开场都能读到，
    相当于「用工具的手法」在积累。
    """
    if a.text:
        sid = cur_talk_id()
        rows = load(F_GROW)
        rows.append({'text': a.text.strip(), 'session': sid,
                     'date': today(), 'kind': a.kind or '工具'})
        rewrite(F_GROW, rows)
        print('[ OK ] 已记入经验：%s' % a.text.strip())
        print('       以后每次开场都在热层里带着它。')
        return
    if a.list:
        rows = load(F_GROW)
        if not rows:
            print('还没有记录的经验。')
            print('  记一句：kb.py growth --text "xxx工具要yyy才对"')
            return
        print('工具/操作经验（%d 条，最新在前）：\n' % len(rows))
        for r in rows[-20:][::-1]:
            print('  [%s] %s%s' % (r.get('date', ''), r.get('text', ''),
                                  '  ·%s' % r['kind'] if r.get('kind') else ''))
        return
    print('记一句工具/操作经验，或看已有的：')
    print('  kb.py growth --text "xxx工具要yyy才对"')
    print('  kb.py growth --list')


def _tail_lines(path, n):
    if not os.path.exists(path):
        return []
    with io.open(path, encoding='utf-8') as f:
        rows = [x.rstrip() for x in f if x.startswith('- ')]
    return rows[-n:]


def cmd_context(a):
    """组装「这一次该带进上下文的全部内容」。只读。

    **分级压缩（同一场对话内，按远近三档）**：
    · 很近     → 原文       （按**消息条数**算，--raw-lines）
    · 比较近   → 摘要       （按段算，--sum-segs）
    · 比较远   → 索引       （总结成一句，带坐标，AI 能跳回去）
    """
    parts = []
    p = d(F_BOOK)
    if os.path.exists(p):
        with io.open(p, encoding='utf-8') as f:
            parts.append('== 热层 · 偏好与铁律 ==\n' + f.read().rstrip())

    sid, part = _cur()
    rows = session_index_rows(sid) if sid else []

    # 本场各段（按 ref 排 = 时间顺序），并记下每段有几条消息
    segs, seg_msgs = [], {}
    for r in rows:
        ref = str(r.get('ref') or '')
        if not ref:
            continue
        if ref not in segs:
            segs.append(ref)
            seg_msgs[ref] = 0
        seg_msgs[ref] += 1
    # 补上没索引的段（还没写 index 的）
    for d_ in lib_dirs():
        for fn in sorted(os.listdir(d_)):
            if not fn.endswith('.md'):
                continue
            ref = fn[:-3]
            if ref.startswith(sid or '@@none@@') and ref not in segs:
                segs.append(ref)
                seg_msgs[ref] = 0

    # 每段实际消息数（数原文里的 '- ' 行）
    def msg_count(ref):
        fp = find_seg(ref)
        if fp:
            with io.open(fp, encoding='utf-8') as f:
                return len([x for x in f.read().split('\n') if x.startswith('- ')])
        return 0

    sums = {}
    for x in load(F_SUM):
        sums[str(x.get('ref') or '')] = x.get('text', '')

    # ① 很近：原文（从最新往回凑够 --raw-lines 条消息）
    budget = max(0, a.raw_lines)
    raw_refs, used = [], 0
    for ref in reversed(segs):
        if used >= budget:
            break
        c = msg_count(ref)
        if used + c <= budget or not raw_refs:
            raw_refs.append(ref)
            used += c
    raw_refs.reverse()

    raw_parts = []
    for ref in raw_refs:
        fp = find_seg(ref)
        if fp:
            with io.open(fp, encoding='utf-8') as f:
                raw_parts.append('--- %s ---\n%s' % (ref, f.read().rstrip()))
    # 当前段（正在进行的）也带最近几条
    if sid:
        tail = _tail_lines(
            os.path.join(lib_root('short'), DIR_SESS, '%s-p%d.md' % (sid, part)),
            a.recent)
        if tail:
            raw_parts.append('--- 当前段最近 %d 条 · %s 第 %d 段 ---\n%s' % (
                len(tail), sid, part, '\n'.join(tail)))
    if raw_parts:
        parts.append('== 很近 · 原文（最近 %d 条消息） ==\n' % used
                     + '\n\n'.join(raw_parts))

    rest = [r for r in segs if r not in raw_refs]

    # ② 比较近：摘要（最近 --sum-segs 段）
    sum_segs = max(0, a.sum_segs)
    mid_refs = rest[:sum_segs] if sum_segs else []
    mid_lines = []
    for ref in mid_refs:
        t = sums.get(ref)
        mid_lines.append('  %s：%s' % (ref, t if t else '（还没写摘要）'))
    if mid_lines:
        parts.append('== 比较近 · 摘要（%d 段） ==\n' % len(mid_refs)
                     + '\n'.join(mid_lines))

    # ③ 比较远：索引（总结成一句，带坐标）
    far_refs = rest[sum_segs:] if sum_segs else rest
    idx_lines = []
    for r in rows:
        ref = str(r.get('ref') or '')
        if ref in far_refs:
            idx_lines.append('  [%s] %s   -> %s' % (
                r['id'], r.get('gist', ''), ref))
    if idx_lines:
        parts.append('== 比较远 · 索引（%d 条 · 需要细节就按坐标读原文） ==\n'
                     % len(idx_lines) + '\n'.join(idx_lines))

    # ④ 本场总摘要（可选）
    if a.digest and sid:
        digs = [x for x in load(F_DIG) if x.get('sid') == sid]
        if digs:
            parts.append('== 本场总摘要 · %s ==\n%s' % (sid, digs[-1].get('text', '')))

    if not sid:
        parts.append('== 当前没有进行中的会话 ==')

    # ⑤ 库概况（告诉 AI 有什么可查）
    nseg = 0
    for sd in lib_dirs():
        if seg_is_arch(sd):
            nseg += len([x for x in os.listdir(sd) if x.endswith('.md')])
    parts.append('== 本地库（可查） ==\n'
                 '已归档 %d 段原文 · %d 条坑点 · %d 条索引\n'
                 '用户提到以前讨论过的内容时，先跑：python scripts/kb.py search <用户原话里的关键词>\n'
                 '命中后按 ref 读原文：python scripts/kb.py session <段名>\n'
                 '关键词说不清（"上次那套"）→ 先问用户具体指哪个，不要猜。' % (
                     nseg, len(load(F_PIT)), len(load(F_IDX))))

    out = '\n\n'.join(parts)
    print(out)
    print('')
    print('-' * 56)
    print('粗估 %d token（汉字按 1 算，偏保守）' % len(out))
    print('用法：把上面整段放进 system prompt 或对话开头。')
    print('     换档位：--raw-lines 60（原文几条消息） --sum-segs 3（摘要几段）')
    print('     要某段原文：python scripts/kb.py session <段名>')


