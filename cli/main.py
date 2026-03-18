import json
from pathlib import Path

import typer

from agents.runtime_env import load_environment

app = typer.Typer(help="AtlasFabric — Historical boundary generation engine.")


@app.command()
def generate(
    year: int = typer.Option(..., "--year", "-y", help="Historical year to generate"),
    region: str = typer.Option(..., "--region", "-r", help="Region name (see geo/regions.py)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without storing to MongoDB"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write config JSON to file"),
):
    """Run the historical boundary generation pipeline."""
    from agents.tracing import configure_tracing
    from geo.regions import list_regions

    load_environment()

    valid_regions = list_regions()

    if region not in valid_regions:
        typer.echo(f"Error: Unknown region '{region}'. Valid: {valid_regions}", err=True)
        raise typer.Exit(1)

    configure_tracing(run_name=f"generate-{year}-{region}")
    typer.echo(f"Generating year={year} region={region} dry_run={dry_run}")

    from agents.orchestrator import run_pipeline

    state = run_pipeline(year=year, region=region, dry_run=dry_run)

    decision = state.get("review_decision", "unknown")
    typer.echo(f"Review decision: {decision}")

    if decision in ("approved", "partial"):
        typer.echo("Generation successful.")
        if output:
            config = state.get("map_config", {})
            output.write_text(json.dumps(config, indent=2))
            typer.echo(f"Config written to {output}")
    else:
        feedback = state.get("review_feedback", "No feedback available.")
        typer.echo("Generation failed after all retries.", err=True)
        typer.echo(f"Last feedback: {feedback}", err=True)
        raise typer.Exit(1)


@app.command()
def regions():
    """List all supported region names."""
    from geo.regions import list_regions
    for r in list_regions():
        typer.echo(r)


if __name__ == "__main__":
    app()
