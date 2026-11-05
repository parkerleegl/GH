"""Package only source allowlisted here; never include runtime data or credentials."""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent.parent
output = root.parent / 'gl-sala-review.zip'
allowed = [root / name for name in ('README.md', 'SECURITY.md', '.gitignore')]
for folder, extension in [('muse_room', '.py'), ('tests', '.py'), ('scripts', '.py'), ('docs', '.md'), ('web', '.html'), ('web', '.css'), ('web', '.js'), ('.github/workflows', '.yml')]:
    allowed.extend((root / folder).glob('*' + extension))
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(allowed):
        if path.is_symlink():
            raise SystemExit('Refusing to package a symlink: ' + str(path))
        archive.write(path, Path('gl-sala') / path.relative_to(root))
print(str(output))
print('files=' + str(len(allowed)))
print('sha256=' + hashlib.sha256(output.read_bytes()).hexdigest())
