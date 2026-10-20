# -*- coding: utf-8 -*-
"""主题层：前缀切分 / 主题匹配 / 分组显示 / 词频给方向"""
from .base import *  # noqa: F401,F403
from .base import CN_STOP_W
import io, os, re, sys, json, datetime
from collections import Counter


def _tag_hit(r, key, words):
    """这个归属 key 是不是被搜到的词**准确**命中的。

    规矩：一一对应才算命中，不靠字面包含。
    · 词 == key（'白名单' 命中 '白名单'）→ 命中
    · key 按 '/' 拆开，词是其中某一级（'原理' 命中 '压缩/原理'）→ 命中
    · '白名单' 命中 '白名单校验'？→ **不命中**。字面沾边不算。
    """
    kl = str(key).strip()
    kparts = [p.strip() for p in kl.split('/') if p.strip()]
    for w in words:
        wl = str(w).strip()
        if not wl:
            continue
        if wl.lower() == kl.lower():
            return True
        if wl.lower() in [p.lower() for p in kparts]:
            return True
    return False


def _pick_hit_keys(r, keys, words):
    """一条有多个归属时，挑最精确的那个来显示。

    '白名单' 和 '白名单校验' 都被搜到时，只显示 '白名单'——
    否则同一条会在两个组里各出现一次，看着像两条。
    """
    hit = [k for k in keys if _tag_hit(r, k, words)]
    if not hit:
        return keys[:1]
    # 精确匹配优先（key == 词），其次短的优先
    exact = [k for k in hit if str(k).lower() in
             [str(w).lower() for w in words]]
    pool = exact or hit
    return [sorted(pool, key=len)[0]]


def _print_index_grouped(rows, tp=None, bytime=False, words=None):
    """检索命中后，按**组**（符号）分组显示。

    一个组 = 一个符号 = 一组同前缀的索引。组名来自符号映射。
    """
    if bytime:
        _print_index_bytime(rows)
        return
    syms = load_symbols()
    groups, nohead = {}, []
    for r in rows:
        sym = str(r.get('sym') or '').strip()
        if sym:
            groups.setdefault(sym, []).append(r)
        else:
            nohead.append(r)

    for sym, items in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        name = syms.get(sym, {}).get('name', '?')
        mark = ''
        if tp and tp.get('name') and tp['name'] != name:
            mark = ' · 命中组「%s」' % tp['name']
        print('')
        print('  [组] %s %s（%d 条）%s' % (sym, name, len(items), mark))
        for r in items:
            print('     %s' % r.get('gist', ''))
            print('        %s -> %s' % (
                r['id'], ref_to_path(r.get('ref', ''), r.get('lines', ''))))

    if nohead:
        print('')
        print('  [未归组] %d 条' % len(nohead))
        for r in nohead:
            print('     %s' % r.get('gist', ''))
            print('        %s -> %s' % (
                r['id'], ref_to_path(r.get('ref', ''), r.get('lines', ''))))


def _print_index_bytime(rows):
    """按日期归组，从新到旧翻——总检索本来就是按时间排的，翻时间段最顺。"""
    days = {}
    for r in rows:
        days.setdefault(row_date(r) or '（无日期）', []).append(r)
    for day in sorted(days, reverse=True):
        items = days[day]
        print('\n  [%s] %d 条' % (day, len(items)))
        for r in items:
            k = row_topic(r)
            lead = ('%s · ' % k) if k else ''
            print('     %s%s' % (lead, r.get('gist', '')))
            print('        %s -> %s' % (
                r['id'], ref_to_path(r.get('ref', ''), r.get('lines', ''))))


# ── 主题层：程序聚类，AI 只负责命名 ────────────────

def split_symbol(gist):
    """把 gist 开头的一个符号剥出来。

    '$白名单：校验必须前置' → ('$', '白名单：校验必须前置')
    '白名单：校验必须前置'    → ('',  '白名单：校验必须前置')

    符号是**类型维度**（这段是代码/是坑点/是疑问），
    剩下的才是主题名（内容维度）。两层不冲突。
    """
    t = str(gist or '').lstrip()
    if not t:
        return '', ''
    for s in sorted(load_symbols(), key=len, reverse=True):
        if t.startswith(s):
            return s, t[len(s):].lstrip()
    return '', t


def topic_of(gist):
    """从 gist 里抽主题词（兼容老数据）。

    新模型里主题名由**符号映射**给出（见 row_topic），
    gist 只写「符号 + 结论」。这个函数只处理没符号的老格式。
    """
    sym, rest = split_symbol(gist)
    if sym:
        return ''              # 有符号 → 主题名走映射
    m = re.match(r'^\s*([^：:|]{1,30})\s*[：:]', rest or '')
    if not m:
        return ''
    t = m.group(1).strip()
    if re.search(r'[(){};=<>]|^\s*(def|class|function|func|public|private|import|return)\b',
                 t):
        return ''          # 像代码，不认
    return t


def row_topic(r):
    """一条索引的组键 = 它的前缀符号。

    组名（前缀表里的 name）只是给人看的说明，检索靠符号。
    """
    sym = str(r.get('sym') or '').strip()
    if sym:
        return sym
    return str(r.get('topic') or topic_of(r.get('gist', '')) or '')


def match_group(kw, lib=None):
    """查这个字词对应哪个组（符号）。

    两种命中：
    · 符号本身（搜 $ 找到「代码」组）
    · 组名（搜「代码」找到 $ 组）
    返回 (符号, 组名) 或 None。
    """
    low = str(kw or '').strip().lower()
    if not low:
        return None
    for k, v in load_symbols(lib).items():
        nm = v['name'].lower()
        if low == k.lower() or low == nm:
            return k, v['name']
        # 组名带层级时，搜某一级也算命中（'原理' 命中 '压缩/原理'）
        if low in [p.strip().lower() for p in nm.split('/')]:
            return k, v['name']
    return None


def match_topic(kw, lib=None):
    """兼容旧接口：返回 {name, tags} 形式的一行。"""
    g = match_group(kw, lib)
    if not g:
        return None
    sym, name = g
    return {'name': name, 'sym': sym, 'tags': [name, sym]}


def _sync_topics_to_hot():
    """把长期层的东西同步进热层 hot.md。

    热层 = 长期库的记忆，跨所有对话累积：
      · 前缀表   —— 写索引时照着挑前缀
      · 长期经验 —— 踩过的坑的提炼（AI 写的）
      · 工具/操作经验 —— 这个工具怎么用才对
    """
    syms = load_symbols()
    if syms:
        names = '　'.join('%s %s' % (k, v['name']) for k, v in syms.items())
    else:
        names = '（还没有，先 kb.py symbol --add "$" --name "代码"）'
    block = ('## 前缀表（写索引时从这里挑；没有就新建一个组）\n\n'
             '%s\n' % names)

    # 长期经验：active 的坑点，各取一句「标题：解法」
    # 名额 8 席 = 最近记的 4 条（新教训别错过）+ 命中次数最多的 4 条（常用老坑别被挤出）
    pits = [x for x in load(F_PIT, 'long')
            if x.get('status', 'active') == 'active']
    if pits:
        picked, seen = [], set()
        for x in reversed(pits[-4:]):      # 最近 4 条，新的排前面
            if x.get('id') not in seen:
                picked.append(x)
                seen.add(x.get('id'))
        top = sorted([x for x in pits if int(x.get('hit') or 0) > 0],
                     key=lambda x: (int(x.get('hit') or 0), x.get('last') or ''))
        for x in reversed(top):            # 命中最多的 4 条，命中多的排前面
            if len(picked) >= 8:
                break
            if x.get('id') in seen:
                continue
            picked.append(x)
            seen.add(x.get('id'))
        lines = []
        for x in picked:
            t = x.get('title') or ''
            fix = (x.get('fix') or '').strip()
            lines.append('- %s%s' % (t, ('：%s' % fix) if fix else ''))
        block += ('\n## 长期经验（踩过的坑，别再踩）\n\n%s\n'
                  % '\n'.join(lines))

    # 工具/操作经验：怎么用这个工具才对
    grow = load(F_GROW, 'long')
    if grow:
        lines = ['- %s' % x.get('text', '') for x in grow[-8:]]
        block += ('\n## 工具/操作经验（怎么用才对，跨对话累积）\n\n%s\n'
                  % '\n'.join(lines))
    # 同步到长期库的热层（那是权威的那份）
    root = lib_path('long')
    p = os.path.join(root, F_BOOK)
    if not os.path.exists(p):
        return
    with io.open(p, encoding='utf-8') as f:
        txt = f.read()
    key = '## 前缀表'
    if key in txt:
        i = txt.index(key)
        j = txt.find('\n## ', i + len(key))
        j = j if j != -1 else len(txt)
        txt = txt[:i] + block + txt[j:]
    else:
        txt = txt.rstrip() + '\n\n' + block
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)


def cmd_symbol(a):
    """前缀表：符号 + 说明。AI 查这张表就知道每个前缀是什么种类。"""
    syms = load_symbols()

    if a.add:
        s = a.add.strip()
        nm = (a.name or '').strip() or s
        if s in syms:
            print('       前缀「%s」已经有了。' % s)
        else:
            syms[s] = {'name': nm, 'desc': (a.desc or '').strip()}
            # 前缀表是共用的 → 写进长期库（权威的那张）
            root = lib_path('long')
            os.makedirs(root, exist_ok=True)
            p = os.path.join(root, F_SYM)
            with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
                for k, v in syms.items():
                    f.write(json.dumps({'sym': k, 'name': v['name'],
                                        'desc': v['desc'],
                                        'date': today()},
                                       ensure_ascii=False) + '\n')
            _sync_topics_to_hot()
            print('[ OK ] 加了前缀「%s」= %s' % (s, nm))
            print('       往后 gist 开头写「%s」就会归到这个组。' % s)
            print('       已写进长期库的前缀表（两边共用），并同步进 hot.md。')
        return

    if a.remove:
        s = a.remove.strip()
        if s not in syms:
            print('       没有前缀「%s」。' % s)
        else:
            syms.pop(s)
            root = lib_path('long')
            os.makedirs(root, exist_ok=True)
            p = os.path.join(root, F_SYM)
            with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
                for k, v in syms.items():
                    f.write(json.dumps({'sym': k, 'name': v['name'],
                                        'desc': v['desc'],
                                        'date': today()},
                                       ensure_ascii=False) + '\n')
            _sync_topics_to_hot()
            print('[ OK ] 删了前缀「%s」。已有的索引不受影响。' % s)
        return

    print('前缀表（写索引时从这里挑一个）\n')
    if syms:
        for k, v in syms.items():
            print('  %-4s %-10s %s' % (k, v['name'], v['desc']))
    else:
        print('  （还没有）')
    print('\n加前缀：kb.py symbol --add "$" --name "代码" --desc "代码相关"')
    print('删前缀：kb.py symbol --remove "$"')


def cmd_topic(a):
    """看组：一个组 = 一个符号 = 一组同前缀的索引。"""

    def show_group(sym, name, members):
        print('')
        print('「%s」%s（%d 条）' % (sym, name, len(members)))
        for r in members:
            print('   %s' % r.get('gist', ''))
            print('      %s -> %s' % (
                r['id'], ref_to_path(r.get('ref', ''), r.get('lines', ''))))
            for sb in (r.get('subs') or []):
                print('      ├ %s' % sb)

    idx = load(F_IDX)
    syms = load_symbols()

    # --show <组名或符号>：展开那一个组
    if a.show:
        key = a.show.strip()
        sym = key if key in syms else ''
        if not sym:
            for k, v in syms.items():
                if v['name'] == key:
                    sym = k
                    break
        if not sym:
            print('[ X ] 没有这个组：%s' % key)
            print('      现有组：%s'
                  % ('、'.join('%s(%s)' % (k, v['name']) for k, v in syms.items())
                     or '（表是空的）'))
            sys.exit(2)
        members = [r for r in idx if str(r.get('sym') or '') == sym]
        show_group(sym, syms.get(sym, {}).get('name', ''), members)
        if not members:
            print('  （这个组下还没有索引）')
        return

    if not idx:
        print('还没有索引。已建的组：')
        print('')
        if syms:
            for k, v in syms.items():
                print('  %-4s → %-10s %s' % (k, v['name'], v['desc']))
        else:
            print('  （还没建组。先 kb.py symbol --add "$" --name "代码"）')
        return

    # 按组分组：一个组 = 一个符号
    groups = {}
    for r in idx:
        sym = str(r.get('sym') or '').strip()
        if not sym:
            continue
        groups.setdefault(sym, []).append(r)

    print('按组分组（一个组 = 一个符号 = 一组同前缀的索引）：')
    print('')
    for sym, members in sorted(groups.items(),
                               key=lambda x: (-len(x[1]), x[0])):
        show_group(sym, syms.get(sym, {}).get('name', '?'), members)
    orphan = [r for r in idx if not str(r.get('sym') or '').strip()]
    if orphan:
        print('')
        print('没挂符号的 %d 条（程序归不了组，建议补上）：' % len(orphan))
        for r in orphan[:6]:
            print('   %s  %s' % (r['id'], r.get('gist', '')))


def _cn_grams(text, lo=2, hi=4):
    """粗提中文片段（2-4 字），不做分词——够看出高频词就行。"""
    out = []
    for m in re.finditer(r'[\u4e00-\u9fa5]+', text):
        w = m.group(0)
        for n in range(lo, hi + 1):
            for i in range(len(w) - n + 1):
                g = w[i:i + n]
                if g not in CN_STOP_W:
                    out.append(g)
    return out


def cmd_keywords(a):
    """给当前段做词频，帮 AI 定前缀时少读原文。
    先看已登记主题命中几次（最准），再看高频片段（发现新话题用）。
    """
    m = meta_read()
    sid = m.get('cur_session')
    part = m.get('cur_part') or 1
    if not sid:
        print('当前没有进行中的段。')
        return
    p = os.path.join(lib_root('short'), DIR_SESS, '%s-p%d.md' % (sid, part))
    if not os.path.exists(p):
        print('当前段还没有内容。')
        return

    with io.open(p, encoding='utf-8') as f:
        lines = [x for x in f.read().split('\n') if x.startswith('- ')]
    body = '\n'.join(lines)

    print('%s 第 %d 段，%d 条发言\n' % (sid, part, len(lines)))

    print('① 前缀表里的词在这一段里出现过几次（最可靠的依据）：')
    any_hit = False
    for k, v in load_symbols().items():
        n = body.count(v['name']) if v['name'] else 0
        if n:
            any_hit = True
            print('   %-4s %-10s %2d 次   → 前缀「%s」' % (k, v['name'], n, k))
    if not any_hit:
        print('   （一条都没有——这段很可能是新话题）')

    from collections import Counter
    clean = re.sub(r'\[(用户|AI)\]', '', body)      # 去掉说话人标记，否则"用户"永远最高频
    clean = re.sub(r'用户[问说][:：]?', '', clean)   # 去掉"用户问："

    # ② 先看英文/技术词——bat、ps1、CEF 这种经常就是真前缀，比中文碎片靠谱
    print('\n② 英文/技术词（技术类话题的前缀通常就是它）：')
    en = Counter(m.group(0).lower()
                 for m in re.finditer(r'[A-Za-z][A-Za-z0-9_+\-.]{1,19}', clean))
    en = Counter({w: n for w, n in en.items() if n >= 2})
    if en:
        for w, n in en.most_common(6):
            print('   %-10s %2d 次' % (w, n))
    else:
        print('   （这段里没有反复出现的英文词）')

    # ③ 中文片段（发现新话题用）
    c = Counter(_cn_grams(clean))

    # 2 字词要求 ≥3 次（压掉滑窗碎片），3-4 字词 ≥2 次
    cand = sorted([(w, n) for w, n in c.items()
                   if n >= 3],
                  key=lambda x: (-x[1], len(x[0])))
    keep = []
    for w, n in cand:
        if any(w2 != w and w2 in w and n2 >= n for w2, n2 in keep):
            continue
        keep.append((w, n))
        if len(keep) >= 10:
            break

    if keep:
        print('\n③ 中文高频片段（新话题从这儿挑前缀）：')
        for w, n in keep:
            print('   %-10s %2d 次' % (w, n))

    print('\n下一步：挑一个当前缀，配上结论写索引')
    print('  python scripts/kb.py index --gist "前缀：结论" --ref "%s-p%d"' % (sid, part))
