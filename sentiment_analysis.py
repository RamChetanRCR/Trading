"""Legacy entry point kept for backwards compatibility.

Runs the original gold-news scan through the new package. Prefer:
    python -m newsscan query "gold price" "gold forecast" --name GOLD
"""

import sys

from newsscan.cli import main

if __name__ == "__main__":
    sys.exit(main(["query", "gold market", "gold price", "gold news", "gold forecast",
                   "gold investment", "--name", "GOLD", "--headlines", "10"]))
