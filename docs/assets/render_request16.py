"""Render the frozen public Request-16 rates; standard library only."""
import argparse
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render(data):
    """Draw reported rates without estimating intervals or new outcomes."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 470" role="img" aria-labelledby="title desc">',
             '<title id="title">Request-16 development study: verified protocol success</title>',
             '<desc id="desc">Luna A 72%, B 68%, C 56%. Sol A 92%, B 100%, C 84%. '
             '150 assignments; five tasks and five repeats per setup and condition. '
             'Descriptive rates without significance claims.</desc>',
             '<style>text{font-family:system-ui,-apple-system,sans-serif;fill:#1f2328;font-size:14px}'
             '.bg{fill:#ffffff}.grid{stroke:#d0d7de;stroke-width:1}.luna{fill:#0969da}'
             '.sol{fill:#bc4c00}.value{font-weight:650}.caption{font-size:12px}'
             '@media(prefers-color-scheme:dark){text{fill:#e6edf3}.bg{fill:#0d1117}'
             '.grid{stroke:#3d444d}.luna{fill:#58a6ff}.sol{fill:#f0883e}}</style>',
             '<rect class="bg" width="780" height="470" rx="10"/>',
             '<text x="84" y="29" font-size="18" font-weight="650">Request-16 development study</text>']
    for i, series in enumerate(data["series"]):
        x = 84 + 214 * i
        cls = ("luna", "sol")[i]
        parts += [f'<rect class="{cls}" x="{x}" y="45" width="14" height="14"/>',
                  f'<text x="{x + 22}" y="57">{escape(series["setup"])}</text>']
    for tick in range(0, 101, 20):
        y = 360 - 2.6 * tick
        parts += [f'<path class="grid" d="M84 {y:g}H748"/>',
                  f'<text x="72" y="{y + 5:g}" text-anchor="end">{tick}</text>']
    parts.append('<text transform="translate(23 230) rotate(-90)" text-anchor="middle">Verified protocol success (%)</text>')
    for j, condition in enumerate(data["conditions"]):
        center = 200 + j * 218
        for i, series in enumerate(data["series"]):
            value = series["percent"][j]
            x, height = center - 66 + i * 72, 2.6 * value
            parts += [f'<rect class="{("luna", "sol")[i]}" x="{x}" y="{360 - height:g}" width="60" height="{height:g}"/>',
                      f'<text class="value" x="{x + 30}" y="{350 - height:g}" text-anchor="middle">{value}%</text>']
        parts.append(f'<text class="value" x="{center}" y="385" text-anchor="middle">{escape(condition)}</text>')
    parts += ['<text class="caption" x="84" y="414">A: guided construction · B: A + boundaries · C: B + smoke</text>',
              '<text class="caption" x="84" y="437">150 sessions · five tasks × five repeats per setup/condition · zero retries</text>',
              '<text class="caption" x="84" y="456">Equal task weights; the unresolved Sol/C incident remains in the denominator.</text>',
              '</svg>']
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the committed SVG without writing.")
    args = parser.parse_args()
    svg = render(json.loads((HERE / "request16-success-rates.json").read_text()))
    target = HERE / "request16-success-rates.svg"
    if args.check:
        if target.read_text() != svg:
            raise SystemExit("SVG differs from the frozen data and generator.")
        print("SVG matches the frozen data and generator.")
    else:
        target.write_text(svg)


if __name__ == "__main__":
    main()
