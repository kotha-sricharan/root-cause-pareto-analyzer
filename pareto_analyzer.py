#!/usr/bin/env python3
"""Root-cause Pareto analyzer for manufacturing defect logs.

Loads a defect/incident log CSV and produces:
  * Pareto analysis of defect codes (80/20, cumulative %)
  * A Pareto chart (PNG) with the 80% cut-off line
  * Fishbone (6M) category grouping: Man / Machine / Method /
    Material / Measurement / Environment
  * A countermeasure action tracker summary (from a JSON file),
    including overdue actions

Usage:
    python pareto_analyzer.py --data data/defects.csv \
        --actions data/countermeasures.json --out output/

    python pareto_analyzer.py --data data/defects.csv --out output/ --top 5

CSV columns: date, line, defect_code, category, units_affected,
              shift, description
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

FISHBONE_CATEGORIES = [
    "Man",
    "Machine",
    "Method",
    "Material",
    "Measurement",
    "Environment",
]

REQUIRED_COLUMNS = {
    "date",
    "line",
    "defect_code",
    "category",
    "units_affected",
    "shift",
    "description",
}

STATUSES = ("open", "in_progress", "done")


def load_defects(path: Path) -> pd.DataFrame:
    """Load the defect log, ignoring '#' comment lines in the header."""
    df = pd.read_csv(path, comment="#", parse_dates=["date"])
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    unknown = sorted(set(df["category"]) - set(FISHBONE_CATEGORIES))
    if unknown:
        print(
            f"Warning: {len(unknown)} categor(ies) outside the 6M fishbone "
            f"set: {unknown}",
            file=sys.stderr,
        )
    return df


def pareto_table(df: pd.DataFrame, top: int) -> pd.DataFrame:
    """Defect codes ranked by incident count, with cumulative %."""
    grouped = (
        df.groupby("defect_code")
        .agg(
            incidents=("defect_code", "size"),
            units_affected=("units_affected", "sum"),
        )
        .sort_values("incidents", ascending=False)
        .reset_index()
    )
    total = grouped["incidents"].sum()
    # Keep full precision internally: cumulative % is cumulative
    # incident counts / total incidents, rounded only for display.
    # The 80% vital-few cutoff below uses these unrounded values.
    grouped["pct_of_incidents"] = grouped["incidents"] / total * 100
    grouped["cumulative_pct"] = grouped["incidents"].cumsum() / total * 100
    grouped["rank"] = range(1, len(grouped) + 1)
    return grouped, total


def category_table(df: pd.DataFrame) -> pd.DataFrame:
    """Fishbone 6M grouping: incidents and units affected per category."""
    grouped = (
        df.groupby("category")
        .agg(
            incidents=("category", "size"),
            units_affected=("units_affected", "sum"),
        )
        .reindex(FISHBONE_CATEGORIES)
        .fillna(0)
    )
    grouped["incidents"] = grouped["incidents"].astype(int)
    grouped["units_affected"] = grouped["units_affected"].astype(int)
    return grouped.sort_values("incidents", ascending=False)


def plot_pareto(pareto: pd.DataFrame, top: int, out_path: Path) -> None:
    """Bar chart of incidents per defect code with cumulative % line."""
    data = pareto.head(top)
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(data["defect_code"], data["incidents"], color="#1f77b4")
    ax.bar_label(bars, fmt="%d")
    ax.set_xlabel("Defect code")
    ax.set_ylabel("Incidents")
    ax.set_title(f"Pareto Analysis — Top {top} Defect Codes (80/20)")

    ax2 = ax.twinx()
    ax2.plot(
        data["defect_code"],
        data["cumulative_pct"],
        color="#d62728",
        marker="o",
        label="Cumulative %",
    )
    ax2.axhline(80, color="#d62728", linestyle="--", linewidth=1)
    ax2.set_ylabel("Cumulative % of incidents")
    ax2.set_ylim(0, 105)
    ax2.legend(loc="center right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_categories(cat: pd.DataFrame, out_path: Path) -> None:
    """Bar chart of incidents per fishbone (6M) category."""
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(cat.index, cat["incidents"], color="#2ca02c")
    ax.bar_label(bars, fmt="%d")
    ax.set_xlabel("Fishbone category (6M)")
    ax.set_ylabel("Incidents")
    ax.set_title("Defects by Root-Cause Category (Fishbone 6M)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def load_actions(path: Path) -> list[dict]:
    """Load the countermeasure action tracker (JSON list of actions)."""
    if path is None:
        return []
    with path.open() as f:
        data = json.load(f)
    actions = data["actions"] if isinstance(data, dict) else data
    for action in actions:
        if action.get("status") not in STATUSES:
            raise ValueError(
                f"Action {action.get('id')}: unknown status "
                f"{action.get('status')!r} (expected one of {STATUSES})"
            )
    return actions


def action_summary(actions: list[dict], today: date) -> dict:
    """Status counts plus overdue actions (past due, not done)."""
    by_status = {s: 0 for s in STATUSES}
    overdue = []
    for action in actions:
        by_status[action["status"]] += 1
        due = date.fromisoformat(action["due_date"])
        if due < today and action["status"] != "done":
            overdue.append(action)
    return {"by_status": by_status, "overdue": overdue, "total": len(actions)}


def write_report(
    df: pd.DataFrame,
    pareto: pd.DataFrame,
    total: int,
    cat: pd.DataFrame,
    actions: list[dict],
    summary: dict,
    today: date,
    out_path: Path,
) -> None:
    """Write the full analysis as a Markdown report."""
    start = df["date"].min().date()
    end = df["date"].max().date()
    # Vital few: every code up to and including the one that first takes
    # the cumulative share to (or past) 80%. The crossing code is part
    # of the vital few — a plain `cumulative_pct <= 80` filter would
    # drop it and leave the selection short of 80%.
    prev_cum = pareto["cumulative_pct"].shift(fill_value=0)
    vital_few = pareto[prev_cum < 80]
    lines = []
    lines.append("# Root-Cause Pareto Report\n")
    lines.append(f"Generated: {today.isoformat()}  ")
    lines.append(f"Period: {start} to {end} ({(end - start).days + 1} days)  ")
    lines.append(f"Total incidents: {total}  ")
    lines.append(
        f"Total units affected: {int(df['units_affected'].sum()):,}  "
    )
    lines.append(f"Lines: {', '.join(sorted(df['line'].unique()))}\n")

    lines.append("## Pareto — defect codes (80/20)\n")
    lines.append("| Rank | Defect code | Incidents | % of total | Cumulative % | Units affected |")
    lines.append("|-----:|-------------|----------:|-----------:|-------------:|---------------:|")
    for row in pareto.itertuples():
        lines.append(
            f"| {row.rank} | {row.defect_code} | {row.incidents} | "
            f"{row.pct_of_incidents:.1f}% | {row.cumulative_pct:.1f}% | "
            f"{row.units_affected:,} |"
        )
    lines.append(
        f"\n**Vital few:** the top {len(vital_few)} defect code(s) "
        f"({', '.join(vital_few['defect_code'])}) account for "
        f"{vital_few['pct_of_incidents'].sum():.1f}% of all incidents — "
        "fix these first to move yield the fastest.\n"
    )

    lines.append("## Fishbone categories (6M)\n")
    lines.append("| Category | Incidents | Units affected |")
    lines.append("|----------|----------:|---------------:|")
    for name, row in cat.iterrows():
        lines.append(f"| {name} | {row['incidents']} | {row['units_affected']:,} |")
    lines.append("")

    lines.append("## Incidents by shift and line\n")
    lines.append("| Shift | Incidents | Units affected |")
    lines.append("|-------|----------:|---------------:|")
    for name, grp in df.groupby("shift"):
        lines.append(
            f"| {name} | {len(grp)} | {int(grp['units_affected'].sum()):,} |"
        )
    lines.append("")
    lines.append("| Line | Incidents | Units affected |")
    lines.append("|------|----------:|---------------:|")
    for name, grp in df.groupby("line"):
        lines.append(
            f"| {name} | {len(grp)} | {int(grp['units_affected'].sum()):,} |"
        )
    lines.append("")

    lines.append("## Countermeasure action tracker\n")
    if not actions:
        lines.append("No action tracker supplied.\n")
    else:
        counts = " | ".join(
            f"{s.replace('_', ' ')}: {summary['by_status'][s]}"
            for s in STATUSES
        )
        lines.append(
            f"**{summary['total']} actions** — {counts}  "
            f"| Overdue: **{len(summary['overdue'])}**\n"
        )
        lines.append(
            "| ID | Defect | Owner | Due | Status | Countermeasure |"
        )
        lines.append("|----|--------|-------|-----|--------|----------------|")
        for a in sorted(actions, key=lambda x: x["due_date"]):
            flag = " ⚠️ OVERDUE" if a in summary["overdue"] else ""
            lines.append(
                f"| {a['id']} | {a['defect_code']} | {a['owner']} | "
                f"{a['due_date']} | {a['status'].replace('_', ' ')}{flag} | "
                f"{a['countermeasure']} |"
            )
        lines.append("")
        lines.append("### Root-cause notes (5-Why)\n")
        for a in actions:
            lines.append(f"- **{a['id']} ({a['defect_code']}):** {a['root_cause']}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pareto + fishbone root-cause analysis of a defect log."
    )
    parser.add_argument("--data", required=True, help="Defect log CSV file")
    parser.add_argument(
        "--actions",
        default=None,
        help="Countermeasure tracker JSON file (optional)",
    )
    parser.add_argument(
        "--out", required=True, help="Output directory for report and charts"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of defect codes in the Pareto chart (default: 8)",
    )
    args = parser.parse_args()

    today = date.today()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_defects(Path(args.data))
    pareto, total = pareto_table(df, args.top)
    cat = category_table(df)
    actions = load_actions(Path(args.actions)) if args.actions else []
    summary = action_summary(actions, today)

    chart_path = out_dir / "pareto_chart.png"
    cat_chart_path = out_dir / "category_chart.png"
    report_path = out_dir / "pareto_report.md"
    plot_pareto(pareto, args.top, chart_path)
    plot_categories(cat, cat_chart_path)
    write_report(df, pareto, total, cat, actions, summary, today, report_path)

    print(f"Period: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Total incidents: {total}")
    print(f"Total units affected: {int(df['units_affected'].sum()):,}")
    print("\nTop defect codes (Pareto):")
    for row in pareto.head(args.top).itertuples():
        print(
            f"  {row.defect_code}: {row.incidents} incidents "
            f"({row.pct_of_incidents:.1f}%, cumulative {row.cumulative_pct:.1f}%)"
        )
    print("\nFishbone categories (6M):")
    for name, row in cat.iterrows():
        print(f"  {name}: {row['incidents']} incidents")
    print("\nCountermeasure actions:")
    for status in STATUSES:
        print(f"  {status}: {summary['by_status'][status]}")
    print(f"  overdue: {len(summary['overdue'])}")
    for a in summary["overdue"]:
        print(f"    - {a['id']} ({a['defect_code']}), due {a['due_date']}")
    print(f"\nWrote: {report_path}")
    print(f"Wrote: {chart_path}")
    print(f"Wrote: {cat_chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
