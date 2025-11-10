import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium", layout_file="layouts/app.grid.json")


@app.cell
def _():
    import json

    import marimo as mo

    from utils import (
        apply_run_filters,
        resolve_entity_project,
    )
    from utils import fetch_artifacts as _fetch_artifacts
    from utils import fetch_runs as _fetch_runs

    # Wrap fetch functions with caching
    fetch_runs = mo.cache(_fetch_runs)
    fetch_artifacts = mo.cache(_fetch_artifacts)

    ENTITY, PROJECT = resolve_entity_project()
    missing_banner = (
        None
        if PROJECT
        else mo.md(
            "⚠️ **Warning:** WANDB_PROJECT is not set. Set it to `entity/project` or just `project` "
            "(optionally with WANDB_ENTITY), then restart."
        )
    )
    return (
        ENTITY,
        PROJECT,
        apply_run_filters,
        fetch_artifacts,
        fetch_runs,
        json,
        missing_banner,
        mo,
    )


@app.cell
def _(mo):
    search_box = mo.ui.text(placeholder="Filter by run name / tag / id…")
    state_filter = mo.ui.multiselect(
        options=["running", "finished", "failed", "crashed", "queued", "preempted"],
        value=[],
        label="State",
    )
    tag_filter = mo.ui.text(placeholder="Comma-separated tags (optional)")
    metric_sort = mo.ui.text(placeholder="Metric to sort by (e.g. val/loss)")
    sort_desc = mo.ui.switch(value=True, label="Sort desc")
    type_input = mo.ui.text(placeholder="Optional artifact type (e.g. dataset, model)")
    return (
        metric_sort,
        search_box,
        sort_desc,
        state_filter,
        tag_filter,
        type_input,
    )


@app.cell
def _(ENTITY, PROJECT, fetch_runs, missing_banner, mo):
    from utils import short_run_row

    def page_dashboard():
        if missing_banner:
            return missing_banner
        runs = fetch_runs(ENTITY, PROJECT)
        # fetch_runs returns a list on success, or a mo.md() object on error
        if not isinstance(runs, list):
            return runs  # Return the error message

        total = len(runs)
        finished = sum(1 for r in runs if getattr(r, "state", "") == "finished")
        failed = sum(
            1 for r in runs if getattr(r, "state", "") in {"failed", "crashed"}
        )
        running = sum(1 for r in runs if getattr(r, "state", "") == "running")

        cards = mo.hstack(
            [
                mo.md(f"### Total\n**{total}**"),
                mo.md(f"### Finished\n**{finished}**"),
                mo.md(f"### Running\n**{running}**"),
                mo.md(f"### Failed\n**{failed}**"),
            ],
            gap="1rem",
            wrap=True,
        )

        rows = [short_run_row(r) for r in runs[:20]]
        table = mo.ui.table(rows) if rows else mo.md("_No runs yet._")

        return mo.vstack(
            [
                mo.md(f"# W&B: {ENTITY + '/' if ENTITY else ''}{PROJECT}"),
                mo.md("Welcome! Use the nav to browse Runs and Artifacts."),
                cards,
                mo.md("## Recent runs"),
                table,
            ],
            gap="1rem",
        )

    return page_dashboard, short_run_row


@app.cell
def _(ENTITY, PROJECT, json, mo):
    from utils import api

    def run_details(run_id: str):
        a = api()
        try:
            path = f"{ENTITY}/{PROJECT}" if ENTITY else PROJECT
            run = a.run(f"{path}/{run_id}")
        except Exception as e:
            return mo.md(f"❌ **Error:** Unable to load run {run_id}: {e}")

        summary = dict(getattr(run, "summary", {}) or {})
        scalars = {
            k: v for k, v in summary.items() if isinstance(v, (int, float, str, bool))
        }
        cfg = dict(getattr(run, "config", {}) or {})

        def _short(v):
            s = str(v)
            return (s[:200] + "…") if len(s) > 200 else s

        short_cfg = {k: _short(v) for k, v in cfg.items()}

        # history preview
        hist_keys = [
            k for k in summary.keys() if isinstance(summary.get(k), (int, float))
        ][:4] or ["step"]
        try:
            df = run.history(keys=hist_keys, pandas=True)  # type: ignore
        except Exception:
            df = None

        blocks = [
            mo.md(
                f"### {getattr(run, 'name', '') or run_id}  \n_State:_ **{getattr(run, 'state', '')}**"
            ),
            mo.md(
                "**Summary**\n```json\n"
                + (json.dumps(scalars, indent=2) if scalars else "{}")
                + "\n```"
            ),
            mo.md(
                "**Config (truncated)**\n```json\n"
                + (json.dumps(short_cfg, indent=2) if short_cfg else "{}")
                + "\n```"
            ),
        ]
        if df is not None and len(df) > 0:
            num_cols = [c for c in df.columns if c != "_step"]
            if num_cols:
                x = "_step" if "_step" in df.columns else (df.index.name or "index")
                y = num_cols[0]
                blocks.append(mo.ui.plot.line(df, x=x, y=y, title=f"{y} over time"))
            blocks.append(mo.ui.table(df.tail(50).to_dict(orient="records")))
        return mo.vstack(blocks, gap="0.75rem")

    return (run_details,)


@app.cell
def _(
    ENTITY,
    PROJECT,
    apply_run_filters,
    details,
    fetch_runs,
    metric_sort,
    missing_banner,
    mo,
    run_select,
    search_box,
    short_run_row,
    show_btn,
    sort_desc,
    state_filter,
    tag_filter,
):
    def page_runs():
        if missing_banner:
            return missing_banner
        runs = fetch_runs(ENTITY, PROJECT)
        # fetch_runs returns a list on success, or a mo.md() object on error
        if not isinstance(runs, list):
            return runs  # Return the error message

        rows = [short_run_row(r) for r in runs]
        filtered = apply_run_filters(
            rows,
            search_query=search_box.value or "",
            states=state_filter.value or [],
            tag_query=tag_filter.value or "",
            metric=metric_sort.value or "",
            sort_desc=sort_desc.value,
        )

        controls = mo.hstack(
            [search_box, state_filter, tag_filter, metric_sort, sort_desc],
            gap="0.75rem",
            wrap=True,
        )
        table = (
            mo.ui.table(filtered, page_size=25)
            if filtered
            else mo.md("_No runs match._")
        )

        return mo.vstack(
            [
                mo.md("# Runs"),
                controls,
                mo.hstack([run_select, show_btn], gap="0.5rem"),
                details or mo.md("_Pick a run to see details._"),
                mo.md("## All matching runs"),
                table,
            ],
            gap="1rem",
        )

    return (page_runs,)


@app.cell
def _(ENTITY, PROJECT, fetch_runs, mo, short_run_row):
    # Create UI elements for run selection
    # These need to be in a separate cell from where we access their values
    if not PROJECT:
        run_choices = []
    else:
        runs = fetch_runs(ENTITY, PROJECT)
        if isinstance(runs, list) and runs:
            rows = [short_run_row(r) for r in runs]
            # Don't apply filters here - just show all runs
            # Filtering happens in page_runs
            run_choices = [(f"{r['name']} ({r['id']})", r["id"]) for r in rows[:500]]
        else:
            run_choices = []
    run_select = mo.ui.dropdown(options=run_choices, label="Select a run…")
    show_btn = mo.ui.button("Show details")
    return run_select, show_btn


@app.cell
def _(run_details, run_select, show_btn):
    # Access UI element values in a separate cell from where they were created
    details = (
        run_details(run_select.value) if show_btn.value and run_select.value else None
    )
    return (details,)


@app.cell
def _(ENTITY, PROJECT, fetch_artifacts, missing_banner, mo, type_input):
    def page_artifacts():
        if missing_banner:
            return missing_banner
        arts = fetch_artifacts(
            ENTITY, PROJECT, type_filter=lambda: (type_input.value or None)
        )
        # fetch_artifacts returns a list on success, or a mo.md() object on error
        if not isinstance(arts, list):
            return arts  # Return the error message
        else:
            rows = [
                {
                    "name": getattr(a, "name", ""),
                    "type": getattr(a, "type", ""),
                    "version": getattr(a, "version", ""),
                    "aliases": ", ".join(getattr(a, "aliases", []) or []),
                    "created_at": str(getattr(a, "created_at", "")),
                }
                for a in arts
            ]
            table = (
                mo.ui.table(rows, page_size=25)
                if rows
                else mo.md("_No artifacts found._")
            )
        return mo.vstack(
            [
                mo.md("# Artifacts"),
                mo.hstack([mo.md("Filter by type:"), type_input], gap="0.5rem"),
                table,
            ],
            gap="1rem",
        )

    return (page_artifacts,)


@app.cell
def _(mo, page_artifacts, page_dashboard, page_runs):
    nav = mo.nav_menu(
        {
            "#/": "🏠 Dashboard",
            "#/runs": "📈 Runs",
            "#/artifacts": "📦 Artifacts",
        }
    )
    routes = mo.routes(
        {
            "#/": page_dashboard,
            "#/runs": page_runs,
            "#/artifacts": page_artifacts,
            mo.routes.CATCH_ALL: page_dashboard,  # default
        }
    )
    return nav, routes


@app.cell
def _(mo, nav, routes):
    mo.vstack([nav, routes], gap="1.25rem")
    return


if __name__ == "__main__":
    app.run()
