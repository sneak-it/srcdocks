#!/usr/bin/env python3
"""Drives linkLatest.sh's overlay handling against a fake /repo, /srcds/srv and /overlays.

mountpoint(1) is stubbed on PATH because a real bind mount needs root. find -mount only prevents
descent, so a plain directory plus the stub reproduces the real control flow.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / 'srcds' / 'linkLatest.sh'

# find emits the search root with a trailing slash, and a real mountpoint(1) does not care
STUB = ('#!/bin/sh\n'
        't=${2%/}\n'
        'for p in $MOUNTPOINTS; do [ "$t" = "${p%/}" ] && exit 0; done\n'
        'exit 1\n')

STOCK = ['de_dust2.bsp', 'de_nuke.bsp']


class Fixture:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        for d in ('srv', 'overlays/maps', 'layers', 'custom'):
            (self.root / d).mkdir(parents=True)
        stub = self.root / 'bin' / 'mountpoint'
        stub.parent.mkdir()
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.maps = self.root / 'overlays' / 'maps'

    def version(self, name, maps=STOCK):
        mod = self.root / 'repo' / 'csgo' / name / 'csgo'
        (mod / 'maps' / 'graphs').mkdir(parents=True, exist_ok=True)
        (mod / 'cfg').mkdir(parents=True, exist_ok=True)
        for m in maps:
            (mod / 'maps' / m).touch()
        # loadLatestVersion sleeps 3s when a version dir looks half-written, and picks the
        # newest by mtime, so age the tree and leave this version as the distinctly newest
        for path, age in ((self.root / 'repo', '-1 hour'), (mod.parent, '-1 minute')):
            subprocess.run(['find', str(path), '-exec', 'touch', '-d', age, '{}', '+'], check=True)
        return mod

    def boot(self, mode='merge', mounts=None, funcs='loadLatestVersion; addOverlays; addCustomFiles'):
        env = {
            'PATH': f'{self.root}/bin:/usr/bin:/bin',
            'HOME': str(self.root),
            'APP_NAME': 'csgo',
            'OVERLAY_MODE': mode,
            'REPO': str(self.root / 'repo'),
            'SRV': str(self.root / 'srv'),
            'OVERLAYS': str(self.root / 'overlays'),
            'LAYERS': str(self.root / 'layers'),
            'CUSTOM': str(self.root / 'custom'),
            'MOUNTPOINTS': ' '.join(str(m) for m in (mounts or [self.maps])),
        }
        return subprocess.run(['bash', '-c', f'source "$1"; {funcs}', '_', str(SCRIPT)],
                              env=env, capture_output=True, text=True)

    def served(self):
        """What the running server sees in <mod>/maps."""
        return sorted(os.listdir(self.root / 'srv' / 'csgo' / 'maps'))

    def shared(self):
        return sorted(os.listdir(self.maps))

    def clean(self):
        shutil.rmtree(self.root, ignore_errors=True)


def case(label, mode='merge', mounts=None, setup=None):
    f = Fixture()
    f.version('v_13881')
    if setup:
        setup(f)
    res = f.boot(mode=mode, mounts=mounts)
    print(f'{label}: exit={res.returncode}')
    assert res.returncode == 0, f'{label}: {res.stderr}'
    return f


# 1 + 2: merge seeds stock maps, and the user's own file of the same name is not clobbered
f = case('merge seeds stock', setup=lambda f: (
    (f.maps / 'de_dust2.bsp').write_text('MINE'),
    (f.maps / 'gg_custom.bsp').touch(),
))
assert f.served() == ['de_dust2.bsp', 'de_nuke.bsp', 'gg_custom.bsp', 'graphs'], f.served()
assert (f.maps / 'de_dust2.bsp').read_text() == 'MINE', 'user file was clobbered'
# 8: stock maps are links into the repo, never copied bytes
assert (f.maps / 'de_nuke.bsp').is_symlink(), 'stock map was copied instead of linked'
assert str((f.maps / 'de_nuke.bsp').readlink()).startswith(str(f.root / 'repo')), 'link escaped /repo'
f.clean()

# 3: a version bump re-points the links even though the old version is still on disk
f = case('update tracks new version')
f.version('v_13890', maps=STOCK + ['de_ancient.bsp'])
assert (f.root / 'repo' / 'csgo' / 'v_13881').exists(), 'fixture: old version should still be here'
f.boot()
assert 'de_ancient.bsp' in f.served(), f.served()
target = str((f.maps / 'de_nuke.bsp').readlink())
assert 'v_13890' in target, f'still pinned to the old build: {target}'

# 4: after KEEPCOUNT rotation drops the old version, no dangling links are left behind
shutil.rmtree(f.root / 'repo' / 'csgo' / 'v_13881')
f.boot()
dangling = [p for p in f.maps.iterdir() if p.is_symlink() and not p.exists()]
print(f'rotation leaves no dangling links: {len(dangling)} found')
assert dangling == [], dangling
f.clean()

# 5: replace is the default and still wipes the stock maps, exactly as before this change
f = case('replace keeps old behaviour', mode='replace',
         setup=lambda f: (f.maps / 'only_mine.bsp').touch())
assert f.served() == ['only_mine.bsp'], f.served()
f.clean()

# 6: /overlays itself being a mountpoint must not eat the mod folder
f = Fixture()
f.version('v_13881')
res = f.boot(mounts=[f.root / 'overlays'])
print(f'overlays root is skipped: exit={res.returncode}')
assert res.returncode == 0, res.stderr
assert sorted(f.served()) == ['de_dust2.bsp', 'de_nuke.bsp', 'graphs'], f.served()
assert not (f.root / 'srv' / 'csgo').is_symlink(), 'mod folder was replaced by the overlay'
f.clean()

# 7: a layer whose top-level name collides with an overlay still gets through
f = case('layer reaches an overlaid dir', setup=lambda f: (
    (f.root / 'layers' / 'extra' / 'maps').mkdir(parents=True),
    (f.root / 'layers' / 'extra' / 'maps' / 'layer_map.bsp').touch(),
))
assert 'layer_map.bsp' in f.served(), f.served()
f.clean()

# An unwritable overlay must be skipped loudly rather than silently serving no stock maps.
# root ignores the permission bits, so this only means anything as a normal user (i.e. in CI).
if os.geteuid() == 0:
    print('unwritable overlay: skipped, running as root')
    raise SystemExit(print('all ok'))

f = Fixture()
f.version('v_13881')
f.maps.chmod(0o555)
res = f.boot()
f.maps.chmod(0o755)
print(f'unwritable overlay: exit={res.returncode} warned={"not writable" in res.stdout}')
assert res.returncode == 0, res.stderr
assert 'not writable' in res.stdout, res.stdout
assert 'de_dust2.bsp' in f.served(), 'stock maps were dropped for an unwritable overlay'
f.clean()

print('all ok')
