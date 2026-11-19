"""Pruebas del tamaño de pantalla (zoom) guardado."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from logica.preferencias import (
    NIVELES_ZOOM,
    ZOOM_POR_DEFECTO,
    Preferencias,
    nivel_mas_cercano,
    nivel_siguiente,
)


class PruebasNiveles(unittest.TestCase):
    def test_los_niveles_son_de_100_a_200(self):
        self.assertEqual(NIVELES_ZOOM, (100, 125, 150, 175, 200))
        self.assertEqual(ZOOM_POR_DEFECTO, 100)

    def test_nivel_mas_cercano(self):
        self.assertEqual(nivel_mas_cercano(150), 150)
        self.assertEqual(nivel_mas_cercano(140), 150)
        self.assertEqual(nivel_mas_cercano(110), 100)
        self.assertEqual(nivel_mas_cercano(999), 200)
        self.assertEqual(nivel_mas_cercano(-5), 100)
        self.assertEqual(nivel_mas_cercano("175"), 175)

    def test_valores_que_no_sirven_vuelven_al_100(self):
        for malo in (None, "grande", "", [], {}, True, float("nan"), float("inf")):
            self.assertEqual(nivel_mas_cercano(malo), 100, msg=repr(malo))

    def test_nivel_siguiente_sube_y_baja_un_paso(self):
        self.assertEqual(nivel_siguiente(100, +1), 125)
        self.assertEqual(nivel_siguiente(125, +1), 150)
        self.assertEqual(nivel_siguiente(200, -1), 175)
        self.assertEqual(nivel_siguiente(125, -1), 100)

    def test_nivel_siguiente_se_queda_en_los_extremos(self):
        self.assertEqual(nivel_siguiente(200, +1), 200)
        self.assertEqual(nivel_siguiente(100, -1), 100)

    def test_nivel_siguiente_con_un_valor_intermedio(self):
        self.assertEqual(nivel_siguiente(140, +1), 175)


class PruebasPreferencias(unittest.TestCase):
    def setUp(self):
        self._carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self._carpeta.name) / "datos" / "preferencias.json"

    def tearDown(self):
        self._carpeta.cleanup()

    def test_sin_archivo_el_zoom_es_100(self):
        self.assertEqual(Preferencias(self.ruta).zoom, 100)

    def test_guarda_y_recupera_el_zoom(self):
        self.assertTrue(Preferencias(self.ruta).guardar_zoom(175))
        self.assertEqual(Preferencias(self.ruta).zoom, 175)

    def test_el_archivo_guardado_es_un_json_sencillo(self):
        Preferencias(self.ruta).guardar_zoom(150)
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8")), {"zoom": 150})
        self.assertFalse(self.ruta.with_suffix(".json.tmp").exists())

    def test_guardar_un_valor_raro_guarda_el_nivel_mas_cercano(self):
        preferencias = Preferencias(self.ruta)
        preferencias.guardar_zoom(140)
        self.assertEqual(preferencias.zoom, 150)
        self.assertEqual(Preferencias(self.ruta).zoom, 150)

    def test_archivo_danado_no_impide_abrir_el_sistema(self):
        self.ruta.parent.mkdir(parents=True)
        for contenido in ("{ esto no es json", "", "[1, 2, 3]", "null", '{"zoom": "enorme"}', '{"otra": 1}'):
            self.ruta.write_text(contenido, encoding="utf-8")
            self.assertEqual(Preferencias(self.ruta).zoom, 100, msg=contenido)

    def test_archivo_con_bom_de_windows(self):
        self.ruta.parent.mkdir(parents=True)
        self.ruta.write_text('{"zoom": 200}', encoding="utf-8-sig")
        self.assertEqual(Preferencias(self.ruta).zoom, 200)

    def test_si_no_se_puede_escribir_no_se_lanza_error(self):
        preferencias = Preferencias(self.ruta)
        with mock.patch("logica.preferencias.os.replace", side_effect=PermissionError("solo lectura")):
            self.assertFalse(preferencias.guardar_zoom(150))
        self.assertEqual(preferencias.zoom, 150)
        self.assertEqual(Preferencias(self.ruta).zoom, 100)

    def test_carpeta_imposible_de_crear(self):
        preferencias = Preferencias(self.ruta)
        with mock.patch.object(Path, "mkdir", side_effect=OSError("sin permiso")):
            self.assertFalse(preferencias.guardar_zoom(125))


if __name__ == "__main__":
    unittest.main()
