#!/usr/bin/env bash
# Rebuilds dist/aa-reels.zip from the aa-reels/ folder.
# The ZIP holds the aa-reels/ folder at its root, as Claude's skill upload expects.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
rm -f dist/aa-reels.zip
python3 - <<'EOF'
import os, zipfile
skip_dirs = {"node_modules", "__pycache__", "out", ".git"}
skip_files = {".DS_Store", "pray.json"}
with zipfile.ZipFile("dist/aa-reels.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk("aa-reels"):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs)
        for f in sorted(files):
            if f not in skip_files:
                z.write(os.path.join(root, f))
print("dist/aa-reels.zip:", sum(1 for _ in zipfile.ZipFile("dist/aa-reels.zip").namelist()), "files,",
      os.path.getsize("dist/aa-reels.zip") // 1024, "KB")
EOF
