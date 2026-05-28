#!/usr/bin/env python
"""Allow running the CLI as a module: python -m lead_to_cash.services.knowledge_base.cli"""

from lead_to_cash.services.knowledge_base.cli.main import main

if __name__ == "__main__":
    exit(main())
