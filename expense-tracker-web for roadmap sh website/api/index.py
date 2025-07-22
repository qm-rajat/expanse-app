import sys
sys.path.append('.')
from expense_tracker.app import create_app

app = create_app()

# Vercel expects 'app' to be the entry point 