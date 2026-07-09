import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "xiaohuliming")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("ACTIVITY_SVG", "assets/activity.svg")
MAX_ROWS = 5
ROW_COLORS = ["#0A84FF", "#FF453A"]


def fetch():
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=40")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def repo_name(repo):
    full = repo["name"]
    owner, _, short = full.partition("/")
    return short if owner == USER else full


def build_items(events):
    items = []
    seen_push = set()
    for e in events:
        t = e.get("type")
        repo = e.get("repo", {})
        payload = e.get("payload", {})
        date = e.get("created_at", "")[:10]
        name = repo_name(repo)
        text = None
        if t == "PushEvent":
            if repo["name"] in seen_push:
                continue
            seen_push.add(repo["name"])
            n = len(payload.get("commits", [])) or 1
            text = f"Pushed {n} commit{'s' if n != 1 else ''} to {name}"
        elif t == "PullRequestEvent":
            pr = payload.get("pull_request", {})
            action = payload.get("action", "")
            verb = "Merged" if action == "closed" and pr.get("merged") else action.capitalize()
            text = f"{verb} PR #{pr.get('number')} in {name}"
        elif t == "IssuesEvent":
            issue = payload.get("issue", {})
            text = f"{payload.get('action', '').capitalize()} issue #{issue.get('number')} in {name}"
        elif t == "CreateEvent" and payload.get("ref_type") == "repository":
            text = f"Created repository {name}"
        elif t == "ReleaseEvent":
            text = f"Released {payload.get('release', {}).get('tag_name', '')} in {name}"
        elif t == "WatchEvent":
            text = f"Starred {name}"
        elif t == "ForkEvent":
            text = f"Forked {name}"
        if text:
            items.append((text, date))
        if len(items) >= MAX_ROWS:
            break
    return items


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(items):
    rows = []
    for i, (text, date) in enumerate(items):
        y = 100 + i * 26
        color = ROW_COLORS[i % 2]
        disp = text if len(text) <= 62 else text[:61] + "…"
        rows.append(
            f'<rect x="36" y="{y - 10}" width="9" height="9" fill="{color}"/>'
            f'<text class="m" x="54" y="{y}" font-size="14.5" fill="#1a1a1a">{xml_escape(disp)}</text>'
            f'<text class="m" x="846" y="{y}" font-size="12.5" text-anchor="end" fill="#8a8a8a">{xml_escape(date)}</text>')
    rows_svg = "\n".join(rows)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 244" width="880" height="244" role="img" aria-label="Recent GitHub activity">\n'
        '<defs>\n'
        '  <pattern id="ag" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.5" fill="#111111" opacity="0.06"/></pattern>\n'
        '  <clipPath id="ap"><rect x="10" y="12" width="844" height="210"/></clipPath>\n'
        '</defs>\n'
        '<style>\n'
        " .m{font-family:'SF Mono',ui-monospace,Menlo,Consolas,monospace}\n"
        ' .panel{animation:snap .6s cubic-bezier(0.16,1,0.3,1) both;transform-box:fill-box;transform-origin:top left}\n'
        ' @keyframes snap{from{transform:translate(-8px,-8px)}to{transform:translate(0,0)}}\n'
        ' .acc{animation:cyc 4.5s ease-in-out infinite}\n'
        ' @keyframes cyc{0%,100%{fill:#0A84FF}33%{fill:#FF453A}66%{fill:#FFD60A}}\n'
        '</style>\n'
        '<rect x="16" y="20" width="848" height="212" fill="#111111"/>\n'
        '<g class="panel">\n'
        '<rect x="8" y="12" width="848" height="210" fill="#f4f1ea" stroke="#111111" stroke-width="4"/>\n'
        '<g clip-path="url(#ap)">\n'
        '<rect x="10" y="12" width="844" height="210" fill="url(#ag)"/>\n'
        '<rect class="acc" x="34" y="34" width="8" height="22" fill="#0A84FF"/>\n'
        '<text class="m" x="52" y="52" font-size="17" font-weight="700" fill="#111111">RECENT ACTIVITY</text>\n'
        '<text class="m" x="846" y="51" font-size="12.5" text-anchor="end" fill="#8a8a8a">git log --oneline -5</text>\n'
        '<rect x="34" y="70" width="812" height="2" fill="#111111" opacity="0.12"/>\n'
        f'{rows_svg}\n'
        '</g>\n</g>\n</svg>\n')


def main():
    try:
        items = build_items(fetch())
    except Exception as ex:  # keep the existing card on any failure
        print("activity fetch failed:", ex, file=sys.stderr)
        return
    if not items:
        items = [("No public activity lately, heads-down building", "")]
    svg = build_svg(items)
    try:
        old = open(OUT, encoding="utf-8").read()
    except FileNotFoundError:
        old = ""
    if svg != old:
        open(OUT, "w", encoding="utf-8").write(svg)
    print("\n".join(f"{t} · {d}" for t, d in items))


main()
