"""Genera assets/stats.svg con datos reales de GitHub. Corre en GitHub Actions."""
import json, os, sys, urllib.request
from datetime import date
from html import escape

USER = os.environ.get("GH_USER", "sannngaitan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

LANG_COLORS = {
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "Python": "#3572A5",
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#663399",
    "C#": "#178600", "PHP": "#4F5D95", "Shell": "#89e051", "SQL": "#e38c00", "TSQL": "#e38c00",
    "Jupyter Notebook": "#DA5B0B", "Kotlin": "#A97BFF", "Go": "#00ADD8", "Rust": "#dea584",
    "Vue": "#41b883", "Dart": "#00B4AB", "QML": "#44a51c", "CMake": "#DA3434",
}
SKIP_LANGS = {"CMake", "Makefile", "Batchfile", "PowerShell", "Dockerfile"}


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    u = gql(QUERY, {"login": USER})["user"]
    repos = u["repositories"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    langs = {}
    colors = {}
    for n in repos["nodes"]:
        for e in n["languages"]["edges"]:
            name = e["node"]["name"]
            if name in SKIP_LANGS:
                continue
            langs[name] = langs.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or LANG_COLORS.get(name, "#8b949e")
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    today = date.today().isoformat()
    days = [d for d in days if d["date"] <= today]
    streak, best, run = 0, 0, 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        best = max(best, run)
    i = len(days) - 1
    if i >= 0 and days[i]["contributionCount"] == 0:
        i -= 1  # hoy todavia no cuenta como racha cortada
    while i >= 0 and days[i]["contributionCount"] > 0:
        streak += 1
        i -= 1
    return {
        "contribs": cal["totalContributions"],
        "streak": streak,
        "best": best,
        "repos": repos["totalCount"],
        "stars": stars,
        "followers": u["followers"]["totalCount"],
        "langs": langs,
        "colors": colors,
    }


THEMES = {
    "light": ":root {{ --bg:#ffffff; --fg:#1f2328; --mute:#656d76; --line:#d0d7de; --track:#eaeef2; }}",
    "dark": ":root {{ --bg:#0d1117; --fg:#e6edf3; --mute:#7d8590; --line:#30363d; --track:#21262d; }}",
}


def render(s, theme):
    W, H = 840, 172
    total = sum(s["langs"].values()) or 1
    top = sorted(s["langs"].items(), key=lambda kv: -kv[1])[:6]

    metrics = [
        ("contribuciones", s["contribs"], "último año"),
        ("racha actual", s["streak"], f"mejor: {s['best']} días"),
        ("repos", s["repos"], f"★ {s['stars']}"),
    ]
    mx = 40
    m_svg = ""
    for k, (label, val, hint) in enumerate(metrics):
        x = mx + k * 135
        m_svg += (
            f'<g class="fade" style="animation-delay:{.1 + k * .12:.2f}s">'
            f'<text x="{x}" y="74" class="num">{escape(str(val))}</text>'
            f'<text x="{x}" y="100" class="lbl">{escape(label)}</text>'
            f'<text x="{x}" y="120" class="hint">{escape(hint)}</text></g>'
        )

    bx, bw, by = 470, 330, 52
    bar, legend, cx = "", "", bx
    for k, (name, size) in enumerate(top):
        w = max(size / total * bw, 3)
        col = s["colors"].get(name, "#8b949e")
        bar += f'<rect x="{cx:.1f}" y="{by}" width="{w:.1f}" height="8" fill="{col}"/>'
        cx += w
        lx = bx + (k % 2) * 170
        ly = by + 34 + (k // 2) * 24
        pct = size / total * 100
        legend += (
            f'<g class="fade" style="animation-delay:{.3 + k * .07:.2f}s">'
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="4.5" fill="{col}"/>'
            f'<text x="{lx + 16}" y="{ly}" class="lang">{escape(name)}'
            f'<tspan class="hint" dx="6">{pct:.1f}%</tspan></text></g>'
        )
    if not top:
        legend = f'<text x="{bx}" y="{by + 34}" class="hint">todavía sin código público</text>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
  {THEMES[theme].replace("{{", "{").replace("}}", "}")}
  text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
  .num {{ fill: var(--fg); font-size: 34px; font-weight: 700; letter-spacing: -1px; }}
  .lbl {{ fill: var(--fg); font-size: 14px; }}
  .hint {{ fill: var(--mute); font-size: 12px; }}
  .lang {{ fill: var(--fg); font-size: 13px; }}
  .fade {{ opacity: 0; animation: in .6s ease-out forwards; }}
  @keyframes in {{ to {{ opacity: 1; }} }}
  .grow {{ transform-origin: {bx}px 0; transform: scaleX(0); animation: grow 1s cubic-bezier(.2,.7,.2,1) .2s forwards; }}
  @keyframes grow {{ to {{ transform: scaleX(1); }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="var(--bg)" stroke="var(--line)"/>
{m_svg}
<line x1="440" y1="36" x2="440" y2="140" stroke="var(--line)"/>
<text x="{bx}" y="38" class="hint">lenguajes</text>
<clipPath id="r"><rect x="{bx}" y="{by}" width="{bw}" height="8" rx="4"/></clipPath>
<rect x="{bx}" y="{by}" width="{bw}" height="8" rx="4" fill="var(--track)"/>
<g clip-path="url(#r)"><g class="grow">{bar}</g></g>
{legend}
<text x="40" y="150" class="hint">actualizado {date.today().strftime("%d/%m/%Y")}</text>
</svg>
'''


if __name__ == "__main__":
    if "--demo" in sys.argv:
        data = {"contribs": 0, "streak": 0, "best": 0, "repos": 0, "stars": 0, "followers": 0,
                "langs": {}, "colors": {}}
        if "--sample" in sys.argv:
            data.update(contribs=214, streak=6, best=19, repos=12, stars=9,
                        langs={"Java": 50, "C++": 22, "HTML": 12, "CSS": 8, "Python": 5, "JavaScript": 3},
                        colors=LANG_COLORS)
    else:
        data = fetch()
    for theme in THEMES:
        with open(os.path.join(ASSETS, f"stats-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(data, theme))
    print("ok", {k: v for k, v in data.items() if k not in ("langs", "colors")})
