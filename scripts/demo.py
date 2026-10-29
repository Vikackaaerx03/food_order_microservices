import runpy
import os

runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo.py"), run_name="__main__")

