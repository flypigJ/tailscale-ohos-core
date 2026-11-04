"""Small, dependency-free helpers for the public port build scripts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def run(args, *, cwd=None, env=None, capture=False):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            check=True, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def child(root, relative):
    root = Path(root).resolve()
    relative = str(relative)
    if "\\" in relative or ":" in relative:
        raise ValueError("manifest paths must use relative POSIX paths")
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("manifest path escapes source directory")
    result = (root / p).resolve()
    if result == root or not result.is_relative_to(root):
        raise ValueError("manifest path escapes source directory")
    return result


def verify_files(root, files):
    seen = set()
    for item in files:
        if item["path"] in seen:
            raise ValueError("duplicate manifest path")
        seen.add(item["path"])
        if digest(child(root, item["path"])) != item["sha256"]:
            raise ValueError("source digest differs: " + item["path"])


def clean_env():
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("GO", "CGO_")) or key in ("CC", "CXX", "AR", "PKG_CONFIG"):
            env.pop(key)
    env.update(GOENV="off", GOTOOLCHAIN="local", GOWORK="off", CGO_ENABLED="0")
    return env


def go_env(root):
    root = Path(root).resolve()
    env = clean_env()
    env["GOROOT"] = str(root)
    env["PATH"] = str(root / "bin") + os.pathsep + env.get("PATH", "")
    return env


def go_binary(root):
    return Path(root).resolve() / "bin" / ("go.exe" if os.name == "nt" else "go")


def native_sdk(root):
    root = Path(root).resolve()
    info = read(root / "oh-uni-package.json")
    if int(info["apiVersion"]) != 26 or info["releaseType"] != "Release":
        raise ValueError("this qualified build requires the API 26 Release native SDK")
    for name in ("clang", "llvm-readelf"):
        tool = root / "llvm/bin" / (name + (".exe" if os.name == "nt" else ""))
        if not tool.is_file():
            raise ValueError("missing native SDK tool: " + name)
    if not (root / "sysroot").is_dir():
        raise ValueError("native SDK sysroot missing")
    return root, info


def target_env(go_root, sdk, cache):
    env = go_env(go_root)
    suffix = ".exe" if os.name == "nt" else ""
    # Go parses CC/CXX as quoted fields, including on Windows. Forward slashes
    # avoid treating backslashes as escapes; quotes preserve spaces in paths.
    def compiler(name):
        exe = (sdk / "llvm/bin" / (name + suffix)).as_posix()
        return '"' + exe + '" --target=aarch64-linux-ohos "--sysroot=' + (sdk / "sysroot").as_posix() + '" -D__MUSL__'
    env.update(GOOS="openharmony", GOARCH="arm64", CGO_ENABLED="1",
               CC=compiler("clang"), CXX=compiler("clang++"), GOCACHE=str(Path(cache).resolve()))
    return env


def tracked_digest(root, paths):
    untracked = run(["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=root, capture=True)
    if untracked:
        raise ValueError("untracked build inputs; add reviewed source to Git before building")
    names = run(["git", "ls-files", "-z", "--", *paths], cwd=root, capture=True).split("\0")
    files = [{"path": p, "sha256": digest(child(root, p))} for p in sorted(set(names)) if p]
    if not files:
        raise ValueError("no tracked source files; commit the source before building")
    value = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return value, files
