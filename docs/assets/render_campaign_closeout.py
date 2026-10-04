"""Render campaign 2 outcome counts from its frozen closeout; standard library only."""
import argparse
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "experiments" / "campaign-150-rerun-01.json"
TARGET = HERE / "campaign-150-rerun-01-outcomes.svg"
FIELDS = ("success", "evaluated_failure", "incident")


def aggregate(data):
    """Keep each planned assignment, including incidents, in the displayed counts."""
    groups = {}
    for row in data["by_task_and_condition"]:
        values = [row[field] for field in (*FIELDS, "planned")]
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("Outcome counts must be nonnegative integers.")
        if sum(values[:3]) != values[3]:
            raise ValueError("Terminal outcomes must sum to planned assignments.")
        key = (row["model"], row["configuration"])
        group = groups.setdefault(key, dict.fromkeys((*FIELDS, "planned"), 0))
        for field, value in zip((*FIELDS, "planned"), values):
            group[field] += value
    for field in (*FIELDS, "planned"):
        if sum(group[field] for group in groups.values()) != data["totals"][field]:
            raise ValueError("Grouped counts disagree with the campaign totals.")
    expected = {(model, condition) for model in ("gpt-5.6-luna", "gpt-5.6-sol")
                for condition in "ABC"}
    if set(groups) != expected or any(group["planned"] != 25 for group in groups.values()):
        raise ValueError("This frozen figure requires six groups of 25 assignments.")
    return groups


def render(data):
    groups = aggregate(data)
    descriptions = []
    for (model, condition), group in sorted(groups.items()):
        descriptions.append(f'{model} {condition}: {group["success"]} successes, '
                            f'{group["evaluated_failure"]} evaluated failures, '
                            f'{group["incident"]} unscored incidents out of 25.')
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 510" role="img" aria-labelledby="title desc">',
             '<title id="title">Campaign 2: terminal outcomes by setup and condition</title>',
             f'<desc id="desc">{escape(" ".join(descriptions))} Descriptive counts; no causal comparison.</desc>',
             '<style>text{font-family:system-ui,-apple-system,sans-serif;fill:#1f2328;font-size:14px}'
             '.bg{fill:white}.grid{stroke:#d0d7de}.luna{fill:#0969da}.sol{fill:#bc4c00}'
             '.failure{fill:#f5b5b0}.caption{font-size:12px}.value{font-weight:650}</style>',
             '<defs><pattern id="incident" width="6" height="6" patternUnits="userSpaceOnUse">'
             '<rect width="6" height="6" fill="#eaeef2"/>'
             '<path d="M-1 1L1-1M0 6L6 0M5 7L7 5" stroke="#57606a"/></pattern></defs>',
             '<rect class="bg" width="820" height="510" rx="10"/>',
             '<text x="80" y="30" class="value">Campaign 2 · October 2026 · 150 planned assignments</text>']
    for x, fill, label in ((80, '#0969da', 'Luna success'), (250, '#bc4c00', 'Sol success'),
                           (410, '#f5b5b0', 'Evaluated failure'), (600, 'url(#incident)', 'Unscored incident')):
        parts += [f'<rect x="{x}" y="50" width="14" height="14" fill="{fill}"/>',
                  f'<text x="{x + 22}" y="62">{label}</text>']
    for tick in range(0, 26, 5):
        y = 370 - 10 * tick
        parts += [f'<path class="grid" d="M80 {y}H785"/>',
                  f'<text x="68" y="{y + 5}" text-anchor="end">{tick}</text>']
    parts.append('<text transform="translate(25 245) rotate(-90)" text-anchor="middle">Assignment count</text>')
    for j, condition in enumerate("ABC"):
        center = 195 + 235 * j
        for i, model in enumerate(("gpt-5.6-luna", "gpt-5.6-sol")):
            group = groups[(model, condition)]
            x = center - 72 + 78 * i
            y = 370
            for field in FIELDS:
                count = group[field]
                height = count * 10
                y -= height
                fill = ('#0969da' if i == 0 else '#bc4c00') if field == 'success' else (
                    '#f5b5b0' if field == 'evaluated_failure' else 'url(#incident)')
                parts.append(f'<rect x="{x}" y="{y}" width="66" height="{height}" fill="{fill}"/>')
            parts += [f'<text x="{x + 33}" y="104" text-anchor="middle" class="value">'
                      f'{group["success"]} / 25</text>',
                      f'<text x="{x + 33}" y="392" text-anchor="middle">{("Luna", "Sol")[i]}</text>']
        parts.append(f'<text x="{center}" y="420" text-anchor="middle" class="value">{condition}</text>')
    parts += ['<text x="80" y="451" class="caption">A: construction · B: A + boundaries · C: B + smoke · labels: diagnostic successes / planned</text>',
              '<text x="80" y="474" class="caption">16 requests / 600 seconds · five reused tasks × five repeats · zero retries</text>',
              '<text x="80" y="495" class="caption">Incidents remain unscored. Scientific review pending. Counts do not establish a tool effect.</text>',
              '</svg>']
    return '\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify the retained SVG without writing.')
    args = parser.parse_args()
    svg = render(json.loads(SOURCE.read_text()))
    if args.check:
        if TARGET.read_text() != svg:
            raise SystemExit('SVG differs from the frozen closeout and generator.')
        print('SVG matches the frozen closeout and generator.')
    else:
        TARGET.write_text(svg)


if __name__ == '__main__':
    main()
