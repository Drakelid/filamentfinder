#!/usr/bin/env python3
"""Initialize the database with migrations."""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

os.chdir(backend_dir)

from alembic.config import Config
from alembic import command


def main():
    alembic_cfg = Config("alembic.ini")
    
    print("Running database migrations...")
    command.upgrade(alembic_cfg, "head")
    print("Database initialized successfully!")


if __name__ == "__main__":
    main()
