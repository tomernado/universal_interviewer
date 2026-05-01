"""
File browser API — runs inside Docker on port 8080.
Serves real directory listings and file contents to the dashboard.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

ALLOWED_ROOTS = (
    '/app',
    '/usr/local/lib/python3.10/site-packages',
)

MAX_FILE_BYTES = 500_000  # 500 KB read cap


def safe_path(raw: str) -> str | None:
    """Resolve and validate that path stays under an allowed root."""
    try:
        resolved = os.path.realpath(raw)
    except Exception:
        return None
    for root in ALLOWED_ROOTS:
        if resolved == root or resolved.startswith(root + os.sep):
            return resolved
    return None


@app.get('/health')
def health():
    return jsonify({'status': 'ok'})


@app.get('/api/ls')
def ls():
    raw = request.args.get('path', '/app')
    path = safe_path(raw)
    if path is None:
        return jsonify({'error': 'Path not allowed'}), 403
    if not os.path.isdir(path):
        return jsonify({'error': 'Not a directory'}), 404

    try:
        entries = []
        for name in sorted(os.listdir(path), key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower())):
            full = os.path.join(path, name)
            is_dir = os.path.isdir(full)
            entries.append({
                'name': name,
                'type': 'dir' if is_dir else 'file',
                'size': None if is_dir else os.path.getsize(full),
                'ext':  os.path.splitext(name)[1].lstrip('.') if not is_dir else None,
            })
        return jsonify({'path': path, 'entries': entries})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403


@app.get('/api/read')
def read():
    raw = request.args.get('path', '')
    path = safe_path(raw)
    if path is None:
        return jsonify({'error': 'Path not allowed'}), 403
    if not os.path.isfile(path):
        return jsonify({'error': 'Not a file'}), 404

    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        return jsonify({'error': f'File too large ({size // 1024} KB). Limit is {MAX_FILE_BYTES // 1024} KB.', 'size': size}), 413

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({'path': path, 'content': content, 'size': size})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('[file-browser] API listening on http://0.0.0.0:8080')
    app.run(host='0.0.0.0', port=8080, debug=False)
