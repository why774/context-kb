# -*- coding: utf-8 -*-
"""检索：主题检索 / 时间检索 / 总检索 / 原文下探"""
from .base import *  # noqa: F401,F403
from .topics import *  # noqa: F401,F403
from .topics import _print_index_grouped, _print_index_bytime
import io, os, re, sys, json, datetime


def _scan_raw(kws, limit=40):
    """下探原文：搜 archive/ 和 session/ 里每一行。
    多个词时要求**同一行同时包含全部**（交叉），不是任意一个。
    """
    out = []
    lows = [str(k).lower() for k in kws]
    for sd in lib_dirs():
        for f in sorted(os.listdir(sd)):
            if not f.endswith('.md'):
                continue
            p = os.path.join(sd, f)
            with io.open(p, encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    low = line.lower()
                    if all(k in low for k in lows):
                        out.append(('%s/%s' % (os.path.basename(sd), f),
                                    i, line.strip()))
                        if len(out) >= limit:
                            return out
    return out


def _date_bounds(a):
    """把 --day / --since / --until / --days 收成一个区间 (lo, hi, 说明文字)。"""
    lo = hi = None
    try:
        if getattr(a, 'day', None):
            lo = parse_drange(a.day)
            hi = parse_drange(a.day, end=True)
        if getattr(a, 'since', None):
            lo = parse_drange(a.since)
        if getattr(a, 'until', None):
            hi = parse_drange(a.until, end=True)
        if getattr(a, 'days', None):
            hi = datetime.date.today()
            lo = hi - datetime.timedelta(days=max(1, int(a.days)) - 1)
    except ValueError as e:
        sys.exit('[ X ] %s' % e)
    if lo and hi and lo > hi:
        sys.exit('[ X ] 区间反了：%s 比 %s 还晚' % (lo, hi))
    if lo and hi:
        txt = ('%s（只此一天）' % lo if lo == hi
               else '%s ~ %s' % (lo, hi))
    elif lo:
        txt = '%s 起' % lo
    elif hi:
        txt = '截至 %s' % hi
    else:
        txt = '全部时间'
    return lo, hi, txt


def _in_span(r, lo, hi):
    if not lo and not hi:
        return True
    s = row_date(r)
    if not s:
        return False
    try:
        x = datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return False
    return (lo is None or x >= lo) and (hi is None or x <= hi)


def cmd_when(a):
    """时间检索：不按词，按日期翻。总检索本来就是按时间排的，所以这里直接摊时间轴。"""
    lo, hi, txt = _date_bounds(a)
    print('（时间检索：%s，倒序，最新在上）' % txt)

    # ── 喂哪个库的数据给工具 ──
    # 工具只做「排列」这一件事：喂当前库就排当前的，喂长期库就排长期的。
    # 默认喂短期库；--long 喂长期库（用户明确要「别的对话的资料」时才用）。
    lib = 'long' if getattr(a, 'long', False) else 'short'
    if not lib_exists(lib):
        print('[ X ] %s库不存在。先建：python scripts/kb.py init%s'
              % ('长期' if lib == 'long' else '短期',
                 ' --long' if lib == 'long' else ''))
        sys.exit(2)
    if lib == 'long':
        print('（喂的是【长期库】的数据——跨所有对话的资料）')
    words = [w for w in (a.keyword or []) if w.strip()]
    # 关键词里如果写了符号或组名 → 那就是「时间 × 组」的真交叉
    groups = []
    for w in list(words):
        g = match_group(w, lib)
        if g:
            groups.append(g[0])
            words.remove(w)
    if groups:
        print('（组交叉：%s —— 只要这些组里的）' % ' + '.join(groups))
    print('（关键词：%s —— 要求同时命中）' % ' + '.join(words) if words
          else '（不给词就是纯翻时间轴）')

    idx = [r for r in load(F_IDX, lib) if _in_span(r, lo, hi)]
    if groups:
        idx = [r for r in idx
               if str(r.get('sym') or '') in groups
               or sym_name(r.get('sym')) in
               [sym_name(g) for g in groups]]
    if words:
        def kw_ok(r):
            return all(hit(r, w) for w in words)
        idx = [r for r in idx if kw_ok(r)]
    idx.sort(key=lambda r: row_date(r), reverse=True)
    _print_index_bytime(idx)

    # 坑点 / 偏好 / 会话摘要也跟着筛，别只给索引层
    for label, f in (('坑点', F_PIT), ('偏好', F_PREF), ('会话摘要', F_DIG)):
        rows = [r for r in load(f, lib) if _in_span(r, lo, hi)]
        if words:
            rows = [r for r in rows if all(hit(r, w) for w in words)]
        if not rows:
            continue
        rows.sort(key=row_date, reverse=True)
        print('\n--- %s（%d 条）---' % (label, len(rows)))
        for r in rows:
            if f == F_PIT:
                print(fmt_pit(r))
            elif f == F_PREF:
                print('[%s] [%s] %s' % (r['id'], row_date(r), r.get('text', '')))
            else:
                print('[%s] [%s] %s' % (r.get('sid', ''), row_date(r),
                                        r.get('text', '')))
        if f == F_PIT:
            bump_pits(rows, lib)   # 真被翻出来看过 → hit+1、last=今天（gc 的依据）

    n = len(idx)
    if not n:
        print('\n这个时间段里没有记录。换个月份试试，或先 kb.py log 存过东西。')
    else:
        print('\n时间段内共 %d 条索引。要看某一条的原文：'
              'python scripts/kb.py read <坐标>' % n)
        hot_groups = crowded_groups(idx)
        if hot_groups:
            print('（这几个前缀到预警线了，该做拥挤测试：%s）'
                  % '、'.join('%s %d 条 线%d' % (k, v, th)
                            for k, v, th in hot_groups[:3]))


def crowded_groups(rows):
    """哪些前缀到了预警线。

    判据是「单个叶子前缀的条数」，不是一级前缀、也不是总命中数：
    · 搜一个泛词命中 40 条、分散在 10 个主题上，每个 4 条 —— 翻起来不慢。
    · 一级前缀 800 条但拆成了 40 个子主题各 20 条 —— 翻起来也不慢，
      因为分组显示时本来就是一节一节看的。
    · 真正的信号是「某一节自己就很长」——那就是没拆干净。

    阈值按层数递减（单前缀宽、多层紧），所以这里逐个前缀算自己的线。

    **到线只是预警，不是禁止**：程序告诉 AI「这个前缀到线了，该做拥挤测试了」，
    超不超、拆不拆，全由 AI 看完内容自己定。
    """
    c = {}
    for r in rows:
        k = row_topic(r)
        if k:
            c[k] = c.get(k, 0) + 1
    g = []
    for k, v in c.items():
        # 层级看组名（符号表里映射的名字，可能带 / 表示子组）
        th = hot_threshold(sym_name(k) or k)
        if v >= th:
            g.append((k, v, th))
    return sorted(g, key=lambda x: (-x[1], x[0]))

def cmd_search(a):
    """支持多个词：多个词之间是 AND（交叉），每条必须同时命中全部。"""
    # ── 喂哪个库的数据给工具 ──
    # 工具只做「排列」这一件事：喂当前库就排当前的，喂长期库就排长期的。
    # 默认喂短期库；--long 喂长期库（用户明确要「别的对话的资料」时才用）。
    lib = 'long' if getattr(a, 'long', False) else 'short'
    if not lib_exists(lib):
        print('[ X ] %s库不存在。先建：python scripts/kb.py init%s'
              % ('长期' if lib == 'long' else '短期',
                 ' --long' if lib == 'long' else ''))
        sys.exit(2)
    if lib == 'long':
        print('（喂的是【长期库】的数据——跨所有对话的资料）')
    words = a.keyword
    if isinstance(words, str):
        words = [words]

    # 每个词各自展开成"该词 + 它命中的组（符号 + 组名）"
    variants, tops = [], []
    for w in words:
        vs = [w]
        g = match_group(w, lib)
        if g:
            sym, name = g
            for x in (sym, name):
                if str(x).lower() != w.lower() and x not in vs:
                    vs.append(str(x))
            tops.append({'name': name, 'sym': sym})
            print('（「%s」命中组「%s %s」）' % (w, sym, name))
        variants.append(vs)

    if len(words) > 1:
        print('（交叉检索：%s —— 要求同时命中）' % ' + '.join(words))

    def keep(r):
        return all(any(hit(r, v) for v in vs) for vs in variants)

    total = 0
    # 顺序即优先级：索引（细）→ 会话摘要（粗）→ 经验 → 原文
    for label, f in (('索引', F_IDX), ('会话摘要', F_DIG), ('坑点', F_PIT),
                     ('偏好', F_PREF), ('候选', F_CAN)):
        rows = [r for r in load(f, lib) if keep(r)]
        if not rows:
            continue
        total += len(rows)
        if f == F_IDX:
            hot_groups = crowded_groups(rows)
            _print_index_grouped(rows, tops[0] if tops else None, words=words)
            if hot_groups:
                print('\n  （这些前缀到预警线了，该做拥挤测试——'
                      '搜一下看翻起来挤不挤：）')
                for name, cnt, th in hot_groups:
                    print('     %s：%d 条（线 %d）' % (name, cnt, th))
            continue
        print('\n--- %s（%d 条）---' % (label, len(rows)))
        for r in rows:
            if f == F_PIT:
                print(fmt_pit(r))
            elif f == F_PREF:
                print('[%s] %s   (tag: %s)' % (
                    r['id'], r.get('text', ''), '/'.join(r.get('tags') or [])))
            elif f == F_DIG:
                print('[%s] %s' % (r.get('sid', ''), r.get('text', '')))
                print('     整场原文：kb.py session %s' % r.get('sid', ''))
            else:
                print('[候选 %s] %s' % (r['id'],
                                      json.dumps(r, ensure_ascii=False)[:120]))
        if f == F_PIT:
            bump_pits(rows, lib)   # 真被翻出来看过 → hit+1、last=今天（gc 的依据）

    # 索引层没命中 → 自动下探原文（不用记参数）
    if not total or a.deep:
        hits = _scan_raw(words, a.limit)
        if hits:
            print('\n--- 原文正文（%d 处命中）---' % len(hits))
            for fn, ln, txt in hits:
                print('  %s:%d' % (fn, ln))
                print('      %s' % txt[:140])
            print('\n看某处前后文：python scripts/kb.py read %s:%d' % (hits[0][0], hits[0][1]))
            total += len(hits)
        elif not total:
            print('索引层和原文里都没有「%s」。' % ' + '.join(words))
            print('提示：换成症状词再试（"不生效" "报错" "乱码"）；多词表示"同时满足"，词太多会搜不到。')
            sys.exit(1)


def cmd_read(a):
    """按坐标读原文，支持三种写法：
        read archive/S-xxx-p1.md:47      那一行前后各 5 行
        read archive/S-xxx-p1.md:5-12    就读 5~12 行（索引里的精确指向）
        read S-xxx-p1:5-12               段名也行，自动补目录
    """
    loc = a.loc
    if ':' not in loc:
        print('[ X ] 坐标要写成 文件:行 或 文件:起-止，例如 archive/S-20261019-001-p3.md:47')
        sys.exit(2)
    fn, rng = loc.rsplit(':', 1)
    fn = fn.replace('\\', '/').lstrip('/')
    if fn.endswith('.md'):
        fn = fn.rsplit('/', 1)[-1][:-3]

    p = find_seg(fn)
    if not p:
        print('[ X ] 找不到段 %s，先跑 kb.py session 看看有哪些' % fn)
        sys.exit(2)

    try:
        if '-' in rng:
            s, e = [int(x) for x in rng.split('-', 1)]
        else:
            n = int(rng)
            s, e = n - a.around, n + a.around
    except ValueError:
        print('[ X ] 行号写错了：%s（要 47 或 5-12）' % rng)
        sys.exit(2)

    with io.open(p, encoding='utf-8') as f:
        lines = f.read().split('\n')
    s = max(1, s)
    e = min(len(lines), e)
    print('%s  第 %d~%d 行（共 %d 行）' % (fn, s, e, len(lines)))
    print('')
    for i in range(s, e + 1):
        print('%4d | %s' % (i, lines[i - 1]))
