"""CLI: `testing-autonomy generate --url X --journey "..."`."""
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

# Load .env from CWD so users don't have to export env vars manually
load_dotenv()


def _configure_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )


@click.group()
def main() -> None:
    """Testing Autonomy: AI agent that writes Playwright tests."""


@main.command()
@click.option("--url", required=True, help="Starting URL of the web app.")
@click.option(
    "--journey",
    required=True,
    help="Plain-English description of the user journey to test.",
)
@click.option(
    "--output",
    "output_dir",
    default="./output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write the generated test to.",
)
@click.option(
    "--max-steps",
    default=15,
    show_default=True,
    type=int,
    help="Max exploration steps before giving up.",
)
@click.option(
    "--headed",
    is_flag=True,
    help="Show the browser window (default: headless).",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging.")
def generate(
    url: str,
    journey: str,
    output_dir: Path,
    max_steps: int,
    headed: bool,
    verbose: bool,
) -> None:
    """Explore URL and generate a Playwright test for the given journey."""
    _configure_logging(verbose)

    # Import inside the function so `--help` works without API key set
    from testing_autonomy.agent import run_agent

    logger.info(f"Target: {url}")
    logger.info(f"Journey: {journey}")
    logger.info(f"Output: {output_dir.resolve()}")

    try:
        outcome = run_agent(
            url=url,
            journey=journey,
            output_dir=output_dir,
            max_exploration_steps=max_steps,
            headless=not headed,
        )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Agent crashed: {e}")
        sys.exit(2)

    # Summary
    click.echo("")
    click.echo("=" * 60)
    if outcome.success:
        click.secho("✓ SUCCESS", fg="green", bold=True)
    else:
        click.secho("✗ FAILED", fg="red", bold=True)
    click.echo(f"  Exploration steps: {outcome.exploration_steps}")
    click.echo(f"  Fix attempts:      {outcome.fix_attempts}")
    click.echo(f"  Summary:           {outcome.summary}")
    if outcome.test_path:
        click.echo(f"  Test file:         {outcome.test_path}")
    click.echo("=" * 60)

    sys.exit(0 if outcome.success else 1)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port.")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev mode).")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the web UI server."""
    try:
        import uvicorn
    except ImportError:
        click.secho(
            "uvicorn is not installed. Run: pip install 'uvicorn[standard]'",
            fg="red",
        )
        raise SystemExit(1)

    click.echo(f"Starting server at http://{host}:{port}")
    uvicorn.run(
        "testing_autonomy.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
