"""Entry point that runs app.py on EVERY Streamlit rerun.

(A plain `import app` only runs once per server process, so the page stopped updating after the
first click. runpy executes the file again each time.)
Start the app with:  python -m streamlit run AI_whiteboard.py   (or app.py)
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("app.py")), run_name="__main__")
