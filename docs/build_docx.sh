#!/usr/bin/env bash
# Build the theory Word document in two passes so the table of contents
# carries real page numbers.
#
#   bash docs/build_docx.sh
set -e
cd "$(dirname "$0")/.."

echo "== figures =="
python3 docs/make_figures.py >/dev/null

echo "== pass 1 =="
rm -f docs/.tocmap.json
node docs/build_docx.js

echo "== rendering to find page numbers =="
# needs LibreOffice (soffice) and poppler (pdftotext) on the PATH
soffice --headless --convert-to pdf --outdir docs \
    docs/THEORY.docx >/dev/null

python3 - <<'PY'
import json, re, subprocess, os
head = json.load(open("docs/.headings.json"))
txt = subprocess.run(["pdftotext", "-layout",
                      "docs/THEORY.pdf", "-"],
                     capture_output=True, text=True).stdout
pages = txt.split("\f")

# the body starts after the contents; find the first page that carries chapter 1
first_body = 0
for i, pg in enumerate(pages):
    if re.search(r"^\s*1\.\s+The physics of earthing\s*$", pg, re.M) and i > 1:
        first_body = i
        break

mp = {}
for h in head:
    t = h["text"]
    pat = re.compile(r"^\s*" + re.escape(t) + r"\s*$", re.M)
    for i in range(first_body, len(pages)):
        if pat.search(pages[i]):
            mp[t] = i + 1          # pdftotext pages are 0-based here
            break
json.dump(mp, open("docs/.tocmap.json", "w"), indent=1)
print(f"   located {len(mp)}/{len(head)} headings")
PY

echo "== pass 2 =="
node docs/build_docx.js
rm -f docs/.headings.json
echo "done: docs/THEORY.docx"
