from pathlib import Path
import io
import tarfile

root = Path('..').resolve()
dist = root / 'dist'
original = root / 'pingus.tar.bz2'
if not original.is_file():
    raise SystemExit('original Pingus source archive missing')

out = dist / 'PINGUS-CORRESPONDING-SOURCE.tar.gz'
readme = '''Pingus 0.7.6 Web port - Corresponding Source\n\nThis archive accompanies the distributed WebAssembly/object-code build.\nIt contains the pristine Pingus 0.7.6 source archive plus all Web/Yandex\npatch scripts, localized Web assets, browser shell files, and the CI build\nworkflow used to produce the release.\n\nRebuild outline:\n1. Extract pingus-0.7.6.orig.tar.bz2.\n2. Rename the extracted directory to pingus-src.\n3. Copy tools/build_web.sh to pingus-src/build_web.sh.\n4. Install Emscripten SDK 3.1.64 and the host dependencies shown in\n   port/pingus-web.yml.\n5. From pingus-src run: bash build_web.sh\n\nThe original project and this port are distributed under the GPL terms in\nCOPYING. No private repository access is required to obtain the corresponding\nsource included here.\n'''

with tarfile.open(out, 'w:gz', compresslevel=6) as tf:
    tf.add(original, arcname='pingus-0.7.6.orig.tar.bz2', recursive=False)
    for directory in ('tools', 'web', 'assets'):
        base = root / directory
        if not base.is_dir():
            raise SystemExit(f'missing source component: {directory}')
        for path in sorted(base.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            tf.add(path, arcname=str(Path('port') / path.relative_to(root)), recursive=False)
    workflow = root / '.github' / 'workflows' / 'pingus-web.yml'
    if workflow.is_file():
        tf.add(workflow, arcname='port/pingus-web.yml', recursive=False)
    info = tarfile.TarInfo('BUILDING.txt')
    payload = readme.encode('utf-8')
    info.size = len(payload)
    info.mode = 0o644
    tf.addfile(info, io.BytesIO(payload))

print(f'GPL corresponding source bundle: {out.name} {out.stat().st_size} bytes')
