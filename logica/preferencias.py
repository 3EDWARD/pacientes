"""Guarda el tamaño de pantalla (zoom) que eligió la persona."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from logica.rutas import carpeta_de_datos

# Tamaños disponibles, en porcentaje.
NIVELES_ZOOM = (100, 125, 150, 175, 200)
ZOOM_POR_DEFECTO = 100

RUTA_POR_DEFECTO = carpeta_de_datos() / "preferencias.json"


def nivel_mas_cercano(valor: object) -> int:
    """Devuelve el nivel de zoom disponible más cercano (o 100 si no sirve)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ZOOM_POR_DEFECTO
    if isinstance(valor, bool) or not math.isfinite(numero):
        return ZOOM_POR_DEFECTO
    return min(NIVELES_ZOOM, key=lambda nivel: abs(nivel - numero))


def nivel_siguiente(nivel: object, direccion: int) -> int:
    """Nivel anterior (-1) o siguiente (+1); en los extremos se queda igual."""
    posicion = NIVELES_ZOOM.index(nivel_mas_cercano(nivel)) + (1 if direccion > 0 else -1)
    posicion = max(0, min(len(NIVELES_ZOOM) - 1, posicion))
    return NIVELES_ZOOM[posicion]


class Preferencias:
    def __init__(self, ruta: str | Path | None = None) -> None:
        self.ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
        self.zoom = self._leer_zoom()

    def _leer_zoom(self) -> int:
        try:
            with open(self.ruta, "r", encoding="utf-8-sig") as archivo:
                datos = json.load(archivo)
            return nivel_mas_cercano(datos.get("zoom"))
        except (OSError, ValueError, AttributeError):
            return ZOOM_POR_DEFECTO

    def guardar_zoom(self, zoom: object) -> bool:
        """Guarda el zoom; devuelve False si no se pudo escribir."""
        self.zoom = nivel_mas_cercano(zoom)
        temporal = self.ruta.with_suffix(".json.tmp")
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(temporal, "w", encoding="utf-8") as archivo:
                json.dump({"zoom": self.zoom}, archivo)
            os.replace(temporal, self.ruta)
            return True
        except OSError:
            return False
