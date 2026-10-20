# -*- coding: utf-8 -*-
"""冒烟测试：用临时目录把主流程跑一遍，不碰真实库。

用法：python tests/smoke_test.py
只用标准库，Windows / macOS / Linux 都能跑。
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / 'scripts' / 'kb.py'
PASS = 0


def ok(name):
    global PASS
    PASS += 1
    print('  [ok] %s' % name)


def run(project, home, *args):
    env = os.environ.copy()
    env['USERPROFILE'] = str(home)
    env['HOME'] = str(home)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, str(KB)] + [str(a) for a in args],
                       cwd=str(project), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    return p.returncode, out


def check(project, home, name, args, must=(), rc_want=0):
    rc, out = run(project, home, *args)
    if rc != rc_want:
        raise AssertionError('%s 退出码 %d（期望 %d）：\n%s' % (name, rc, rc_want, out))
    for m in must:
        if m not in out:
            raise AssertionError('%s 输出里没有 %r：\n%s' % (name, m, out))
    ok(name)
    return out


def main():
    tmp = Path(tempfile.mkdtemp(prefix='kbsmoke-'))
    project = tmp / 'proj'
    home = tmp / 'home'
    project.mkdir()
    home.mkdir()
    try:
        check(project, home, 'init 短期库', ['init'])
        check(project, home, 'init 长期库', ['init', '--long'])
        check(project, home, 'log 用户', ['log', '用户问：为什么测试不生效'])
        check(project, home, 'log AI', ['log', 'AI答：重启一下', '--who', 'AI'])

        # seal 后找到归档的段名
        check(project, home, 'seal', ['seal'], must=('封存',))
        segs = sorted((project / '.context-kb').glob('talks/*/archive/*.md'))
        assert segs, 'seal 之后没有归档段'
        seg = segs[0].stem
        ok('找到段 %s' % seg)

        # P0-bug①：read 能读到短库归档段
        check(project, home, 'read 短库归档段', ['read', seg + ':1'],
              must=('用户问',))
        # P0-bug②：--deep 能下探短库原文
        check(project, home, 'search --deep 短库原文', ['search', '重启', '--deep'],
              must=('重启',))
        # P0-bug③：session 能列出短库段
        check(project, home, 'session 列段', ['session'], must=(seg,))

        check(project, home, 'index 建索引',
              ['index', '--gist', '!测试结论：重启才生效', '--ref', seg,
               '--summary', '测试段摘要'])
        check(project, home, 'search 索引命中', ['search', '测试结论'],
              must=('C-',))
        check(project, home, 'check 短库', ['check'], must=('检查 短期库',))

        check(project, home, 'pitfall 记坑', ['pitfall', '--title', '测试坑A',
                                              '--symptom', '症状S', '--fix', '解法F'])
        check(project, home, 'search 坑点命中', ['search', '测试坑A'],
              must=('K-',))
        check(project, home, 'growth 记经验', ['growth', '--text', '测试经验G'])
        check(project, home, 'hot', ['hot'], must=('坑点 1 条',))
        check(project, home, 'context 组装', ['context'], must=('已归档',))
        check(project, home, 'keywords', ['keywords'])
        check(project, home, 'suggest', ['suggest'])
        check(project, home, 'digest', ['digest', '--text', '这场对话是测试'])

        # rm 默认只列清单、不动手
        check(project, home, 'rm 只列清单', ['rm', 'K-001'],
              must=('将要删除', 'K-001', '测试坑A'))
        check(project, home, 'rm 后坑点还在', ['search', '测试坑A'], must=('K-',))

        check(project, home, 'close', ['close'])
        check(project, home, 'merge 并入长期库', ['merge'], must=('并',))
        check(project, home, 'check 长期库', ['check', '--long'],
              must=('检查 长期库',))
        check(project, home, 'search 长期库', ['search', '测试坑A', '--long'],
              must=('K-',))

        print('\n全部通过：%d 项' % PASS)
        return 0
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
