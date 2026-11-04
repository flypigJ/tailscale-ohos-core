"""Check public C export and reference coverage; native builds check full signatures."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
source = (root / "main.go").read_text(encoding="utf-8")
header = (root / "include/tailscale_ohos.h").read_text(encoding="utf-8")
reference = (root / "docs/api.md").read_text(encoding="utf-8")
exports = re.findall(r"^//export (TS\w+)$", source, re.M)
declarations = re.findall(r"^extern .*?\b(TS\w+)\(", header, re.M)
documented = re.findall(r"^\| `(TS\w+)` \|", reference, re.M)
if len(exports) != 41 or len(set(exports)) != 41:
    raise SystemExit("C ABI export inventory changed; review compatibility and update the contract")
if sorted(exports) != sorted(declarations) or sorted(exports) != sorted(documented):
    raise SystemExit("C exports, public header and API reference are inconsistent")
print("All 41 exports have public declarations and API documentation")
