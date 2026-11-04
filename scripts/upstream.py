"""Report upstream drift; optionally maintain one tracking issue in this repo."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


def api(path, method="GET", payload=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ohos-port-upstream-monitor", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com/" + path, headers=headers, method=method,
                                     data=None if payload is None else json.dumps(payload).encode())
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def stable_version(tag, prefix):
    match = re.fullmatch(re.escape(prefix) + r"(\d+)\.(\d+)(?:\.(\d+))?", tag)
    return tuple(int(x or 0) for x in match.groups()) if match else None


def report(config, tags, head):
    versions = [(stable_version(t["name"], config["tag_prefix"]), t["name"]) for t in tags]
    versions = [(v, t) for v, t in versions if v is not None]
    if not versions:
        raise ValueError("upstream did not return a stable version")
    latest_version, latest_tag = max(versions)
    pinned = stable_version(config["qualified_tag"], config["tag_prefix"])
    if pinned is None:
        raise ValueError("invalid qualified tag")
    return {"qualified": config["qualified_tag"], "latest": latest_tag, "new_release": latest_version > pinned,
            "mainline_commit": head, "mainline_changed": head != config["observed_mainline_commit"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "upstream.json"))
    parser.add_argument("--issue", action="store_true", help="maintain a single issue in the configured owner repository")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    upstream, owner = config["upstream"], config["repository"]
    for repo in (upstream, owner):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("invalid repository identifier")
    tags = []
    for page in range(1, 4):
        endpoint = "releases" if config.get("use_releases") else "tags"
        batch = api(f"repos/{upstream}/{endpoint}?per_page=100&page={page}")
        tags += [t for t in batch if not t.get("prerelease") and not t.get("draft")]
        if len(batch) < 100: break
    tags = [{"name": t.get("tag_name", t.get("name"))} for t in tags]
    head = api(f"repos/{upstream}/git/ref/heads/{config['branch']}")["object"]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("invalid upstream commit")
    result = report(config, tags, head)
    print(json.dumps(result, indent=2))
    if not args.issue:
        return
    if os.environ.get("GITHUB_REPOSITORY") != owner:
        raise ValueError("issue updates are limited to this workflow's configured repository")
    title = "Upstream synchronization tracking"
    issues = []
    for page in range(1, 4):
        batch = api(f"repos/{owner}/issues?state=open&per_page=100&page={page}")
        issues += batch
        if len(batch) < 100: break
    matches = [i for i in issues if i["title"] == title and "pull_request" not in i and "<!-- ohos-upstream-monitor -->" in (i.get("body") or "")]
    if len(matches) > 1:
        raise ValueError("multiple tracking issues; refusing ambiguous update")
    if not result["new_release"] and not result["mainline_changed"]:
        if matches:
            api(f"repos/{owner}/issues/{matches[0]['number']}", "PATCH", {"state": "closed", "state_reason": "completed"})
        return
    body = ("<!-- ohos-upstream-monitor -->\n"
            f"Qualified release: `{result['qualified']}`\n\nLatest stable tag observed: `{result['latest']}`\n\n"
            f"Upstream {config['branch']}: https://github.com/{upstream}/commit/{head}\n\n"
            "This is discovery, not an accepted upgrade. Review release/security notes, replay the port on a new branch, "
            "run host/SDK/device checks as applicable, and update the qualified lock only after review. "
            "Do not silently replace the pinned dependency or inherit old device evidence.\n\n"
            "See the repository's maintenance guide. Update observed_mainline_commit after triage; "
            "update qualified_tag only after an actual validated upgrade.\n")
    if matches:
        if matches[0].get("body") != body:
            api(f"repos/{owner}/issues/{matches[0]['number']}", "PATCH", {"body": body})
    else:
        api(f"repos/{owner}/issues", "POST", {"title": title, "body": body})


if __name__ == "__main__":
    main()
