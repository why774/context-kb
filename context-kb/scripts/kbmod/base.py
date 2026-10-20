# -*- coding: utf-8 -*-
"""常量 / 路径 / 读写 / 匹配 / 坐标 —— 底层，谁都依赖它"""

import io, os, re, sys, json, datetime

# 被重定向到管道/文件时统一用 UTF-8（终端里保持平台默认，交给控制台自己显示）
if hasattr(sys.stdout, 'reconfigure') and not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding='utf-8')

# ── 库定位 ──
# 短期库：**每开一场对话就建一个**（多开并存），功能跟长期库一样
#   .context-kb/talks/<对话id>/  ← 一场对话 = 一个短期库
#   .context-kb/current         ← 记着当前是哪场
# 长期库：全局唯一，跨所有对话
KB_SHORT = '.context-kb'                    # 短期库容器（当前目录）
KB_LONG = os.path.join(os.path.expanduser('~'), '.context-kb')   # 长期库（全局）
KB = KB_SHORT                               # 当前操作的库（可切换）
LIB = 'short'                               # 当前在长期库还是短期库：short / long
DIR_TALK = 'talks'                          # 短期库容器里的：各场对话
F_CUR = 'current'                           # 记当前是哪场对话

STALE_DAYS = 180          # 超过这么久没被踩到，gc 时降级

F_PIT = 'pitfalls.jsonl'
F_PREF = 'prefs.jsonl'
F_IDX = 'index.jsonl'
F_CAN = 'candidates.jsonl'
F_DIG = 'digests.jsonl'    # 会话级摘要：一场对话干了什么
F_SUM = 'summaries.jsonl'  # 段级摘要：每个话题段压一小段（分级压缩用）
F_SYM = 'symbols.jsonl'   # 前缀表：一个符号 = 一个组（sym + name + desc）
F_GROW = 'growth.jsonl'    # 工具/操作经验：这个工具怎么用才对（长期层）
F_BOOK = 'hot.md'
F_META = 'meta.json'
DIR_SESS = 'session'
DIR_ARCH = 'archive'      # 长期层的原文归档：任务结束后从 session 移过来

MAX_RAW_LINES = 400       # 单个会话原文超过这个行数就提示该 close 了


def d(name):
    """当前库里的某个文件/目录的完整路径。

    短期库时，路径落在**当前那场对话**的目录里：
    .context-kb/talks/S-20261020-001/index.jsonl
    """
    if LIB == 'short' and not os.path.isabs(KB):
        return os.path.join(KB, DIR_TALK, cur_talk_id(), name)
    return os.path.join(KB, name)


def cur_talk_id():
    """当前是哪场对话（读 .context-kb/current）。没有就返回空。"""
    p = os.path.join(KB_SHORT, F_CUR)
    try:
        with io.open(p, encoding='utf-8') as f:
            return f.read().strip()
    except IOError:
        return ''


def set_cur_talk(tid):
    """把当前对话指到某场。"""
    os.makedirs(KB_SHORT, exist_ok=True)
    with io.open(os.path.join(KB_SHORT, F_CUR), 'w', encoding='utf-8',
                 newline='\n') as f:
        f.write(tid)


def talk_dir(tid):
    """某场对话的短期库目录。"""
    return os.path.join(KB_SHORT, DIR_TALK, tid)


def ensure_talk():
    """确保当前有一场对话的短期库；没有就建一个（并指为当前）。"""
    tid = cur_talk_id()
    if tid and os.path.isdir(talk_dir(tid)):
        return tid
    # 借 write 模块建库（避免循环导入，这里只做最小的事）
    from .write import cur_segment
    tid, part, p = cur_segment()
    return tid


def list_talks():
    """所有短期库（各场对话），按时间倒序。"""
    root = os.path.join(KB_SHORT, DIR_TALK)
    if not os.path.isdir(root):
        return []
    out = []
    for fn in os.listdir(root):
        p = os.path.join(root, fn)
        if os.path.isdir(p):
            out.append(fn)
    return sorted(out, reverse=True)


def use_lib(which):
    """切换当前操作的库：'short'（项目自己的）或 'long'（全局长期库）。"""
    global KB, LIB
    LIB = 'long' if which == 'long' else 'short'
    KB = KB_LONG if LIB == 'long' else KB_SHORT
    return KB


def lib_path(which):
    """某个库的位置（不切换当前）。"""
    return KB_LONG if which == 'long' else KB_SHORT


def lib_root(which=None):
    """某个库的数据根目录（文件**实际落在**哪）。

    短期库的正文全在当前那场对话的目录里（跟 d() 一个口径）：
    .context-kb/talks/<对话id>/；长期库直接在库根。
    唯一例外是前缀表，它放容器根（项目级共用，见 load()）。
    """
    which = which or LIB
    if which == 'long':
        return KB_LONG
    tid = cur_talk_id()
    return talk_dir(tid) if tid else os.path.join(KB_SHORT, DIR_TALK)


def lib_dirs(which=None):
    """某个库里所有「段目录」（session / archive 的实际位置）。

    短期库的正文在 .context-kb/talks/<对话id>/ 下（跟 d()、lib_root() 一个口径），
    容器根也带上兜底——兼容早期版本留下的旧数据。
    """
    which = which or LIB
    roots = [lib_root(which)]
    if which == 'short':
        roots.append(KB_SHORT)
    out = []
    for root in roots:
        for sub in (DIR_SESS, DIR_ARCH):
            sd = os.path.join(root, sub)
            if sd not in out and os.path.isdir(sd):
                out.append(sd)
    return out


def find_seg(ref, which=None):
    """段名 → 段文件的实际路径；找不到返回 None。

    ref 可以带目录前缀（archive/S-...），也可以只有段名。
    """
    ref = str(ref or '').strip().replace('\\', '/')
    if not ref:
        return None
    ref = ref.rsplit('/', 1)[-1]
    dirs = lib_dirs(which)
    if which is None and LIB != 'long':
        dirs += [x for x in lib_dirs('long') if x not in dirs]
    for sd in dirs:
        p = os.path.join(sd, ref + '.md')
        if os.path.exists(p):
            return p
    return None


def seg_is_arch(sd):
    """这个段目录是不是归档目录。"""
    return os.path.basename(os.path.normpath(sd)) == DIR_ARCH


def both_libs():
    """两个库的位置，长期库不存在时跳过。"""
    out = [('short', KB_SHORT)]
    if os.path.isdir(KB_LONG):
        out.append(('long', KB_LONG))
    return out


def pick_libs(a):
    """决定这次查哪个库。

    **默认只查短期库**。长期库是「别的对话」的东西，
    只有当用户明确说了要别的对话/以前/别的项目里的资料，才加 --long。
    """
    if getattr(a, 'long', False):
        return ['long']
    return ['short']


def lib_exists(which):
    return os.path.isdir(lib_path(which))


def now_hm():
    return datetime.datetime.now().strftime('%H:%M')


def today():
    return datetime.date.today().isoformat()


def _mdays(y, m):
    """那个月有多少天（闰年也对）。"""
    nxt = datetime.date(y + (m == 12), (m % 12) + 1, 1)
    return (nxt - datetime.date(y, m, 1)).days


def parse_drange(s, end=False):
    """把'2026' / '2026-10' / '2026-10-15' 解析成一个日期区间的某一端。

    end=False → 取区间头；end=True → 取区间尾（把当月补到最后一天）。
    只写年 → 1月1日～12月31日；只写年月 → 当月1日～当月末日。
    """
    s = (s or '').strip().replace('/', '-').replace('.', '-')
    s = s.replace('年', '-').replace('月', '-').replace('日', '')
    if s.endswith('-'):
        s = s[:-1]
    parts = [p for p in s.split('-') if p != '']
    if not parts:
        raise ValueError('空日期')
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        dd = int(parts[2]) if len(parts) > 2 else 1
    except ValueError:
        raise ValueError('看不懂的日期：%s（请写 2026 / 2026-10 / 2026-10-15）' % s)
    if not (1 <= m <= 12):
        raise ValueError('月份不对：%s' % s)
    last = _mdays(y, m)
    if dd < 1 or dd > last:
        raise ValueError('日期不对：%s（当月只有 %d 天）' % (s, last))
    if end and len(parts) == 1:
        return datetime.date(y, 12, 31)
    if end and len(parts) == 2:
        return datetime.date(y, m, last)
    return datetime.date(y, m, dd)


def row_date(r):
    """一条记录的时间。不同表叫法不一样，这里统一。"""
    for k in ('date', 'last', 'since', 'ts'):
        v = str(r.get(k) or '')
        if v:
            return v[:10]
    m = re.search(r'S-(\d{8})-', str(r.get('sid') or ''))
    return ('%s-%s-%s' % (m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:8])
            if m else '')


def load(name, lib=None):
    """读某个库里的一个数据文件。

    lib=None → 当前库；'short' → 项目短期库；'long' → 全局长期库。
    **工具只做「排列」这一件事——喂哪个库的数据，它就排哪个库的。**
    """
    which = lib or LIB
    if which == 'short' and name == F_SYM:
        root = KB_SHORT          # 前缀表：项目级共用，放在容器根
    else:
        root = lib_root(which)
    p = os.path.join(root, name)
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


def append(name, obj):
    with io.open(d(name), 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def rewrite(name, rows):
    with io.open(d(name), 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def bump_pits(rows, lib=None):
    """坑点被检索真正命中一次 → hit+1、last=今天。

    就写回「读它的那个文件」（跟 load 同口径），不新建文件；其它行的字段原样保留。
    这是 gc 判「有没有长期没被用到」的依据：只有真的检索命中过才算被用到。
    返回这次刷新了几条。
    """
    ids = [r.get('id') for r in (rows or []) if r.get('id')]
    if not ids:
        return 0
    p = os.path.join(lib_root(lib), F_PIT)
    if not os.path.exists(p):
        return 0
    all_rows = []
    with io.open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    all_rows.append(json.loads(line))
                except ValueError:
                    pass
    want, n = set(ids), 0
    day = today()
    for r in all_rows:
        if r.get('id') in want:
            r['hit'] = int(r.get('hit') or 0) + 1
            r['last'] = day
            n += 1
    if n:
        with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
            for r in all_rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return n


# meta 分两处：
#   容器级 .context-kb/meta.json      → 编号计数器（全局，对话 id 不能重复）
#   对话级 talks/<id>/talk.json      → 这场对话的状态（当前第几段、封没封）
F_TALK = 'talk.json'


def meta_read():
    """读全局编号计数器。"""
    p = os.path.join(KB_SHORT if LIB == 'short' else KB_LONG, F_META)
    if os.path.exists(p):
        with io.open(p, encoding='utf-8') as f:
            return json.load(f)
    return {'seq': {'K': 0, 'P': 0, 'C': 0, 'T': 0}, 'day': ''}


def meta_write(m):
    root = KB_SHORT if LIB == 'short' else KB_LONG
    os.makedirs(root, exist_ok=True)
    with io.open(os.path.join(root, F_META), 'w', encoding='utf-8',
                 newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def talk_read():
    """读当前对话的状态。"""
    p = os.path.join(talk_dir(cur_talk_id()), F_TALK) if cur_talk_id() else ''
    if p and os.path.exists(p):
        with io.open(p, encoding='utf-8') as f:
            return json.load(f)
    return {'cur_part': 1, 'cur_closed': False}


def talk_write(m):
    tid = cur_talk_id()
    if not tid:
        return
    p = talk_dir(tid)
    os.makedirs(p, exist_ok=True)
    with io.open(os.path.join(p, F_TALK), 'w', encoding='utf-8',
                 newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def next_id(prefix):
    """编号永不复用：只递增，不回收。
    T = 对话（短期库目录名）· C = 对话索引（两者都带日期，各自独立计数）
    K = 坑点，P = 偏好（全局递增）
    """
    m = meta_read()
    if prefix in ('C', 'T'):
        day = datetime.date.today().strftime('%Y%m%d')
        dk = 'day_' + prefix
        if m.get(dk) != day:
            m[dk] = day
            m['seq'][prefix] = 0
        m['seq'][prefix] = m['seq'].get(prefix, 0) + 1
        n = m['seq'][prefix]
        meta_write(m)
        return '%s-%s-%03d' % (prefix, day, n)
    m['seq'][prefix] = m['seq'].get(prefix, 0) + 1
    n = m['seq'][prefix]
    meta_write(m)
    return '%s-%03d' % (prefix, n)


def find_by_id(rid):
    for f in (F_PIT, F_PREF, F_IDX, F_CAN):
        for r in load(f):
            if r.get('id') == rid:
                return f, r
    return None, None


def load_symbols(lib=None):
    """符号表 = 前缀清单。返回 {符号: {name, desc}}。

    **两个库共用一张前缀表**——长期库那张是权威的，短期库直接读它。
    这样同一个符号在两边含义一致，合并时才不会打架。
    长期库还没有前缀表时，才用自己的。

    **一行就是一个前缀**：符号 + 它代表的种类 + 一句说明。
    AI 查这张表就知道「$ 是什么」「! 是什么」，据此给检索挑前缀。
    """
    if lib is None:
        # 默认：优先读长期库的（权威），没有再读当前的
        rows = load(F_SYM, 'long')
        if not rows:
            rows = load(F_SYM, 'short')
    else:
        rows = load(F_SYM, lib)
        if lib == 'short' and not rows:
            rows = load(F_SYM, 'long')
    out = {}
    for r in rows:
        s = str(r.get('sym') or '').strip()
        if s:
            out[s] = {'name': str(r.get('name') or '').strip(),
                      'desc': str(r.get('desc') or '').strip()}
    return out


def sym_name(sym):
    """符号 → 它的名字。"""
    return load_symbols().get(str(sym or '').strip(), {}).get('name', '')


# 中文停用词（做词频时滤掉）——按词算，不是按字
CN_STOP_W = set('''
的 了 是 在 和 就 都 而 及 与 也 很 不 有 我 你 他 她 它 们 这 那 些 个
我们 你们 他们 咱们 自己 什么 怎么 怎样 为什么 因为 所以 但是 但如果 如果说
一个 一些 一下 一点 这种 那个 这个 这些 那些 这样 那样 时候 地方 事情 问题
可以 应该 必须 需要 不能 不会 不是 没有 就是 还是 已经 正在 一直 比较 非常
真的 好像 似乎 感觉 觉得 知道 看到 听到 说到 想到 看到 现在 刚才 前面 后面
然后 就是 还是 或者 而且 并且 虽然 然而 因此 于是 关于 对于 根据 按照 通过
用 做 说 看 想 写 改 试 试过 试了 加 删 查 找 问 答 记 存 放 拿 传
情况 结果 内容 方式 办法 东西 时候 部分 上面 下面 里面 外面 中间 开始 结束
'''.split())


def _name_hit(v, kw):
    """归属名精确匹配：词 == 名字，或词是'父/子'里的某一级。

    不靠字面包含——搜「白名单」不该命中「白名单校验」。
    """
    v = str(v or '').strip()
    if not v:
        return False
    if v.lower() == kw:
        return True
    parts = [p.strip().lower() for p in v.split('/') if p.strip()]
    return kw in parts


def hit(r, kw):
    kw = kw.lower()
    # 正文类字段：包含就算命中（用户在找的是内容里的词）
    for k in ('id', 'sid', 'title', 'symptom', 'cause', 'fix', 'text', 'gist',
              'ref', 'status'):
        v = r.get(k)
        if isinstance(v, str) and kw in v.lower():
            return True
    # 归属名：精确匹配（一一对应）
    if _name_hit(r.get('topic'), kw):
        return True
    # 符号：搜 '$' 或搜它映射的组名（'代码'）都能命中这个组
    sv = str(r.get('sym') or '').strip()
    if sv:
        if sv.lower() == kw:
            return True
        nm = sym_name(sv)
        if nm and nm.lower() == kw:
            return True
        if _name_hit(nm, kw):
            return True
    for t in (r.get('tags') or []):
        if _name_hit(t, kw):
            return True
    for sub in (r.get('subs') or []):
        s = str(sub)
        if kw in s.lower():
            return True
    return False


def fmt_pit(r):
    s = '[%s] %s\n' % (r['id'], r.get('title', ''))
    if r.get('symptom'):
        s += '   症状：%s\n' % r['symptom']
    if r.get('cause'):
        s += '   根因：%s\n' % r['cause']
    if r.get('fix'):
        s += '   解法：%s\n' % r['fix']
    if r.get('tags'):
        s += '   tag：%s\n' % ' / '.join(r['tags'])
    if r.get('files'):
        s += '   文件：%s\n' % ' / '.join(r['files'])
    extra = []
    if r.get('hit'):
        extra.append('踩过 %d 次' % r['hit'])
    if r.get('status') and r['status'] != 'active':
        extra.append(r['status'])
    if extra:
        s += '   (%s)\n' % ' · '.join(extra)
    return s


def ref_to_path(ref, lines=''):
    """段名 → 可读坐标。S-xxx-p1 → archive/S-xxx-p1.md，带 lines 就拼成 :5-12"""
    ref = str(ref or '').strip()
    if not ref:
        return ''
    tail = (':' + lines) if lines else ''
    p = find_seg(ref)
    if p:
        sub_ = os.path.basename(os.path.dirname(p))
        return '%s/%s.md%s' % (sub_, ref, tail)
    return ref + tail


def _looks_like_code(text):
    """粗判：这段是不是代码。是的话要保留缩进，不能压成一行。

    判断依据按可靠度排（宁可漏判不可误判——误判会把普通句子包成围栏）：
    · 有 ``` 围栏 → 一定是
    · 有明确的关键字+括号组合：def xxx( / class xxx( / function xxx(
    · Python 风格：多行 + 缩进 + 冒号结尾
    · C/JS 风格：多行 + 大括号成对
    """
    t = text or ''
    if '```' in t:
        return True
    lines = [l for l in t.split('\n') if l.strip()]

    # 关键字后面紧跟标识符和括号，才算函数/类定义
    if re.search(r'\b(def|class|func|function|struct|interface|enum)\s+'
                 r'[A-Za-z_$][\w$]*\s*[\(<]', t):
        return True
    if re.search(r'^\s*(public|private|protected|static|void|int|char|bool|'
                 r'float|double|long|short)\s+\w+\s+\w+\s*[\(=]', t, re.M):
        return True
    if re.search(r'(#include|#!/|<\?php|<\/?[a-z]+>)', t):
        return True
    if len(lines) >= 2:
        # Python 风格：缩进 + 冒号结尾
        if any(l.startswith((' ', '\t')) for l in lines) \
                and any(l.rstrip().endswith(':') for l in lines):
            return True
        # C/JS 风格：大括号成对
        if t.count('{') >= 1 and t.count('}') >= 1:
            return True
        # 赋值/调用行：x = y(  或  obj.method(
        if sum(1 for l in lines
               if re.search(r'[=\-+*/]\s*[\w\.]+\s*\(', l)
               or re.search(r'^\s*[\w\.]+\s*\(', l)) >= 2:
            return True
    return False


def segment_has_code(ref, lines=''):
    """这条索引指向的地方有没有代码。

    判断依据是**它指到的那几行**（--lines），不是整段——
    一段里既有代码又有结论很正常，整段判断会把结论也误标成代码。
    没指定 lines 就看整段。
    """
    ref = str(ref or '').strip()
    if not ref:
        return False
    p = find_seg(ref)
    if p:
        with io.open(p, encoding='utf-8') as f:
            txt = f.read()
        if not lines:
            # 没指明行 → 只看 gist 自己的判断，不扫整段
            # （整段可能混着代码和结论，一刀切会误标）
            return False
        # 只看指到的那几行
        a, b = 1, 10 ** 9
        m = re.match(r'^\s*(\d+)', str(lines))
        if m:
            a = int(m.group(1))
        m2 = re.search(r'(\d+)\s*$', str(lines))
        if m2:
            b = int(m2.group(1))
        picked = '\n'.join(txt.split('\n')[a - 1:b])
        if not picked.strip():
            return False
        return '```' in picked or _looks_like_code(picked)
    return False


def hot_threshold(topic=''):
    """预警线：某个前缀挂到多少条，就该提醒 AI 做一次拥挤测试。

    **它是预警，不是上限。** 到了这条线，程序只负责告诉 AI
    「这个前缀到线了，去搜一下看翻起来挤不挤」——
    超不超、拆不拆、往哪拆，全由 AI 看完内容自己定。程序不禁止任何写入。

    这个数不是「上下文装得下多少」——库大到几千条也照样装得下。
    它量的是「结果能不能被认真看完」：每多一条，AI 就得多做一次
    「这条跟我要的相不相关」的判断；条数一多就会开始跳着看，
    跳了等于没搜到，而且 AI 不会告诉你它跳过了。

    实测出来的（造了 11 种库形态跑对比，见 SKILL.md 4.6）：
    · 阈值不该跟「全库多大」成正比。翻结果慢不慢，取决于这一坨有多少条，
      不取决于库里还有多少别的东西。库大只是让人更容易忽略这点。
    · 所以 √N×1.5 在库大到 1500 条时阈值涨到 58，真有个前缀挤了 48 条都不报
      ——阈值等于失效。
    · 于是取 sqrt 伸缩但夹在 12~20：库小的时候别太严，库大了也顶住。

    **阈值按前缀层数递减**（用户定的规矩）：
        单前缀 → 双前缀 ×0.7 → 三前缀 ×0.5 → 四层以上 ×0.35，下限 5
    理由：拆得越深，说明这个主题内容越多、还应该再细分。
    都拆到三层了还挂 20 条，那是拆得不够狠；单前缀才 8 条就拆，没必要。
    """
    n = len(load(F_IDX))
    base = max(12, min(20, int((n ** 0.5) * 1.2)))
    level = len([x for x in str(topic or '').split('/') if x.strip()])
    if level <= 1:
        return base
    ratio = (0.7, 0.5, 0.35)[min(level, 4) - 2]
    return max(5, int(base * ratio))

