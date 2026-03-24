import argparse
import asyncio
import sys
import structlog

from worker.config import get_settings
from worker.database import get_db_session
from worker.models import Source
from worker.crawler.crawler import run_crawler

logger = structlog.get_logger(__name__)
settings = get_settings()


def setup_logging():
    """Setup logging for CLI."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def scan_source(source_id: int):
    """Run a scan for a specific source."""
    db = get_db_session()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            print(f"Error: Source {source_id} not found")
            sys.exit(1)
        
        print(f"Starting scan for source: {source.name} ({source.url})")
    finally:
        db.close()
    
    stats = await run_crawler(source_id)
    
    print("\nScan completed!")
    print(f"  Pages visited: {stats.pages_visited}")
    print(f"  Products found: {stats.products_found}")
    print(f"  Products updated: {stats.products_updated}")
    print(f"  Price changes: {stats.price_changes}")
    print(f"  Errors: {stats.errors}")


async def scan_all():
    """Run scans for all active sources."""
    db = get_db_session()
    try:
        sources = db.query(Source).filter(Source.active == True).all()
        if not sources:
            print("No active sources found")
            return
        
        print(f"Found {len(sources)} active sources")
        source_ids = [s.id for s in sources]
    finally:
        db.close()
    
    for source_id in source_ids:
        await scan_source(source_id)
        print()


def list_sources():
    """List all sources."""
    db = get_db_session()
    try:
        sources = db.query(Source).all()
        if not sources:
            print("No sources found")
            return
        
        print(f"{'ID':<5} {'Name':<30} {'Domain':<30} {'Active':<8} {'Status':<12} {'Last Scan'}")
        print("-" * 110)
        
        for source in sources:
            last_scan = source.last_scan_at.strftime("%Y-%m-%d %H:%M") if source.last_scan_at else "Never"
            print(f"{source.id:<5} {source.name[:28]:<30} {source.domain[:28]:<30} {str(source.active):<8} {source.status:<12} {last_scan}")
    finally:
        db.close()


def main():
    """Main CLI entry point."""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="FilamentFinder Worker CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    scan_parser = subparsers.add_parser("scan", help="Run a scan")
    scan_parser.add_argument("--source-id", "-s", type=int, help="Source ID to scan")
    scan_parser.add_argument("--all", "-a", action="store_true", help="Scan all active sources")
    
    list_parser = subparsers.add_parser("list", help="List sources")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        if args.all:
            asyncio.run(scan_all())
        elif args.source_id:
            asyncio.run(scan_source(args.source_id))
        else:
            print("Error: Specify --source-id or --all")
            sys.exit(1)
    
    elif args.command == "list":
        list_sources()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
