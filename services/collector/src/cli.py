"""CLI for the design collector pipeline."""

import asyncio
import logging
import os

import typer
from rich.console import Console
from rich.logging import RichHandler

from src.ingest_client import push_to_ingest
from src.scrapers.base import CollectedImage

app = typer.Typer(help="Design Collector - Automated high-quality design image collection")
console = Console()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


async def _ingest_results(results: list[CollectedImage], auto_ingest: bool) -> None:
    """Push collected images to the Ingest service."""
    if not auto_ingest or not results:
        return
    console.print(f"\n[bold]Pushing {len(results)} images to Ingest service...[/bold]")
    success = 0
    for item in results:
        try:
            await push_to_ingest(
                item.filepath,
                category=item.category,
                license_type=item.license_type,
                source_url=item.source_url,
                source_domain=item.source_domain,
            )
            success += 1
        except Exception as e:
            console.print(f"[red]Failed to ingest {item.filepath.name}: {e}[/red]")
    console.print(f"[green]Successfully ingested {success}/{len(results)} images[/green]")


@app.command()
def scrape(
    source: str = typer.Argument(
        ..., help="Source to scrape: dribbble, behance, pinterest, unsplash"
    ),
    query: str = typer.Option("web design", "--query", "-q", help="Search query"),
    auto_ingest: bool = typer.Option(False, "--ingest", "-i", help="Auto-push to Ingest service"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Scrape images from a gallery source."""
    setup_logging(verbose)

    scraper_map = _get_scraper_map(query)
    if source not in scraper_map:
        console.print(f"[red]Unknown source: {source}[/red]")
        console.print(f"Available: {', '.join(scraper_map.keys())}")
        raise typer.Exit(1)

    scraper = scraper_map[source]
    results = asyncio.run(scraper.run())
    console.print(f"\n[bold green]Collected {len(results)} images from {source}[/bold green]")

    if auto_ingest:
        asyncio.run(_ingest_results(results, auto_ingest))


@app.command()
def scrape_all(
    query: str = typer.Option("web design", "--query", "-q"),
    auto_ingest: bool = typer.Option(False, "--ingest", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Scrape from all available gallery sources."""
    setup_logging(verbose)
    scraper_map = _get_scraper_map(query)

    all_results: list[CollectedImage] = []
    for name, scraper in scraper_map.items():
        console.print(f"\n[bold]--- {name.upper()} ---[/bold]")
        try:
            results = asyncio.run(scraper.run())
            all_results.extend(results)
            console.print(f"[green]{name}: {len(results)} images[/green]")
        except Exception as e:
            console.print(f"[red]{name} failed: {e}[/red]")

    console.print(f"\n[bold green]Total collected: {len(all_results)} images[/bold green]")
    if auto_ingest:
        asyncio.run(_ingest_results(all_results, auto_ingest))


@app.command()
def hf_download(
    repo: str = typer.Argument(..., help="HuggingFace dataset repo (e.g. user/dataset)"),
    split: str = typer.Option("train", "--split", "-s"),
    category: str = typer.Option("design_reference", "--category", "-c"),
    max_samples: int = typer.Option(200, "--max", "-m"),
    auto_ingest: bool = typer.Option(False, "--ingest", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Download images from a HuggingFace dataset."""
    setup_logging(verbose)

    from src.datasets.hf_loader import load_hf_dataset

    results = asyncio.run(
        load_hf_dataset(repo, split=split, category=category, max_samples=max_samples)
    )
    console.print(f"\n[bold green]Downloaded {len(results)} images from {repo}[/bold green]")
    if auto_ingest:
        asyncio.run(_ingest_results(results, auto_ingest))


@app.command()
def hf_defaults(
    auto_ingest: bool = typer.Option(False, "--ingest", "-i"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Download from all pre-configured HuggingFace datasets."""
    setup_logging(verbose)

    from src.datasets.hf_loader import load_all_default_datasets

    results = asyncio.run(load_all_default_datasets())
    console.print(f"\n[bold green]Downloaded {len(results)} images from HF datasets[/bold green]")
    if auto_ingest:
        asyncio.run(_ingest_results(results, auto_ingest))


def _get_scraper_map(query: str) -> dict:
    from src.scrapers.behance import BehanceScraper
    from src.scrapers.dribbble import DribbbleScraper
    from src.scrapers.pinterest import PinterestScraper
    from src.scrapers.unsplash import UnsplashScraper

    return {
        "dribbble": DribbbleScraper(search_query=query),
        "behance": BehanceScraper(search_query=query),
        "pinterest": PinterestScraper(search_query=query),
        "unsplash": UnsplashScraper(
            search_query=query,
            access_key=os.environ.get("UNSPLASH_ACCESS_KEY", ""),
        ),
    }


if __name__ == "__main__":
    app()
