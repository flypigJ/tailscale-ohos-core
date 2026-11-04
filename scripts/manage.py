"""Prepare, test and cross-build the pinned HarmonyOS C ABI. Python 3.11+."""
import argparse
from datetime import datetime, timezone
import os
import json
from pathlib import Path
import re
import subprocess
import sys

from common import child, digest, go_binary, go_env, native_sdk, read, run, target_env, tracked_digest, verify_files, write

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / ".deps/tailscale"


def verify_vendor(lock):
    if run(["git", "rev-parse", "HEAD"], cwd=VENDOR, capture=True) != lock["upstream_commit"]:
        raise ValueError("vendor baseline changed")
    changed = set(run(["git", "diff", "--name-only", "HEAD"], cwd=VENDOR, capture=True).splitlines())
    if changed != {f["path"] for f in lock["vendor_files"]}:
        raise ValueError("vendor patch file set differs")
    if run(["git", "ls-files", "--others", "--exclude-standard"], cwd=VENDOR, capture=True):
        raise ValueError("unexpected untracked vendor files")
    verify_files(VENDOR, lock["vendor_files"])


def prepare(lock, repository):
    verify_files(ROOT, lock["patches"])
    if not VENDOR.exists():
        VENDOR.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--no-checkout", "--depth=1", "--branch", lock["upstream_tag"], repository, VENDOR])
        run(["git", "config", "core.autocrlf", "false"], cwd=VENDOR)
        run(["git", "config", "core.longpaths", "true"], cwd=VENDOR)
        if run(["git", "rev-parse", "HEAD"], cwd=VENDOR, capture=True) != lock["upstream_commit"]:
            raise ValueError("upstream tag no longer matches the reviewed commit")
        run(["git", "checkout", "--detach", lock["upstream_commit"]], cwd=VENDOR)
        for patch in lock["patches"]:
            run(["git", "apply", "--index", child(ROOT, patch["path"])], cwd=VENDOR)
    verify_vendor(lock)
    print("Pinned dependency verified. Existing checkouts are never reset or cleaned.")


def test(lock, go_root, module_cache=None):
    verify_vendor(lock)
    env = go_env(go_root)
    env["CGO_ENABLED"] = "0"
    if module_cache:
        env["GOMODCACHE"] = str(Path(module_cache).resolve())
    # The C entry file is excluded with CGO=0. This tests bridge behavior and
    # routes on Linux; it is not proof of C ABI or device execution.
    out = ROOT / "out/host-tests.json"
    write(out, {"status": "running", "device_tested": False})
    try:
        output = run([go_binary(go_root), "test", "-json", "-p", "2", "-mod=readonly", "-count=1", "-timeout=180s", "./..."], cwd=ROOT, env=env, capture=True)
        events = [json.loads(line) for line in output.splitlines()]
        tests = [e for e in events if e.get("Test") and e["Action"] in ("pass", "fail", "skip")]
        counts = {a: sum(e["Action"] == a for e in tests) for a in ("pass", "fail", "skip")}
        packages = [e["Package"] for e in events if e["Action"] == "pass" and not e.get("Test")]
        receipt = {"status": "passed", "tests_including_subtests": counts,
                   "top_level_tests_passed": sum(e["Action"] == "pass" and "/" not in e["Test"] for e in tests), "packages": packages, "device_tested": False,
                   "source_digest": tracked_digest(ROOT, ["*.go", "vpnroute", "go.mod", "go.sum", "source.json", "patches", "scripts"])[0],
                   "go_version": run([go_binary(go_root), "version"], env=env, capture=True)}
        write(out, receipt)
        print(json.dumps(receipt, indent=2))
    except Exception as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout)
        write(out, {"status": "failed", "device_tested": False})
        raise


def build_checked(lock, go_root, sdk_root, module_cache=None):
    verify_vendor(lock)
    go_root = Path(go_root).resolve()
    port = read(go_root / "ohos/source.json")
    if run(["git", "rev-parse", "HEAD"], cwd=go_root, capture=True) != lock["toolchain_commit"]:
        raise ValueError("toolchain checkout must match source.json's qualified commit")
    run([sys.executable, go_root / "ohos/scripts/manage.py", "verify-compiler"])
    compiler = go_binary(go_root)
    version = run([compiler, "version"], env=go_env(go_root), capture=True)
    if not version.startswith("go version " + lock["toolchain_identity"] + " "):
        raise ValueError("wrong OpenHarmony compiler identity")
    sdk, info = native_sdk(sdk_root)
    out = ROOT / "out/arm64-v8a"
    out.mkdir(parents=True, exist_ok=True)
    source_id, sources = tracked_digest(ROOT, ["*.go", "vpnroute", "go.mod", "go.sum", "source.json", "patches", "scripts", "include", "examples"])
    env = target_env(go_root, sdk, ROOT / ".cache/native")
    if module_cache:
        env["GOMODCACHE"] = str(Path(module_cache).resolve())
    flags = ("-extldflags=-Wl,-soname,libtailscale_go.so,--build-id=sha1 "
             "-X tailscale.com/version.longStamp=" + lock["engine_version"] +
             " -X tailscale.com/version.shortStamp=" + lock["engine_version"] +
             " -X main.pathDiagnosticBuild=" + source_id)
    library = out / "libtailscale_go.so"
    receipt = {"schema": 1, "status": "building", "source_digest": source_id, "sources": sources,
               "toolchain_identity": lock["toolchain_identity"], "toolchain_commit": lock["toolchain_commit"],
               "compiler_sha256": digest(compiler), "sdk_version": info["version"], "device_tested": False}
    try:
        run([compiler, "build", "-p", "2", "-mod=readonly", "-trimpath", "-buildvcs=false", "-buildmode=c-shared",
             "-ldflags=" + flags, "-o", library, "."], cwd=ROOT, env=env)
        metadata = run([compiler, "version", "-m", library], env=env, capture=True)
        if lock["toolchain_identity"] not in metadata or "tailscale.com\tv" + lock["engine_version"] not in metadata:
            raise ValueError("binary metadata does not match pinned versions")
        expected = re.findall(r"^extern (.+);$", (ROOT / "include/tailscale_ohos.h").read_text(), re.M)
        actual = re.findall(r"^extern (.+);$", library.with_suffix(".h").read_text(), re.M)
        actual = [s for s in actual if re.search(r"\bTS\w+\(", s)]
        normalize = lambda items: sorted(re.sub(r"\s+", " ", s).strip() for s in items)
        if normalize(expected) != normalize(actual) or len(expected) != 41:
            raise ValueError("generated production C ABI differs")
        readelf = sdk / "llvm/bin" / ("llvm-readelf.exe" if os.name == "nt" else "llvm-readelf")
        elf_header = run([readelf, "-h", library], capture=True)
        relocations = run([readelf, "-r", library], capture=True)
        symbols = run([readelf, "--dyn-syms", library], capture=True)
        if "AArch64" not in elf_header or "TLSDESC" not in relocations or "R_AARCH64_TLS_TPREL" in relocations:
            raise ValueError("unexpected architecture or dynamic-library TLS model")
        exports = set(re.findall(r"\b(TS\w+)\s*$", symbols, re.M))
        if exports != set(re.search(r"\b(TS\w+)\(", declaration).group(1) for declaration in expected):
            raise ValueError("ELF exports differ from public C interface")
        clang = sdk / "llvm/bin" / ("clang.exe" if os.name == "nt" else "clang")
        run([clang, "--target=aarch64-linux-ohos", "--sysroot=" + str(sdk / "sysroot"), "-Wall", "-Wextra", "-Werror",
             ROOT / "examples/smoke.c", "-ldl", "-o", out / "smoke"])
        verify_vendor(lock)
        if tracked_digest(ROOT, ["*.go", "vpnroute", "go.mod", "go.sum", "source.json", "patches", "scripts", "include", "examples"])[0] != source_id:
            raise ValueError("source changed while compiling")
        receipt.update(status="passed", library_sha256=digest(library), header_sha256=digest(library.with_suffix(".h")), smoke_sha256=digest(out / "smoke"), c_exports=41, elf_tls="AArch64 TLSDESC; no initial-exec relocation")
    except Exception:
        receipt["status"] = "failed"
        raise
    finally:
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        write(out / "build.json", receipt)
    print("Built out/arm64-v8a/libtailscale_go.so and matching header; device validation remains separate.")


def build(lock, go_root, sdk_root, module_cache=None):
    receipt_path = ROOT / "out/arm64-v8a/build.json"
    write(receipt_path, {"status": "building", "device_tested": False})
    try:
        build_checked(lock, go_root, sdk_root, module_cache)
    except Exception:
        write(receipt_path, {"status": "failed", "device_tested": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--repository", default="https://github.com/tailscale/tailscale.git")
    sub.add_parser("verify")
    t = sub.add_parser("test")
    t.add_argument("--go-root", required=True)
    t.add_argument("--module-cache", help="optional existing Go module download cache")
    b = sub.add_parser("build")
    b.add_argument("--go-root", required=True)
    b.add_argument("--sdk", required=True, help="API 26 native SDK directory containing llvm and sysroot")
    b.add_argument("--module-cache", help="optional existing Go module download cache")
    args = parser.parse_args()
    lock = read(ROOT / "source.json")
    if args.command == "prepare": prepare(lock, args.repository)
    elif args.command == "verify": verify_files(ROOT, lock["patches"]); verify_vendor(lock)
    elif args.command == "test": test(lock, args.go_root, args.module_cache)
    else: build(lock, args.go_root, args.sdk, args.module_cache)


if __name__ == "__main__":
    main()
