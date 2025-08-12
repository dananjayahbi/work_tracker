"""Application entrypoint for Work Tracker"""
import sys

# Defensive import to catch any early Qt issues
try:
    from work_tracker.ui.main_window import run
except Exception as import_err:
    print(f"Failed to initialize UI: {import_err}")
    sys.exit(1)

def main():
    try:
        return run()
    except Exception as e:
        # Catch unexpected errors instead of crashing (helps avoid silent segfault-like exits)
        print(f"Unhandled exception: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
