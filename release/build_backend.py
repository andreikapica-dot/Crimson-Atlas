"""Build a staged backend with the memory engine compiled as native extensions."""

from __future__ import annotations

import shutil
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Distribution, Extension
from setuptools.command.build_ext import build_ext


ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release"
STAGE = RELEASE / "backend-stage"
CYTHONIZED = RELEASE / "cythonized"
CYTHON_BUILD = RELEASE / "cython-build"
MEMORY_SOURCE = ROOT / "memory"
PYTHON_RUNTIME_MODULES = {"teleport.py"}


def reset_directory(target: Path) -> None:
    target = target.resolve()
    release_root = RELEASE.resolve()
    if target.parent != release_root:
        raise RuntimeError(f"Refusing to reset path outside release/: {target}")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)


def compile_memory_engine() -> None:
    sources = sorted(
        path for path in MEMORY_SOURCE.glob("*.py")
        if path.name != "__init__.py" and path.name not in PYTHON_RUNTIME_MODULES
    )
    extensions = [Extension(f"memory.{path.stem}", [str(path)]) for path in sources]
    compiled = cythonize(
        extensions,
        build_dir=str(CYTHON_BUILD),
        compiler_directives={
            "language_level": 3,
            "binding": False,
            "embedsignature": False,
        },
        quiet=True,
    )
    distribution = Distribution({"name": "crimson-atlas-memory", "ext_modules": compiled})
    command = build_ext(distribution)
    command.build_lib = str(CYTHONIZED)
    command.build_temp = str(CYTHON_BUILD / "temp")
    command.ensure_finalized()
    command.run()


def stage_backend() -> None:
    shutil.copytree(
        ROOT / "app",
        STAGE / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (STAGE / "memory").mkdir()
    shutil.copy2(MEMORY_SOURCE / "__init__.py", STAGE / "memory" / "__init__.py")
    compiled_modules = list((CYTHONIZED / "memory").glob("*.pyd"))
    expected_compiled = len(list(MEMORY_SOURCE.glob("*.py"))) - 1 - len(PYTHON_RUNTIME_MODULES)
    if len(compiled_modules) != expected_compiled:
        raise RuntimeError("Not all memory engine modules were compiled")
    for module in compiled_modules:
        shutil.copy2(module, STAGE / "memory" / module.name)
    for module_name in PYTHON_RUNTIME_MODULES:
        shutil.copy2(MEMORY_SOURCE / module_name, STAGE / "memory" / module_name)
    shutil.copy2(ROOT / "logging_config.py", STAGE / "logging_config.py")
    shutil.copy2(RELEASE / "service_entry.py", STAGE / "service_entry.py")


def main() -> None:
    reset_directory(STAGE)
    reset_directory(CYTHONIZED)
    reset_directory(CYTHON_BUILD)
    compile_memory_engine()
    stage_backend()
    print(f"Prepared protected backend stage at {STAGE}")


if __name__ == "__main__":
    main()
