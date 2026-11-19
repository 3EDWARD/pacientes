"""Dónde se guardan los archivos de datos."""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_APLICACION = "SistemaPacientes"


def esta_empaquetado() -> bool:
    """True si corre como programa instalado (PyInstaller) y no desde el código."""
    return bool(getattr(sys, "frozen", False))


def carpeta_de_datos() -> Path:
    """AppData si está instalado; si no, la carpeta datos junto a main.py."""
    if esta_empaquetado():
        base = os.environ.get("LOCALAPPDATA")
        raiz = Path(base) if base else Path.home()
        return raiz / NOMBRE_APLICACION / "datos"
    return Path(__file__).resolve().parent.parent / "datos"
