# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "duckdb==1.4.1",
#     "marimo",
#     "sqlglot==27.29.0",
# ]
# ///

import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Marimo Edit/Publish Mode Example

    This mod demonstrates marimo's two modes:
    - **Edit mode** (default): Interactive notebook editing with live updates
    - **Publish mode**: Read-only view for end users

    Switch modes using the `MARIMO_MODE` environment variable.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Mode Configuration

    **Development:**
    ```bash
    # Edit mode (default)
    ./dev.py mods/marimo

    # Publish mode
    MARIMO_MODE=publish ./dev.py mods/marimo
    ```

    **Production:**
    ```bash
    # Edit mode (default)
    docker run -p 6637:6637 localhost/marimo-example:latest

    # Publish mode
    docker run -p 6637:6637 -e MARIMO_MODE=publish localhost/marimo-example:latest
    ```
    """)
    return


@app.cell
def _(mo):
    # Interactive slider example
    slider = mo.ui.slider(start=0, stop=100, value=50, label="Adjust value:")
    slider
    return (slider,)


@app.cell
def _(mo, slider):
    mo.md(f"""
    **Current value:** {slider.value}
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Try Editing!

    In **edit mode**, you can:
    - Modify code cells and see results update automatically
    - Add new cells
    - Reorganize the notebook structure
    - Save changes

    In **publish mode**, the notebook is read-only for viewers.
    """)
    return


if __name__ == "__main__":
    app.run()
