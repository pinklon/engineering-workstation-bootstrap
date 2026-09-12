#!/usr/bin/env bash
set -euo pipefail
python3 -B - <<'PY'
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, 'lib')
from cloud_apt import prepare_apt_profile

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = root / 'etc-apt'
    parts = source / 'sources.list.d'
    parts.mkdir(parents=True)
    ubuntu = 'Types: deb\nURIs: https://snapshot.ubuntu.com/ubuntu/20260828T000000Z\nSuites: noble\nComponents: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'
    (parts / 'ubuntu.sources').write_text(ubuntu)
    assert prepare_apt_profile(root / 'state', source) is None
    (parts / 'llvm.list').write_text('deb [signed-by=/usr/share/keyrings/llvm.gpg] https://apt.llvm.org/noble llvm-toolchain-noble-20 main\n')
    before = {p.name: p.read_bytes() for p in parts.iterdir()}
    config = prepare_apt_profile(root / 'state', source)
    assert config and config.is_file()
    profile = config.parent
    assert (profile / 'sources.list.d/ubuntu.sources').read_text() == ubuntu + '\n'
    assert 'apt.llvm.org' not in (profile / 'sources.list.d/llvm.list').read_text()
    assert before == {p.name: p.read_bytes() for p in parts.iterdir()}
    assert 'AllowInsecure' not in config.read_text() and 'Trusted' not in config.read_text()
    (parts / 'mixed.sources').write_text(ubuntu + '\nTypes: deb\nURIs: https://apt.llvm.org/noble\nSuites: llvm-toolchain-noble-20\nComponents: main\n')
    prepare_apt_profile(root / 'state', source)
    mixed = (profile / 'sources.list.d/mixed.sources').read_text()
    assert 'snapshot.ubuntu.com' in mixed and 'apt.llvm.org' not in mixed
print('PASS: scoped cloud APT profile preserves source configuration and signature settings')
PY
