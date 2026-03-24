#!/usr/bin/env python3
"""Add a new source to track."""

import argparse
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir.parent))

from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Add a source to FilamentFinder")
    parser.add_argument("url", help="URL to track")
    parser.add_argument("--name", "-n", help="Name for the source")
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages to crawl")
    parser.add_argument("--max-depth", type=int, default=3, help="Max crawl depth")
    
    args = parser.parse_args()
    
    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print("Error: Invalid URL format")
        sys.exit(1)
    
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    
    database_url = os.getenv("DATABASE_URL", "postgresql://filamentfinder:filamentfinder@localhost:5432/filamentfinder")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        from backend.app.models import Source
        
        source = Source(
            url=args.url,
            domain=domain,
            name=args.name or domain,
            crawl_rules_json={
                "max_pages": args.max_pages,
                "max_depth": args.max_depth,
                "same_domain_only": True,
            },
            status="pending",
        )
        session.add(source)
        session.commit()
        
        print(f"Source added successfully!")
        print(f"  ID: {source.id}")
        print(f"  URL: {source.url}")
        print(f"  Domain: {source.domain}")
        print(f"  Name: {source.name}")
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
