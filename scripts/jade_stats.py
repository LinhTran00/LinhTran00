"""Jade & Chrome GitHub stats.

Reads your public GitHub numbers through the GraphQL API and writes four SVGs
into assets/stats/ (a stats card and a contribution calendar, light + dark).
Runs in GitHub Actions with the built-in GITHUB_TOKEN; standard library only.

    python scripts/jade_stats.py            # real data (needs GITHUB_TOKEN, LOGIN)
    python scripts/jade_stats.py --demo     # sample data, for previewing the design
"""
import base64, datetime as dt, json, os, sys, urllib.request
from xml.sax.saxutils import escape

LOGIN = os.environ.get("LOGIN", "LinhTran00")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "stats")

THEMES = {
    "light": dict(pearl="#f6f5fa", mist="#ecebf2", lavender="#dcd9e8", ink="#262a37", muted="#5c6274",
                  jade="#86cbbf", jadeDeep="#2c766d", sage="#a7bca8", blossom="#f3c9d5", blossomDeep="#a5476c",
                  hi="#eff1f6", mid="#9399a9", lo="#545a6b", lantern="#ffffff", empty="#e3e1ec",
                  heat=["#cfe7e1", "#9fd2c6", "#5fae9f", "#2c766d"]),
    "dark": dict(pearl="#0a1c1f", mist="#10282b", lavender="#1a3337", ink="#e8eef0", muted="#a3b6b9",
                 jade="#5fd0c0", jadeDeep="#86e3d5", sage="#7f9f89", blossom="#e7a6ba", blossomDeep="#f2b8ca",
                 hi="#f4f8fa", mid="#b8c4cc", lo="#6f7d88", lantern="#d6fff6", empty="#16302f",
                 heat=["#1f5450", "#2d8077", "#47b3a4", "#86e3d5"]),
}
LANG_COLORS = ["jadeDeep", "sage", "mid", "blossom", "jade", "lo"]

FONT_URLS = {
    "serif": "https://cdn.jsdelivr.net/npm/@fontsource/playfair-display@5.0.25/files/playfair-display-latin-400-italic.woff2",
    "sans3": "https://cdn.jsdelivr.net/npm/@fontsource/be-vietnam-pro@5.0.13/files/be-vietnam-pro-latin-300-normal.woff2",
    "sans4": "https://cdn.jsdelivr.net/npm/@fontsource/be-vietnam-pro@5.0.13/files/be-vietnam-pro-latin-400-normal.woff2",
}


def font_css():
    """Embed the brand fonts so the SVG looks the same everywhere; fall back quietly."""
    data = {}
    for k, url in FONT_URLS.items():
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data[k] = base64.b64encode(r.read()).decode()
        except Exception:
            data[k] = None
    css = ""
    if data["serif"]:
        css += f"@font-face{{font-family:'PF';font-style:italic;src:url(data:font/woff2;base64,{data['serif']}) format('woff2')}}"
    if data["sans3"]:
        css += f"@font-face{{font-family:'BV';font-weight:300;src:url(data:font/woff2;base64,{data['sans3']}) format('woff2')}}"
    if data["sans4"]:
        css += f"@font-face{{font-family:'BV';font-weight:400;src:url(data:font/woff2;base64,{data['sans4']}) format('woff2')}}"
    return css + ".serif{font-family:'PF',Georgia,'Times New Roman',serif;font-style:italic}.sans{font-family:'BV',system-ui,-apple-system,'Segoe UI',sans-serif}"


QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
  }
}"""


def fetch():
    token = os.environ.get("STATS_TOKEN") or os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "jade-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    u = payload["data"]["user"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    cc = u["contributionsCollection"]
    return dict(
        repos=u["repositories"]["totalCount"],
        stars=sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        followers=u["followers"]["totalCount"],
        commits=cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        prs=cc["totalPullRequestContributions"],
        total=cc["contributionCalendar"]["totalContributions"],
        langs=langs,
        weeks=[[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cc["contributionCalendar"]["weeks"]],
    )


def demo():
    import random
    random.seed(7)
    start = dt.date.today() - dt.timedelta(days=370)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks, day = [], start
    while day <= dt.date.today():
        week = []
        for _ in range(7):
            if day <= dt.date.today():
                week.append((day.isoformat(), max(0, int(random.gauss(2, 3))) if random.random() > .35 else 0))
            day += dt.timedelta(days=1)
        weeks.append(week)
    return dict(repos=24, stars=12, followers=30, commits=420, prs=18, total=sum(c for w in weeks for _, c in w),
                langs={"Python": 52, "JavaScript": 28, "TypeScript": 9, "C#": 6, "C++": 3, "HTML": 2}, weeks=weeks)


def head(w, h, label, css):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(label)}">'
            f'<title>{escape(label)}</title><style>{css}</style>')


def chrome_grad(c, gid="chrome"):
    return (f'<linearGradient id="{gid}" x1="-1" y1="0" x2="0" y2="0" gradientUnits="objectBoundingBox">'
            f'<stop offset="0" stop-color="{c["lo"]}"/><stop offset=".4" stop-color="{c["lo"]}"/><stop offset=".47" stop-color="{c["mid"]}"/>'
            f'<stop offset=".5" stop-color="{c["hi"]}"/><stop offset=".53" stop-color="{c["mid"]}"/><stop offset=".6" stop-color="{c["lo"]}"/>'
            f'<stop offset="1" stop-color="{c["lo"]}"/><animate attributeName="x1" values="-1;1;-1" dur="9s" repeatCount="indefinite"/>'
            f'<animate attributeName="x2" values="0;2;0" dur="9s" repeatCount="indefinite"/></linearGradient>')


def frame(c, w, h):
    return (f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="22" fill="{c["pearl"]}" stroke="{c["mid"]}" stroke-opacity=".55"/>')


def compact(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def stats_card(d, t, css):
    c = THEMES[t]
    W, H = 900, 250
    nums = [("contributions", d["total"], "last 12 months"), ("commits", d["commits"], "last 12 months"),
            ("public repos", d["repos"], f'{compact(d["stars"])} stars'), ("pull requests", d["prs"], "last 12 months")]
    s = head(W, H, f'GitHub stats: {d["total"]} contributions, {d["commits"]} commits, {d["repos"]} public repos, {d["prs"]} pull requests in the last year', css)
    s += f'<defs>{chrome_grad(c)}<filter id="glow" x="-2" y="-2" width="5" height="5"><feGaussianBlur stdDeviation="3"/></filter></defs>'
    s += frame(c, W, H)
    for i, (label, val, sub) in enumerate(nums):
        x = 40 + i * 122
        s += (f'<text x="{x}" y="96" class="serif" font-size="46" fill="url(#chrome)">{compact(val)}</text>'
              f'<text x="{x}" y="126" class="sans" font-size="10" font-weight="400" letter-spacing="1.2" fill="{c["ink"]}">{label.upper()}</text>'
              f'<text x="{x}" y="146" class="sans" font-size="11" font-weight="300" fill="{c["muted"]}">{escape(sub)}</text>')
    # waterline + lanterns
    s += f'<rect x="40" y="176" width="420" height="1" fill="{c["mid"]}" opacity=".6"/>'
    for i, x in enumerate([90, 210, 330, 430]):
        s += (f'<g><circle cx="{x}" cy="176" r="7" fill="{c["jade"]}" opacity=".4" filter="url(#glow)"/><circle cx="{x}" cy="176" r="3" fill="{c["lantern"]}" stroke="{c["mid"]}" stroke-width=".6"/>'
              f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" dur="{6 + i}s" repeatCount="indefinite"/></g>')
    s += f'<text x="40" y="214" class="sans" font-size="12" font-weight="300" fill="{c["muted"]}">@{escape(LOGIN)} · updated {dt.date.today():%b %d, %Y}</text>'
    # languages
    total = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    lx, lw = 520, 340
    s += f'<text x="{lx}" y="58" class="sans" font-size="11" letter-spacing="1.8" fill="{c["muted"]}">TOP LANGUAGES</text>'
    s += f'<clipPath id="bar"><rect x="{lx}" y="74" width="{lw}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)"><rect x="{lx}" y="74" width="{lw}" height="12" fill="{c["empty"]}"/>'
    x = lx
    for i, (name, v) in enumerate(top):
        w = lw * v / total
        s += f'<rect x="{x:.1f}" y="74" width="{w + .6:.1f}" height="12" fill="{c[LANG_COLORS[i % len(LANG_COLORS)]]}"/>'
        x += w
    s += '</g>'
    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        x, y = lx + col * 175, 118 + row * 30
        s += (f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{c[LANG_COLORS[i % len(LANG_COLORS)]]}"/>'
              f'<text x="{x + 18}" y="{y}" class="sans" font-size="13.5" font-weight="400" fill="{c["ink"]}">{escape(name)}</text>'
              f'<text x="{x + 160}" y="{y}" text-anchor="end" class="sans" font-size="12.5" font-weight="300" fill="{c["muted"]}">{100 * v / total:.1f}%</text>')
    return s + '</svg>'


def calendar(d, t, css):
    c = THEMES[t]
    weeks = d["weeks"][-53:]
    cell, gap = 13, 3
    W = 40 + len(weeks) * (cell + gap) + 30
    H = 222
    counts = sorted(n for w in weeks for _, n in w if n > 0)
    q = [counts[int(len(counts) * f)] if counts else 1 for f in (.25, .5, .75)] if counts else [1, 2, 3]

    def color(n):
        if n == 0:
            return c["empty"]
        return c["heat"][0 if n <= q[0] else 1 if n <= q[1] else 2 if n <= q[2] else 3]

    s = head(W, H, f'{d["total"]} contributions in the last year', css)
    s += f'<defs>{chrome_grad(c)}</defs>' + frame(c, W, H)
    s += (f'<text x="40" y="52" class="serif" font-size="30" fill="url(#chrome)">{d["total"]:,} contributions</text>'
          f'<text x="{W - 40}" y="50" text-anchor="end" class="sans" font-size="12" font-weight="300" fill="{c["muted"]}">the last 12 months</text>')
    y0 = 74
    last_month = None
    for i, w in enumerate(weeks):
        x = 40 + i * (cell + gap)
        m = dt.date.fromisoformat(w[0][0]).strftime("%b")
        if m != last_month and i < len(weeks) - 2:
            s += f'<text x="{x}" y="{y0 - 8}" class="sans" font-size="10" fill="{c["muted"]}">{m}</text>'
            last_month = m
        for date, n in w:
            wd = (dt.date.fromisoformat(date).weekday() + 1) % 7
            s += f'<rect x="{x}" y="{y0 + wd * (cell + gap)}" width="{cell}" height="{cell}" rx="3.5" fill="{color(n)}"><title>{n} on {date}</title></rect>'
    ly = y0 + 7 * (cell + gap) + 18
    s += f'<text x="{W - 40 - 5 * (cell + 4) - 40}" y="{ly + 10}" text-anchor="end" class="sans" font-size="10.5" fill="{c["muted"]}">less</text>'
    for k, col in enumerate([c["empty"]] + c["heat"]):
        s += f'<rect x="{W - 40 - 5 * (cell + 4) - 32 + k * (cell + 4)}" y="{ly}" width="{cell}" height="{cell}" rx="3.5" fill="{col}"/>'
    s += f'<text x="{W - 40}" y="{ly + 10}" text-anchor="end" class="sans" font-size="10.5" fill="{c["muted"]}">more</text>'
    return s + '</svg>'


def main():
    d = demo() if "--demo" in sys.argv else fetch()
    css = font_css()
    os.makedirs(OUT, exist_ok=True)
    for t in THEMES:
        with open(os.path.join(OUT, f"stats-{t}.svg"), "w", encoding="utf-8") as f:
            f.write(stats_card(d, t, css))
        with open(os.path.join(OUT, f"contributions-{t}.svg"), "w", encoding="utf-8") as f:
            f.write(calendar(d, t, css))
    print(f"Wrote stats for {LOGIN}: {d['total']} contributions, {d['repos']} repos")


if __name__ == "__main__":
    main()
