"""Check local Markdown targets in the downstream documentation only."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
patterns = ["README*.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md", "docs/**/*.md", "ohos/**/*.md", "examples/**/*.md"]
files = sorted({p for pattern in patterns for p in root.glob(pattern) if "/out/" not in p.as_posix() and p.name != "README.upstream.md"})
errors = []
for file in files:
    text = file.read_text(encoding="utf-8")
    for value in re.findall(r"\]\(([^)]+)\)", text):
        target = value.split("#", 1)[0]
        if not target or re.match(r"^[a-zA-Z][\w+.-]*:", target):
            continue
        path = file.parent / unquote(target.strip("<>"))
        if not path.exists(): errors.append(f"{file.relative_to(root)}: missing {target}")
    if re.search(r"^#{4,}\s", text, re.M): errors.append(f"{file.relative_to(root)}: heading exceeds three levels")
    if re.search(r"^```\s*\n", text, re.M):
        # Closing fences are also bare; only opening fences need a language.
        inside = False
        for line in text.splitlines():
            if line.startswith("```"):
                if not inside and line.strip() == "```": errors.append(f"{file.relative_to(root)}: code fence needs language")
                inside = not inside
    if re.search(r"(?i)C:[/\\]Users[/\\]|/mnt/c/Users/", text): errors.append(f"{file.relative_to(root)}: local user path")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Checked {len(files)} downstream Markdown files")
