#!/usr/bin/env python3
"""Run a scan for a specific source or all sources."""

import argparse
import asyncio
import sys
from pathlib import Path

worker_dir = Path(__file__).parent.parent / "worker"
sys.path.insert(0, str(worker_dir.parent))

from worker.cli import scan_source, scan_all, list_sources, setup_logging


def main():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Run FilamentFinder scans")
    parser.add_argument("--source-id", "-s", type=int, help="Source ID to scan")
    parser.add_argument("--all", "-a", action="store_true", help="Scan all active sources")
    parser.add_argument("--list", "-l", action="store_true", help="List all sources")
    
    args = parser.parse_args()
    
    if args.list:
        list_sources()
    elif args.all:
        asyncio.run(scan_all())
    elif args.source_id:
        asyncio.run(scan_source(args.source_id))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
