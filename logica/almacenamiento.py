"""Lee y guarda los pacientes en un archivo JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from logica.rutas import carpeta_de_datos
from modelos.paciente import Paciente, ValidacionError

# La carpeta depende de rutas.py.
RUTA_POR_DEFECTO = carpeta_de_datos() / "pacientes.json"


class AlmacenamientoError(Exception):
    """No se pudo leer o escribir el archivo."""


class Almacenamiento:
    def __init__(self, ruta: str | Path | None = None) -> None:
        self.ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO

    def existe(self) -> bool:
        return self.ruta.is_file()

    def cargar(self) -> list[Paciente]:
        try:
            with open(self.ruta, "r", encoding="utf-8-sig") as archivo:
                datos = json.load(archivo)
        except json.JSONDecodeError as error:
            raise AlmacenamientoError(
                f"El archivo de datos está dañado y no se puede leer:\n{self.ruta}\n\n"
                f"Detalle: {error}\n\n"
                "Haga una copia del archivo y bórrelo para que el sistema cree uno nuevo."
            ) from error
        except OSError as error:
            raise AlmacenamientoError(
                f"No se pudo leer el archivo de datos:\n{self.ruta}\n\nDetalle: {error}"
            ) from error

        if not isinstance(datos, list):
            raise AlmacenamientoError(
                f"El archivo de datos no tiene el formato esperado (una lista de pacientes):\n{self.ruta}"
            )

        pacientes: list[Paciente] = []
        folios: set[str] = set()
        for numero, registro in enumerate(datos, start=1):
            try:
                paciente = Paciente.from_dict(registro)
            except ValidacionError as error:
                raise AlmacenamientoError(
                    f"El registro número {numero} del archivo de datos no es válido: {error.mensaje}"
                ) from error
            if paciente.folio in folios:
                raise AlmacenamientoError(
                    f"El folio {paciente.folio} aparece repetido en el archivo de datos."
                )
            folios.add(paciente.folio)
            pacientes.append(paciente)
        return pacientes

    def guardar(self, pacientes: Iterable[Paciente]) -> None:
        datos = [paciente.a_dict() for paciente in pacientes]
        # Se escribe en un archivo temporal y luego reemplaza al original, para no dañarlo si falla.
        temporal = self.ruta.with_suffix(".json.tmp")
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(temporal, "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, ensure_ascii=False, indent=2)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(temporal, self.ruta)
        except OSError as error:
            raise AlmacenamientoError(
                f"No se pudo guardar la información en:\n{self.ruta}\n\nDetalle: {error}"
            ) from error
