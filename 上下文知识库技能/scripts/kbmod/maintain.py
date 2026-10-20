# -*- coding: utf-8 -*-
"""维护：删除 / 建议 / 候选区 / 清理 / 统计"""
from .base import *  # noqa: F401,F403
import io, os, re, sys, json, datetime


# ── 删除：默认不删，要删必须列清单 + 输 y ──────────

def _find_targets(key):
    """找出 key 命中的所有东西：段文件、jsonl 条目、会话摘要。
    key 可以是：段名 S-xxx-p1 / 会话名 S-xxx / K-003 / C-xxx / P-xxx
    """
    files, rows = [], []
    seen = set()

    def add_file(p):
        if p not in seen and os.path.exists(p):
            seen.add(p)
            files.append(p)

    for sd in lib_dirs():
        add_file(os.path.join(sd, key + '.md'))
        for f in sorted(os.listdir(sd)):
            if f.endswith('.md') and f.startswith(key + '-p'):
                add_file(os.path.join(sd, f))

    for f, label in ((F_PIT, '坑点'), (F_IDX, '索引'),
                     (F_PREF, '偏好'), (F_CAN, '候选')):
        for r in load(f):
            if r.get('id') == key:
                rows.append((label, f, r))

    for r in load(F_DIG):
        if r.get('sid') == key:
            rows.append(('会话摘要', F_DIG, r))

    return files, rows


def cmd_rm(a):
    files, rows = _find_targets(a.key)
    if not files and not rows:
        print('[ X ] 没有找到 %s' % a.key)
        sys.exit(2)

    print('将要删除以下内容（不可恢复）：\n')
    for p in files:
        try:
            rel = os.path.relpath(p, lib_root())
        except ValueError:
            rel = p
        with io.open(p, encoding='utf-8') as f:
            n = len([x for x in f.read().split('\n') if x.startswith('- ')])
        print('  [原文] %-28s %d 条' % (rel, n))
    for label, f, r in rows:
        desc = r.get('title') or r.get('gist') or r.get('text') or r.get('sid') or ''
        print('  [%s] %-8s %s' % (label, r.get('id', ''), desc[:60]))

    if not a.yes:
        print('\n确认要删就加 --yes：python scripts/kb.py rm %s --yes' % a.key)
        print('（不加会一直只列清单，不动手）')
        return

    for p in files:
        os.remove(p)
    for f in set(x[1] for x in rows):
        ids = set(r.get('id') for lab, ff, r in rows if ff == f)
        sids = set(r.get('sid') for lab, ff, r in rows
                   if ff == f and r.get('sid') == a.key)
        keep = [r for r in load(f)
                if r.get('id') not in ids and r.get('sid') not in sids]
        rewrite(f, keep)

    print('\n[ OK ] 已删除 %d 个文件、%d 条记录' % (len(files), len(rows)))


def cmd_suggest(a):
    """按「用户问了几次」切小节，直接输出可复制的 --subs 字符串。
    不需要人判断什么算一个主题——问一次就是一件。
    """
    m = meta_read()
    sid = m.get('cur_session')
    part = m.get('cur_part') or 1
    if not sid:
        print('当前没有进行中的段。')
        return
    p = os.path.join(lib_root(), DIR_SESS, '%s-p%d.md' % (sid, part))
    if not os.path.exists(p):
        print('当前段文件还没生成，先 log 几条。')
        return

    asks = []
    total = 0
    all_lines = 0
    with io.open(p, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total = i
            if line.startswith('- '):
                all_lines += 1
            if line.startswith('- ') and '[用户]' in line:
                txt = line.split(']', 1)[-1].strip()
                asks.append((i, txt))
    if not asks:
        print('这一段里没有用户发言，没法切小节。')
        return
    if len(asks) == all_lines and all_lines > 2:
        print('[ ! ] 这一段 %d 条发言全被标成「用户」，很可能漏了 --who AI。' % all_lines)
        print('      小节是按用户提问切的，全标成用户会切成"一条一句"，等于没切。')
        print('      补标：kb.py log "..." --who AI\n')

    segs = []
    for idx, (ln, txt) in enumerate(asks):
        end = asks[idx + 1][0] - 1 if idx + 1 < len(asks) else total
        title = re.sub(r'^用户(问|说)[:：]\s*', '', txt)
        title = re.sub(r'^[「"\'（(]+', '', title)
        title = title.replace(';', '；').replace('\n', ' ')[:18].strip()
        segs.append((ln, end, title))

    print('%s 第 %d 段：按你提问的次数，可以切成 %d 个小节\n' % (sid, part, len(segs)))
    print('  行范围      小节标题')
    for s, e, t in segs:
        print('  %-10s  %s' % ('%d-%d' % (s, e), t))
    print('')
    print('直接复制下面这串当 --subs：\n')
    joined = ';'.join('%d-%d %s' % (s, e, t) for s, e, t in segs)
    print('  --subs "%s"' % joined)
    print('')
    if len(segs) > 10:
        print('[ ! ] 已经 %d 个小节了，说明这一段太长，先 seal 更合适：kb.py seal' % len(segs))


def cmd_review(a):
    rows = load(F_CAN)
    if not rows:
        print('候选区是空的。')
        return
    print('候选区 %d 条（AI 提议的，等你确认）：\n' % len(rows))
    for r in rows:
        print('[%s] %s' % (r.get('id'), r.get('title') or r.get('gist') or r.get('text') or ''))
        for k in ('symptom', 'cause', 'fix', 'reason', 'ref'):
            if r.get(k):
                print('   %s：%s' % (k, r[k]))
        print()
    print('转正：python scripts/kb.py promote <id>    丢弃：python scripts/kb.py drop <id>')


def cmd_promote(a):
    f, r = find_by_id(a.id)
    if not f or f != F_CAN:
        print('[ X ] 候选区里没有 %s' % a.id)
        sys.exit(2)
    rows = load(F_CAN)
    rows = [x for x in rows if x.get('id') != a.id]
    rewrite(F_CAN, rows)
    kind = r.get('kind', 'pitfall')
    new_id = next_id('K' if kind == 'pitfall' else 'P')
    r['id'] = new_id
    r['status'] = 'active'
    r['hit'] = 0
    if kind == 'pitfall':
        r.setdefault('last', today())
        append(F_PIT, r)
    else:
        append(F_PREF, r)
    print('[ OK ] %s → %s 已转正' % (a.id, new_id))


def cmd_drop(a):
    rows = load(F_CAN)
    keep = [x for x in rows if x.get('id') != a.id]
    if len(keep) == len(rows):
        print('[ X ] 候选区里没有 %s' % a.id)
        sys.exit(2)
    rewrite(F_CAN, keep)
    print('[ OK ] 已丢弃 %s' % a.id)


def cmd_gc(a):
    rows = load(F_PIT)
    cutoff = (datetime.date.today() - datetime.timedelta(days=STALE_DAYS)).isoformat()
    stale, dup = [], []
    seen = {}
    for r in rows:
        if r.get('status') == 'active' and r.get('last', '') and r['last'] < cutoff and not r.get('hit'):
            stale.append(r['id'])
        key = tuple(sorted(r.get('tags') or []))
        if key and key in seen:
            dup.append((seen[key], r['id']))
        seen[key] = r['id']
    print('检查 %d 条坑点：' % len(rows))
    print('  超 %d 天未被踩：%s' % (STALE_DAYS, ', '.join(stale) or '无'))
    print('  tag 完全相同（疑似重复）：%s' % (
        '; '.join('%s=%s' % x for x in dup) or '无'))
    if a.apply:
        for r in rows:
            if r['id'] in stale:
                r['status'] = 'archived'
        rewrite(F_PIT, rows)
        print('  已把超期条目标为 archived（没有删除，随时可恢复）')
    else:
        print('\n只报告，不动手。要执行加 --apply')


def cmd_stats(a):
    pits = load(F_PIT)
    print('热层      %s' % ('有' if os.path.exists(d(F_BOOK)) else '缺'))
    print('坑点      %d 条（active %d）' % (
        len(pits), len([r for r in pits if r.get('status') == 'active'])))
    print('偏好      %d 条' % len(load(F_PREF)))
    print('对话索引  %d 条' % len(load(F_IDX)))
    print('候选      %d 条' % len(load(F_CAN)))
    if pits:
        tags = {}
        for r in pits:
            for t in (r.get('tags') or []):
                tags[t] = tags.get(t, 0) + 1
        top = sorted(tags.items(), key=lambda x: -x[1])[:8]
        print('高频 tag  %s' % ', '.join('%s(%d)' % t for t in top))
