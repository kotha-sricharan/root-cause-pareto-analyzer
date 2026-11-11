# Root-Cause Pareto Analyzer

A command-line tool that turns a manufacturing defect log into a prioritized
root-cause action plan: Pareto analysis (80/20), a Pareto chart, fishbone
(6M) category grouping, and a countermeasure action tracker.

Built by **Sri Charan Kotha**.

> **Sample data is synthetic.** `data/defects.csv` and
> `data/countermeasures.json` are generated demo data for an NCM battery-cell
> production line. They are not real production data and are not connected to
> any employer. This project demonstrates the *method* (Pareto + 5-Why +
> countermeasure tracking), not any company's actual defects.

## Why this project exists

It practices the exact work a process technician does every shift:

| Job duty | How this tool maps to it |
|---|---|
| Rapid response on out-of-control processes | Load the latest defect log and see in seconds which defect codes are spiking — the Pareto table ranks them by incident count and units affected |
| Determine root cause | Defects are grouped into fishbone (6M) categories — Man / Machine / Method / Material / Measurement / Environment — so the investigation starts in the right place |
| Implement countermeasures to improve yield | The countermeasure tracker links each action to a defect code, a 5-Why root-cause note, an owner, and a due date, and flags overdue actions |
| Improve process and product yield | The "vital few" line in the report names the smallest set of defect codes behind ~80% of incidents — fix those first to move yield fastest |
| Lean / continuous improvement, 5S | The tracker is the closed-loop part: every countermeasure has a status (`open` / `in_progress` / `done`), so improvements are tracked to completion instead of being forgotten |
| Manage small cross-department projects | Actions carry owners across Process Engineering, Maintenance, Quality, and Production, with due dates and an overdue report |

## What it produces

Running the tool on the sample data writes three files to `output/`:

- **`pareto_report.md`** — full report: Pareto table with cumulative %,
  the "vital few", fishbone category totals, incidents by shift and line,
  and the countermeasure tracker with overdue flags and 5-Why notes.
- **`pareto_chart.png`** — bar chart of incidents per defect code with the
  cumulative-% line and the 80% cut-off.
- **`category_chart.png`** — incidents per fishbone (6M) category.

## How to run

```bash
pip install -r requirements.txt

python pareto_analyzer.py --data data/defects.csv \
    --actions data/countermeasures.json --out output/
```

Options:

- `--top N` — number of defect codes shown in the Pareto chart (default 8)
- `--actions` — optional; omit it to run the Pareto analysis without the
  action tracker

Regenerate the sample data any time (fixed seed, reproducible):

```bash
python scripts/generate_sample_data.py
```

## Sample output

On the bundled synthetic data (343 incidents, 2026-09-28 to 2026-11-06):

```
Top defect codes (Pareto):
  ELEC-101: 95 incidents (27.7%, cumulative 27.7%)
  WELD-204: 70 incidents (20.4%, cumulative 48.1%)
  SEAL-310: 42 incidents (12.2%, cumulative 60.3%)
  CONT-118: 33 incidents (9.6%, cumulative 69.9%)
  ALIGN-207: 30 incidents (8.7%, cumulative 78.6%)

Countermeasure actions:
  open: 2
  in_progress: 2
  done: 2
  overdue: 1
```

The top 5 defect codes drive 78.6% of incidents; adding TEMP-330
(8.5%) crosses the 80% line at 87.1% — so the vital few are the top 6
codes, and the countermeasure effort starts with ELEC-101 and
WELD-204.

## Input format

**Defect log CSV** — columns: `date, line, defect_code, category,
units_affected, shift, description`. Lines starting with `#` are treated
as comments. `category` must be one of the fishbone 6M values: Man,
Machine, Method, Material, Measurement, Environment.

**Countermeasure tracker JSON** — a list (or `{"actions": [...]}` object)
of actions, each with:

```json
{
  "id": "CA-001",
  "defect_code": "ELEC-101",
  "root_cause": "5-Why notes...",
  "countermeasure": "What will be changed",
  "owner": "Process Engineering",
  "due_date": "2026-11-06",
  "status": "done"
}
```

Status must be `open`, `in_progress`, or `done`. An action is **overdue**
when its due date has passed and it is not `done`.

## Tech

Python 3.12 · pandas · numpy · matplotlib (no other dependencies).

## License

MIT — see [LICENSE](LICENSE).
