import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "xiaohuliming")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_LINES = 5


def fetch():
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=40")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def repo_link(repo):
    name = repo["name"]
    return f"[`{name}`](https://github.com/{name})"


def build(events):
    lines = []
    seen_push = set()
    for e in events:
        t = e.get("type")
        repo = e.get("repo", {})
        payload = e.get("payload", {})
        date = e.get("created_at", "")[:10]
        line = None
        if t == "PushEvent":
            if repo["name"] in seen_push:
                continue
            seen_push.add(repo["name"])
            n = len(payload.get("commits", [])) or 1
            line = f"🔨 Pushed {n} commit{'s' if n != 1 else ''} to {repo_link(repo)}"
        elif t == "PullRequestEvent":
            pr = payload.get("pull_request", {})
            action = payload.get("action", "")
            verb = "Merged" if action == "closed" and pr.get("merged") else action.capitalize()
            line = f"🔀 {verb} PR [#{pr.get('number')}]({pr.get('html_url')}) in {repo_link(repo)}"
        elif t == "IssuesEvent":
            issue = payload.get("issue", {})
            line = f"❗ {payload.get('action', '').capitalize()} issue [#{issue.get('number')}]({issue.get('html_url')}) in {repo_link(repo)}"
        elif t == "CreateEvent" and payload.get("ref_type") == "repository":
            line = f"📦 Created repository {repo_link(repo)}"
        elif t == "ReleaseEvent":
            line = f"🚀 Released {payload.get('release', {}).get('tag_name', '')} in {repo_link(repo)}"
        elif t == "WatchEvent":
            line = f"⭐ Starred {repo_link(repo)}"
        elif t == "ForkEvent":
            line = f"🍴 Forked {repo_link(repo)}"
        if line:
            lines.append(f"- {line} · {date}")
        if len(lines) >= MAX_LINES:
            break
    return lines


def main():
    try:
        lines = build(fetch())
    except Exception as ex:  # keep the existing section on any failure
        print("activity fetch failed:", ex, file=sys.stderr)
        return
    if not lines:
        lines = ["- 💤 Nothing public lately, probably heads-down building"]
    block = "<!--START_SECTION:activity-->\n" + "\n".join(lines) + "\n<!--END_SECTION:activity-->"
    md = open("README.md", encoding="utf-8").read()
    new = re.sub(r"<!--START_SECTION:activity-->.*?<!--END_SECTION:activity-->",
                 block, md, flags=re.S)
    if new != md:
        open("README.md", "w", encoding="utf-8").write(new)
    print("\n".join(lines))


main()
