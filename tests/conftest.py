import sys
from pathlib import Path

# the pipeline scripts import each other by bare name, so tests import them the same way
REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / 'pipeline'))
sys.path.insert(0, str(REPO_DIR))

FIXTURES = Path(__file__).parent / 'fixtures'
