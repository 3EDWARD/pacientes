"""Pruebas de dónde se guardan los datos."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from logica import almacenamiento, preferencias, rutas


class PruebasCarpetaDeDatos(unittest.TestCase):
    def test_desde_el_codigo_usa_la_carpeta_datos_del_proyecto(self):
        esperada = Path(rutas.__file__).resolve().parent.parent / "datos"
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertFalse(rutas.esta_empaquetado())
            self.assertEqual(rutas.carpeta_de_datos(), esperada)

    def test_sin_el_atributo_frozen_no_esta_empaquetado(self):
        if hasattr(sys, "frozen"):
            self.skipTest("esta prueba corre dentro de un ejecutable")
        self.assertFalse(rutas.esta_empaquetado())

    def test_empaquetado_usa_localappdata(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.dict(os.environ, {"LOCALAPPDATA": carpeta}):
                self.assertTrue(rutas.esta_empaquetado())
                self.assertEqual(
                    rutas.carpeta_de_datos(),
                    Path(carpeta) / "SistemaPacientes" / "datos",
                )

    def test_empaquetado_sin_localappdata_usa_la_carpeta_personal(self):
        entorno = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.dict(os.environ, entorno, clear=True):
            self.assertEqual(
                rutas.carpeta_de_datos(),
                Path.home() / "SistemaPacientes" / "datos",
            )

    def test_los_dos_archivos_se_guardan_en_la_misma_carpeta(self):
        carpeta = rutas.carpeta_de_datos()
        self.assertEqual(almacenamiento.RUTA_POR_DEFECTO, carpeta / "pacientes.json")
        self.assertEqual(preferencias.RUTA_POR_DEFECTO, carpeta / "preferencias.json")


if __name__ == "__main__":
    unittest.main()
