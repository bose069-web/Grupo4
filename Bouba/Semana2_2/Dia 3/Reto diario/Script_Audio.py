import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(Path(__file__).with_name("transcribir_audio.py"), run_name="__main__")