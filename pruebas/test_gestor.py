"""Pruebas del sistema. Ejecutar con: python -m unittest discover -s pruebas -t . -v"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from logica.almacenamiento import Almacenamiento, AlmacenamientoError
from logica.datos_ficticios import generar_pacientes_ficticios
from logica.gestor import FolioDuplicadoError, GestorPacientes, PacienteNoEncontradoError
import re

from modelos.paciente import (
    PATRON_ESCRITURA_EDAD,
    PATRON_ESCRITURA_NOMBRE,
    PATRON_ESCRITURA_TELEFONO,
    TIPOS_SANGRE,
    Paciente,
    ValidacionError,
    formato_nombre,
    partes_nombre,
)


def crear_paciente(folio="T-001", **cambios):
    """Paciente de prueba válido; se pueden cambiar campos."""
    datos = dict(
        folio=folio,
        nombre="Ana López Ruiz",
        edad=30,
        genero="Femenino",
        telefono="5512345678",
        tipo_sangre="O+",
        diagnostico="Gripe estacional",
    )
    datos.update(cambios)
    return Paciente(**datos)


class BasePruebas(unittest.TestCase):
    def setUp(self):
        self._carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self._carpeta.name) / "pacientes.json"

    def tearDown(self):
        self._carpeta.cleanup()

    def abrir_gestor(self):
        """Abre el sistema como al iniciar la aplicación."""
        return GestorPacientes(Almacenamiento(self.ruta))

    def gestor_vacio(self):
        """Gestor sin los 50 pacientes ficticios."""
        Almacenamiento(self.ruta).guardar([])
        return self.abrir_gestor()

    def gestor_con_muestra(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-001", nombre="Ana López Ruiz", edad=30,
                                        tipo_sangre="O+", diagnostico="Gripe estacional"))
        gestor.registrar(crear_paciente("T-002", nombre="Zoe Pérez Díaz", edad=65,
                                        tipo_sangre="A+", diagnostico="Hipertensión arterial"))
        gestor.registrar(crear_paciente("T-003", nombre="Álvaro Díaz Cruz", edad=8,
                                        tipo_sangre="O+", diagnostico="Asma bronquial"))
        gestor.registrar(crear_paciente("T-004", nombre="Beto Cruz Mora", edad=47,
                                        tipo_sangre="AB-", diagnostico="Gripe y rinitis"))
        return gestor


class PruebasValidacion(BasePruebas):
    def test_normaliza_los_datos_al_crear(self):
        p = crear_paciente(folio=" pac-7 ", nombre="  ana   lópez  ", telefono="55 1234-5678",
                           tipo_sangre="o+", genero="femenino")
        self.assertEqual(p.folio, "PAC-7")
        self.assertEqual(p.nombre, "ANA LÓPEZ")
        self.assertEqual(p.nombre_visible, "Ana López")
        self.assertEqual(p.telefono, "5512345678")
        self.assertEqual(p.tipo_sangre, "O+")
        self.assertEqual(p.genero, "Femenino")

    def test_campos_vacios_son_rechazados(self):
        for campo in ("folio", "nombre", "edad", "genero", "telefono", "tipo_sangre", "diagnostico"):
            with self.subTest(campo=campo):
                with self.assertRaises(ValidacionError) as ctx:
                    crear_paciente(**{campo: "   "})
                self.assertEqual(ctx.exception.campo, campo)

    def test_edad_invalida(self):
        for valor in ("abc", "-3", "121", "3.5", "", 200, -1):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidacionError):
                    crear_paciente(edad=valor)

    def test_edad_limites_validos(self):
        self.assertEqual(crear_paciente(edad="0").edad, 0)
        self.assertEqual(crear_paciente(edad="120").edad, 120)

    def test_telefono_invalido(self):
        for valor in ("123", "55123456789", "abcdefghij"):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidacionError):
                    crear_paciente(telefono=valor)

    def test_telefono_se_guarda_siempre_junto(self):
        for escrito in ("7121020166", "712 102 0166", "712-102-0166", "(712) 102 0166",
                        "+52 712 102 0166", "52 7121020166"):
            with self.subTest(escrito=escrito):
                self.assertEqual(crear_paciente(telefono=escrito).telefono, "7121020166")

    def test_telefono_se_muestra_junto_en_las_tablas(self):
        fila = crear_paciente(telefono="712 102 0166").a_fila()
        self.assertEqual(fila[4], "7121020166")

    def test_tipo_sangre_y_genero_invalidos(self):
        with self.assertRaises(ValidacionError):
            crear_paciente(tipo_sangre="C+")
        with self.assertRaises(ValidacionError):
            crear_paciente(genero="Robot")

    def test_nombre_y_folio_invalidos(self):
        with self.assertRaises(ValidacionError):
            crear_paciente(nombre="Juan123")
        with self.assertRaises(ValidacionError):
            crear_paciente(folio="PAC 001")

    def test_nombre_solo_acepta_letras_y_espacios(self):
        for valor in ("Ana-López", "O'Brien Pérez", "Dr. Ana López", "Ana López 2", "Ana_López"):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidacionError) as ctx:
                    crear_paciente(nombre=valor)
                self.assertEqual(ctx.exception.campo, "nombre")

    def test_nombre_acepta_mayusculas_minusculas_acentos_y_enie(self):
        for valor in ("ANA LÓPEZ", "ana lópez", "Ana LÓPEZ nuñez", "Zoë Müller Peña"):
            with self.subTest(valor=valor):
                self.assertEqual(crear_paciente(nombre=valor).nombre, valor.upper())

    def test_el_nombre_se_guarda_en_mayusculas_y_se_muestra_con_inicial_mayuscula(self):
        for escrito in ("jorge eduardo leandro cirilo", "JORGE EDUARDO LEANDRO CIRILO",
                        "jOrGe eDuArDo   lEaNdRo cIrIlO", "Jorge Eduardo Leandro Cirilo"):
            with self.subTest(escrito=escrito):
                p = crear_paciente(nombre=escrito)
                self.assertEqual(p.nombre, "JORGE EDUARDO LEANDRO CIRILO")
                self.assertEqual(p.nombre_visible, "Jorge Eduardo Leandro Cirilo")
                self.assertEqual(p.a_fila()[1], "Jorge Eduardo Leandro Cirilo")
                self.assertIn("Jorge Eduardo Leandro Cirilo", str(p))

    def test_formato_nombre_con_acentos_y_enie(self):
        self.assertEqual(formato_nombre("ÁLVARO NÚÑEZ PEÑA"), "Álvaro Núñez Peña")
        self.assertEqual(formato_nombre("MARÍA DEL CARMEN"), "María Del Carmen")
        self.assertEqual(formato_nombre("  ana   lópez "), "Ana López")

    def test_reglas_de_escritura_del_formulario(self):
        def permite(patron, texto):
            return re.fullmatch(patron, texto) is not None

        for texto in ("", "7", "35", "120"):
            self.assertTrue(permite(PATRON_ESCRITURA_EDAD, texto), texto)
        for texto in ("a", "3a", "-5", "3.5", "1200", " 5"):
            self.assertFalse(permite(PATRON_ESCRITURA_EDAD, texto), texto)
        for texto in ("", "7", "7121020166"):
            self.assertTrue(permite(PATRON_ESCRITURA_TELEFONO, texto), texto)
        for texto in ("71a", "712 102", "712-102", "+52", "71210201667"):
            self.assertFalse(permite(PATRON_ESCRITURA_TELEFONO, texto), texto)
        for texto in ("", "ana", "ANA López", "Zoë Peña ", "María del Carmen"):
            self.assertTrue(permite(PATRON_ESCRITURA_NOMBRE, texto), texto)
        for texto in ("Ana1", "Ana-López", "Ana.", "Ana_", "O'Brien"):
            self.assertFalse(permite(PATRON_ESCRITURA_NOMBRE, texto), texto)

    def test_ida_y_vuelta_a_diccionario(self):
        p = crear_paciente()
        self.assertEqual(Paciente.from_dict(p.a_dict()), p)


class PruebasRegistro(BasePruebas):
    def test_primer_arranque_crea_50_pacientes_ficticios(self):
        self.assertFalse(self.ruta.exists())
        gestor = self.abrir_gestor()
        self.assertEqual(gestor.total(), 50)
        self.assertTrue(self.ruta.exists())

    def test_registrar_varios_pacientes(self):
        gestor = self.gestor_vacio()
        for numero in range(1, 6):
            gestor.registrar(crear_paciente(f"R-{numero}"))
        self.assertEqual(gestor.total(), 5)

    def test_folio_duplicado_es_rechazado(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-001"))
        with self.assertRaises(FolioDuplicadoError):
            gestor.registrar(crear_paciente("T-001", nombre="Otra Persona"))
        self.assertEqual(gestor.total(), 1)
        self.assertEqual(gestor.buscar_por_folio("T-001").nombre_visible, "Ana López Ruiz")

    def test_folio_duplicado_sin_importar_mayusculas(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("ABC-1"))
        with self.assertRaises(FolioDuplicadoError):
            gestor.registrar(crear_paciente("abc-1"))

    def test_siguiente_folio_sugerido(self):
        gestor = self.abrir_gestor()
        self.assertEqual(gestor.siguiente_folio(), "PAC-051")
        gestor.registrar(crear_paciente(gestor.siguiente_folio()))
        self.assertEqual(gestor.siguiente_folio(), "PAC-052")

    def test_si_falla_el_guardado_se_revierte_el_cambio(self):
        gestor = self.gestor_vacio()
        with mock.patch.object(Almacenamiento, "guardar", side_effect=AlmacenamientoError("disco lleno")):
            with self.assertRaises(AlmacenamientoError):
                gestor.registrar(crear_paciente("T-001"))
        self.assertEqual(gestor.total(), 0)


class PruebasBusquedas(BasePruebas):
    def test_buscar_por_folio_existente(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual(gestor.buscar_por_folio("T-002").nombre_visible, "Zoe Pérez Díaz")
        self.assertEqual(gestor.buscar_por_folio(" t-002 ").folio, "T-002")

    def test_buscar_por_folio_inexistente_devuelve_none(self):
        self.assertIsNone(self.gestor_con_muestra().buscar_por_folio("NO-EXISTE"))

    def test_buscar_por_nombre_parcial_sin_acentos_ni_mayusculas(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual([p.folio for p in gestor.buscar_por_nombre("lopez")], ["T-001"])
        self.assertEqual([p.folio for p in gestor.buscar_por_nombre("ALVARO")], ["T-003"])
        self.assertEqual({p.folio for p in gestor.buscar_por_nombre("diaz")}, {"T-002", "T-003"})
        self.assertEqual([p.folio for p in gestor.buscar_por_nombre("perez zoe")], ["T-002"])

    def test_nombre_guardado_en_mayusculas_y_mostrado_con_inicial_mayuscula(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-010", nombre="MaRíA lópez RUIZ", diagnostico="GRIPE Estacional"))
        for consulta in ("maría lópez", "MARIA LOPEZ", "mArÍa lÓpEz", "RUIZ", "maría  lópez  ruiz"):
            with self.subTest(consulta=consulta):
                resultado = gestor.buscar_por_nombre(consulta)
                self.assertEqual([p.nombre for p in resultado], ["MARÍA LÓPEZ RUIZ"])
                self.assertEqual(resultado[0].nombre_visible, "María López Ruiz")
                self.assertEqual(resultado[0].a_fila()[1], "María López Ruiz")
        self.assertEqual(gestor.buscar_por_diagnostico("gripe")[0].diagnostico, "GRIPE Estacional")
        contenido = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(contenido[0]["nombre"], "MARÍA LÓPEZ RUIZ")
        self.assertEqual(self.abrir_gestor().buscar_por_folio("T-010").nombre_visible, "María López Ruiz")

    def test_un_archivo_con_nombres_en_minusculas_se_normaliza_al_cargar(self):
        registro = crear_paciente("V-001").a_dict()
        registro["nombre"] = "ana lópez ruiz"
        self.ruta.write_text(json.dumps([registro]), encoding="utf-8")
        paciente = self.abrir_gestor().buscar_por_folio("V-001")
        self.assertEqual(paciente.nombre, "ANA LÓPEZ RUIZ")
        self.assertEqual(paciente.nombre_visible, "Ana López Ruiz")

    def test_buscar_por_nombre_sin_resultados(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual(gestor.buscar_por_nombre("xyz"), [])
        self.assertEqual(gestor.buscar_por_nombre("   "), [])

    def test_buscar_por_tipo_de_sangre(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual({p.folio for p in gestor.buscar_por_tipo_sangre("O+")}, {"T-001", "T-003"})
        self.assertEqual(gestor.buscar_por_tipo_sangre("B-"), [])
        with self.assertRaises(ValidacionError):
            gestor.buscar_por_tipo_sangre("Z+")

    def test_buscar_por_diagnostico_parcial(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual({p.folio for p in gestor.buscar_por_diagnostico("gripe")}, {"T-001", "T-004"})
        self.assertEqual([p.folio for p in gestor.buscar_por_diagnostico("hipertension")], ["T-002"])
        self.assertEqual(gestor.buscar_por_diagnostico("cancer"), [])

    def test_mayores_de_es_estrictamente_mayor(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual({p.folio for p in gestor.mayores_de(30)}, {"T-002", "T-004"})
        self.assertEqual({p.folio for p in gestor.mayores_de("29")}, {"T-001", "T-002", "T-004"})
        self.assertEqual(gestor.mayores_de(100), [])

    def test_mayores_de_con_dato_invalido(self):
        gestor = self.gestor_con_muestra()
        for valor in ("abc", "", "-5"):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidacionError):
                    gestor.mayores_de(valor)

    def test_listar_todos(self):
        self.assertEqual(len(self.gestor_con_muestra().listar_todos()), 4)


class PruebasAntecedentes(BasePruebas):
    """Un paciente puede tener varios folios."""

    def gestor_con_historial(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("H-001", nombre="Ana López Ruiz", telefono="7121020166",
                                        diagnostico="Gripe estacional", edad=30))
        gestor.registrar(crear_paciente("H-002", nombre="Luis Pérez Gil", telefono="5511112222",
                                        diagnostico="Asma bronquial", edad=50))
        gestor.registrar(crear_paciente("H-003", nombre="ana  LÓPEZ ruiz", telefono="7121020166",
                                        diagnostico="Migraña", edad=31))
        gestor.registrar(crear_paciente("H-004", nombre="Ana López Ruiz", telefono="7229998888",
                                        diagnostico="Anemia", edad=31))
        return gestor

    def test_mismo_nombre_con_otro_folio_es_permitido(self):
        gestor = self.gestor_con_historial()
        self.assertEqual(gestor.total(), 4)
        self.assertEqual(gestor.buscar_por_folio("H-001").diagnostico, "Gripe estacional")
        self.assertEqual(gestor.buscar_por_folio("H-003").diagnostico, "Migraña")

    def test_el_folio_sigue_siendo_unico_aunque_sea_el_mismo_paciente(self):
        gestor = self.gestor_con_historial()
        with self.assertRaises(FolioDuplicadoError):
            gestor.registrar(crear_paciente("H-001", nombre="Ana López Ruiz"))
        self.assertEqual(gestor.total(), 4)

    def test_antecedentes_por_nombre_ignora_mayusculas_acentos_y_espacios(self):
        gestor = self.gestor_con_historial()
        for escrito in ("Ana López Ruiz", "ANA LOPEZ RUIZ", "  ana   lopez   ruiz "):
            with self.subTest(escrito=escrito):
                self.assertEqual([p.folio for p in gestor.antecedentes_por_nombre(escrito)],
                                 ["H-001", "H-003", "H-004"])

    def test_antecedentes_solo_con_el_nombre_completo(self):
        gestor = self.gestor_con_historial()
        self.assertEqual(gestor.antecedentes_por_nombre("Ana López"), [])
        self.assertEqual(gestor.antecedentes_por_nombre("Pedro Nuevo Gómez"), [])
        self.assertEqual(gestor.antecedentes_por_nombre("   "), [])

    def test_coincidencias_de_registro_por_nombre_y_por_telefono(self):
        gestor = self.gestor_con_historial()
        nuevo = crear_paciente("H-010", nombre="ANA lopez RUIZ", telefono="5500001111")
        por_nombre, por_telefono = gestor.coincidencias_de_registro(nuevo)
        self.assertEqual([p.folio for p in por_nombre], ["H-001", "H-003", "H-004"])
        self.assertEqual(por_telefono, [])
        familiar = crear_paciente("H-011", nombre="Pedro López Ruiz", telefono="7121020166")
        por_nombre, por_telefono = gestor.coincidencias_de_registro(familiar)
        self.assertEqual(por_nombre, [])
        self.assertEqual([p.folio for p in por_telefono], ["H-001", "H-003"])
        igual = crear_paciente("H-012", nombre="Ana López Ruiz", telefono="7121020166")
        por_nombre, por_telefono = gestor.coincidencias_de_registro(igual)
        self.assertEqual([p.folio for p in por_nombre], ["H-001", "H-003", "H-004"])
        self.assertEqual(por_telefono, [])
        nuevo = crear_paciente("H-013", nombre="Carla Nueva Mora", telefono="5599990000")
        self.assertEqual(gestor.coincidencias_de_registro(nuevo), ([], []))

    def test_dos_pacientes_con_el_mismo_telefono_no_comparten_folios(self):
        gestor = self.gestor_con_historial()
        gestor.registrar(crear_paciente("H-011", nombre="Pedro López Ruiz", telefono="7121020166"))
        relacionados = gestor.folios_relacionados()
        self.assertEqual(relacionados["H-011"], ["H-011"])
        self.assertEqual(relacionados["H-001"], ["H-001", "H-003", "H-004"])
        completos = gestor.con_antecedentes(gestor.buscar_por_telefono("7121020166"))
        self.assertEqual([p.folio for p in completos], ["H-001", "H-003", "H-004", "H-011"])

    def test_folios_relacionados(self):
        relacionados = self.gestor_con_historial().folios_relacionados()
        self.assertEqual(relacionados["H-001"], ["H-001", "H-003", "H-004"])
        self.assertEqual(relacionados["H-004"], ["H-001", "H-003", "H-004"])
        self.assertEqual(relacionados["H-002"], ["H-002"])

    def test_buscar_por_telefono_parcial_y_con_separadores(self):
        gestor = self.gestor_con_historial()
        self.assertEqual({p.folio for p in gestor.buscar_por_telefono("7121020166")}, {"H-001", "H-003"})
        self.assertEqual({p.folio for p in gestor.buscar_por_telefono("0166")}, {"H-001", "H-003"})
        self.assertEqual({p.folio for p in gestor.buscar_por_telefono("712-102")}, {"H-001", "H-003"})
        self.assertEqual({p.folio for p in gestor.buscar_por_telefono("+52 55 1111 2222")}, {"H-002"})
        self.assertEqual(gestor.buscar_por_telefono("0000"), [])

    def test_buscar_por_telefono_con_datos_invalidos(self):
        gestor = self.gestor_con_historial()
        for valor in ("abc", "", "71a2", "12345678901"):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidacionError):
                    gestor.buscar_por_telefono(valor)

    def test_con_antecedentes_agrega_todos_los_folios_del_paciente(self):
        gestor = self.gestor_con_historial()
        encontrados = gestor.buscar_por_telefono("7121020166")
        self.assertEqual({p.folio for p in encontrados}, {"H-001", "H-003"})
        completos = gestor.con_antecedentes(encontrados)
        self.assertEqual([p.folio for p in completos], ["H-001", "H-003", "H-004"])
        self.assertEqual([p.diagnostico for p in completos], ["Gripe estacional", "Migraña", "Anemia"])

    def test_con_antecedentes_agrupa_por_paciente(self):
        gestor = self.gestor_con_historial()
        folios = [p.folio for p in gestor.con_antecedentes(gestor.listar_todos())]
        self.assertEqual(folios, ["H-001", "H-003", "H-004", "H-002"])

    def test_con_antecedentes_de_lista_vacia(self):
        self.assertEqual(self.gestor_con_historial().con_antecedentes([]), [])

    def test_eliminar_un_folio_conserva_los_demas_del_paciente(self):
        gestor = self.gestor_con_historial()
        gestor.eliminar("H-003")
        self.assertEqual([p.folio for p in gestor.antecedentes_por_nombre("Ana López Ruiz")], ["H-001", "H-004"])
        self.assertEqual(gestor.folios_relacionados()["H-001"], ["H-001", "H-004"])

    def test_los_folios_acumulados_se_conservan_al_reiniciar(self):
        self.gestor_con_historial()
        reiniciado = self.abrir_gestor()
        self.assertEqual([p.folio for p in reiniciado.antecedentes_por_nombre("Ana López Ruiz")],
                         ["H-001", "H-003", "H-004"])

    def test_los_reportes_cuentan_cada_folio(self):
        gestor = self.gestor_con_historial()
        self.assertEqual(sum(gestor.conteo_por_tipo_sangre().values()), 4)


class PruebasReportes(BasePruebas):
    def test_conteo_por_tipo_de_sangre(self):
        conteo = self.gestor_con_muestra().conteo_por_tipo_sangre()
        self.assertEqual(list(conteo), list(TIPOS_SANGRE))
        self.assertEqual(conteo["O+"], 2)
        self.assertEqual(conteo["A+"], 1)
        self.assertEqual(conteo["AB-"], 1)
        self.assertEqual(conteo["B+"], 0)
        self.assertEqual(sum(conteo.values()), 4)

    def test_promedio_de_edad(self):
        # (30 + 65 + 8 + 47) / 4
        self.assertAlmostEqual(self.gestor_con_muestra().promedio_edad(), 37.5)

    def test_promedio_sin_pacientes_es_cero(self):
        self.assertEqual(self.gestor_vacio().promedio_edad(), 0.0)

    def test_orden_alfabetico_por_nombre(self):
        nombres = [p.nombre_visible for p in self.gestor_con_muestra().ordenados_por_nombre()]
        self.assertEqual(
            nombres, ["Álvaro Díaz Cruz", "Ana López Ruiz", "Beto Cruz Mora", "Zoe Pérez Díaz"]
        )

    def test_orden_por_edad_de_menor_a_mayor(self):
        edades = [p.edad for p in self.gestor_con_muestra().ordenados_por_edad()]
        self.assertEqual(edades, [8, 30, 47, 65])

    def test_los_reportes_usan_datos_actualizados(self):
        gestor = self.gestor_con_muestra()
        gestor.eliminar("T-002")
        self.assertEqual(sum(gestor.conteo_por_tipo_sangre().values()), 3)
        self.assertAlmostEqual(gestor.promedio_edad(), (30 + 8 + 47) / 3)
        self.assertEqual(len(gestor.ordenados_por_edad()), 3)
        gestor.registrar(crear_paciente("T-009", edad=90))
        self.assertEqual(gestor.ordenados_por_edad()[-1].edad, 90)


class PruebasPartesDelNombre(unittest.TestCase):
    def test_nombre_con_dos_apellidos(self):
        self.assertEqual(partes_nombre("JORGE EDUARDO LEANDRO CIRILO"),
                         ("JORGE EDUARDO", "LEANDRO", "CIRILO"))

    def test_tres_palabras_son_un_nombre_y_dos_apellidos(self):
        self.assertEqual(partes_nombre("ANA LÓPEZ RUIZ"), ("ANA", "LÓPEZ", "RUIZ"))

    def test_dos_palabras_solo_tienen_apellido_paterno(self):
        self.assertEqual(partes_nombre("ANA LÓPEZ"), ("ANA", "LÓPEZ", ""))

    def test_una_palabra_solo_tiene_nombre(self):
        self.assertEqual(partes_nombre("MADONNA"), ("MADONNA", "", ""))

    def test_las_particulas_se_unen_al_apellido(self):
        self.assertEqual(partes_nombre("JUAN PÉREZ DE LA CRUZ"), ("JUAN", "PÉREZ", "DE LA CRUZ"))
        self.assertEqual(partes_nombre("Luis del Valle Ruiz"), ("Luis", "del Valle", "Ruiz"))
        self.assertEqual(partes_nombre("MARÍA DE LOS ÁNGELES GARCÍA LÓPEZ"),
                         ("MARÍA DE LOS ÁNGELES", "GARCÍA", "LÓPEZ"))

    def test_particula_al_final_no_provoca_error(self):
        self.assertEqual(partes_nombre("ANA DE"), ("ANA", "DE", ""))

    def test_texto_vacio(self):
        self.assertEqual(partes_nombre("   "), ("", "", ""))


class PruebasOpcionesDeReportes(BasePruebas):
    """Reportes con selector: tipo de sangre, nombre o apellido y edad."""

    def test_sangre_todos_por_tipo(self):
        filas = self.gestor_con_muestra().reporte_tipo_sangre()
        self.assertEqual([tipo for tipo, _ in filas], list(TIPOS_SANGRE))
        self.assertEqual(dict(filas)["O+"], 2)

    def test_sangre_un_solo_tipo(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual(gestor.reporte_tipo_sangre("O+"), [("O+", 2)])
        self.assertEqual(gestor.reporte_tipo_sangre("o-"), [("O-", 0)])

    def test_sangre_un_tipo_ignora_el_orden(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual(gestor.reporte_tipo_sangre("A+", orden="mayor"), [("A+", 1)])

    def test_sangre_de_menor_a_mayor(self):
        filas = self.gestor_con_muestra().reporte_tipo_sangre(orden="menor")
        cantidades = [cantidad for _, cantidad in filas]
        self.assertEqual(cantidades, sorted(cantidades))
        self.assertEqual([t for t, _ in filas],
                         ["A-", "B+", "B-", "AB+", "O-", "A+", "AB-", "O+"])

    def test_sangre_de_mayor_a_menor(self):
        filas = self.gestor_con_muestra().reporte_tipo_sangre(orden="mayor")
        cantidades = [cantidad for _, cantidad in filas]
        self.assertEqual(cantidades, sorted(cantidades, reverse=True))
        self.assertEqual([t for t, _ in filas],
                         ["O+", "A+", "AB-", "A-", "B+", "B-", "AB+", "O-"])

    def test_sangre_siempre_incluye_los_ocho_tipos_y_suma_el_total(self):
        gestor = self.gestor_con_muestra()
        for orden in ("tipo", "menor", "mayor"):
            filas = gestor.reporte_tipo_sangre(orden=orden)
            self.assertEqual(len(filas), len(TIPOS_SANGRE))
            self.assertEqual(sum(c for _, c in filas), gestor.total())

    def test_sangre_rechaza_datos_no_validos(self):
        gestor = self.gestor_con_muestra()
        with self.assertRaises(ValidacionError):
            gestor.reporte_tipo_sangre("Z+")
        with self.assertRaises(ValueError):
            gestor.reporte_tipo_sangre(orden="al-azar")

    def test_nombre_de_la_a_a_la_z_y_de_la_z_a_la_a(self):
        gestor = self.gestor_con_muestra()
        subida = [p.nombre_visible for p in gestor.ordenados_por_nombre("nombre")]
        bajada = [p.nombre_visible for p in gestor.ordenados_por_nombre("nombre", descendente=True)]
        self.assertEqual(subida, ["Álvaro Díaz Cruz", "Ana López Ruiz", "Beto Cruz Mora", "Zoe Pérez Díaz"])
        self.assertEqual(bajada, subida[::-1])

    def test_apellido_de_la_a_a_la_z_y_de_la_z_a_la_a(self):
        gestor = self.gestor_con_muestra()
        subida = [p.nombre_visible for p in gestor.ordenados_por_nombre("apellido")]
        bajada = [p.nombre_visible for p in gestor.ordenados_por_nombre("apellido", descendente=True)]
        self.assertEqual(subida, ["Beto Cruz Mora", "Álvaro Díaz Cruz", "Ana López Ruiz", "Zoe Pérez Díaz"])
        self.assertEqual(bajada, subida[::-1])

    def test_apellido_desempata_por_materno_y_luego_por_nombre(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-001", nombre="Luis Soto Zamora"))
        gestor.registrar(crear_paciente("T-002", nombre="Carlos Soto Álvarez"))
        gestor.registrar(crear_paciente("T-003", nombre="Ana Soto Álvarez"))
        orden = [p.folio for p in gestor.ordenados_por_nombre("apellido")]
        self.assertEqual(orden, ["T-003", "T-002", "T-001"])

    def test_apellido_con_particula_se_ordena_como_se_escribe(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-001", nombre="Juan Pérez De La Cruz"))
        gestor.registrar(crear_paciente("T-002", nombre="Ana Cruz Mora"))
        gestor.registrar(crear_paciente("T-003", nombre="Luis De La Cruz Mora"))
        nombres = [p.nombre_visible for p in gestor.ordenados_por_nombre("apellido")]
        self.assertEqual(nombres, ["Ana Cruz Mora", "Luis De La Cruz Mora", "Juan Pérez De La Cruz"])

    def test_los_folios_de_un_mismo_paciente_siguen_en_orden_aunque_sea_descendente(self):
        gestor = self.gestor_vacio()
        for folio in ("T-001", "T-002", "T-003"):
            gestor.registrar(crear_paciente(folio, nombre="Ana López Ruiz"))
        gestor.registrar(crear_paciente("T-004", nombre="Zoe Pérez Díaz"))
        for por in ("nombre", "apellido"):
            folios = [p.folio for p in gestor.ordenados_por_nombre(por, descendente=True)]
            self.assertEqual(folios, ["T-004", "T-001", "T-002", "T-003"])

    def test_nombre_rechaza_un_criterio_desconocido(self):
        with self.assertRaises(ValueError):
            self.gestor_con_muestra().ordenados_por_nombre("telefono")

    def test_sin_argumentos_sigue_igual_que_antes(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual(gestor.ordenados_por_nombre(), gestor.ordenados_por_nombre("nombre", False))

    def test_edades_registradas_sin_repetir_y_ordenadas(self):
        gestor = self.gestor_con_muestra()
        gestor.registrar(crear_paciente("T-005", edad=30))
        self.assertEqual(gestor.edades_registradas(), [8, 30, 47, 65])
        self.assertEqual(self.gestor_vacio().edades_registradas(), [])

    def test_edad_de_menor_a_mayor_y_de_mayor_a_menor(self):
        gestor = self.gestor_con_muestra()
        self.assertEqual([p.edad for p in gestor.ordenados_por_edad()], [8, 30, 47, 65])
        self.assertEqual([p.edad for p in gestor.ordenados_por_edad(descendente=True)], [65, 47, 30, 8])

    def test_edad_exacta(self):
        gestor = self.gestor_con_muestra()
        gestor.registrar(crear_paciente("T-005", nombre="Bruno Cruz Mora", edad=30))
        resultado = gestor.ordenados_por_edad(edad=30)
        self.assertEqual([p.folio for p in resultado], ["T-001", "T-005"])
        self.assertEqual([p.folio for p in gestor.ordenados_por_edad(edad="30", descendente=True)],
                         ["T-001", "T-005"])

    def test_edad_exacta_sin_coincidencias(self):
        self.assertEqual(self.gestor_con_muestra().ordenados_por_edad(edad=31), [])

    def test_edad_exacta_cero_es_una_edad_valida(self):
        gestor = self.gestor_con_muestra()
        gestor.registrar(crear_paciente("T-005", nombre="Bebé Cruz Mora", edad=0))
        self.assertEqual([p.folio for p in gestor.ordenados_por_edad(edad=0)], ["T-005"])
        self.assertEqual(gestor.ordenados_por_edad()[0].folio, "T-005")

    def test_edad_exacta_rechaza_datos_no_validos(self):
        gestor = self.gestor_con_muestra()
        for malo in ("abc", -1, 121, True, ""):
            with self.assertRaises(ValidacionError):
                gestor.ordenados_por_edad(edad=malo)

    def test_empates_de_edad_quedan_por_nombre_en_ambos_sentidos(self):
        gestor = self.gestor_vacio()
        gestor.registrar(crear_paciente("T-001", nombre="Zoe Pérez Díaz", edad=40))
        gestor.registrar(crear_paciente("T-002", nombre="Ana López Ruiz", edad=40))
        gestor.registrar(crear_paciente("T-003", nombre="Beto Cruz Mora", edad=20))
        self.assertEqual([p.folio for p in gestor.ordenados_por_edad()], ["T-003", "T-002", "T-001"])
        self.assertEqual([p.folio for p in gestor.ordenados_por_edad(descendente=True)],
                         ["T-002", "T-001", "T-003"])

    def test_las_edades_registradas_se_actualizan_al_modificar_y_eliminar(self):
        gestor = self.gestor_con_muestra()
        gestor.eliminar("T-003")
        self.assertNotIn(8, gestor.edades_registradas())
        gestor.modificar("T-001", nombre="Ana López Ruiz", edad=31, genero="Femenino",
                         telefono="5512345678", tipo_sangre="O+", diagnostico="Gripe")
        self.assertEqual(gestor.edades_registradas(), [31, 47, 65])


class PruebasModificarYEliminar(BasePruebas):
    def test_modificar_conserva_el_folio_y_cambia_los_datos(self):
        gestor = self.gestor_con_muestra()
        actualizado = gestor.modificar(
            "T-001", nombre="Ana María López", edad=31, genero="Femenino",
            telefono="5599998888", tipo_sangre="B+", diagnostico="Bronquitis aguda",
        )
        self.assertEqual(actualizado.folio, "T-001")
        guardado = gestor.buscar_por_folio("T-001")
        self.assertEqual(guardado.nombre, "ANA MARÍA LÓPEZ")
        self.assertEqual(guardado.nombre_visible, "Ana María López")
        self.assertEqual(guardado.edad, 31)
        self.assertEqual(guardado.tipo_sangre, "B+")
        self.assertEqual(gestor.total(), 4)

    def test_modificar_con_datos_invalidos_no_cambia_nada(self):
        gestor = self.gestor_con_muestra()
        with self.assertRaises(ValidacionError):
            gestor.modificar("T-001", nombre="Ana", edad="abc", genero="Femenino",
                             telefono="5512345678", tipo_sangre="O+", diagnostico="X")
        self.assertEqual(gestor.buscar_por_folio("T-001").edad, 30)

    def test_modificar_folio_inexistente(self):
        with self.assertRaises(PacienteNoEncontradoError):
            self.gestor_con_muestra().modificar(
                "NO-EXISTE", nombre="Ana López", edad=20, genero="Femenino",
                telefono="5512345678", tipo_sangre="O+", diagnostico="X",
            )

    def test_eliminar_paciente(self):
        gestor = self.gestor_con_muestra()
        eliminado = gestor.eliminar("T-003")
        self.assertEqual(eliminado.folio, "T-003")
        self.assertIsNone(gestor.buscar_por_folio("T-003"))
        self.assertEqual(gestor.total(), 3)
        self.assertNotIn("T-003", [p.folio for p in gestor.buscar_por_tipo_sangre("O+")])

    def test_eliminar_folio_inexistente(self):
        with self.assertRaises(PacienteNoEncontradoError):
            self.gestor_con_muestra().eliminar("NO-EXISTE")


class PruebasPersistencia(BasePruebas):
    def test_los_registros_se_recuperan_al_reiniciar(self):
        gestor = self.abrir_gestor()
        gestor.registrar(crear_paciente("NUEVO-1"))
        reiniciado = self.abrir_gestor()
        self.assertEqual(reiniciado.total(), 51)
        self.assertIsNotNone(reiniciado.buscar_por_folio("NUEVO-1"))

    def test_las_modificaciones_se_conservan_al_reiniciar(self):
        gestor = self.abrir_gestor()
        gestor.modificar("PAC-001", nombre="Nombre Modificado", edad=77, genero="Otro",
                         telefono="5500000000", tipo_sangre="AB+", diagnostico="Diagnóstico nuevo")
        paciente = self.abrir_gestor().buscar_por_folio("PAC-001")
        self.assertEqual(paciente.nombre_visible, "Nombre Modificado")
        self.assertEqual(paciente.edad, 77)
        self.assertEqual(paciente.diagnostico, "Diagnóstico nuevo")

    def test_las_eliminaciones_se_conservan_al_reiniciar(self):
        gestor = self.abrir_gestor()
        gestor.eliminar("PAC-010")
        reiniciado = self.abrir_gestor()
        self.assertEqual(reiniciado.total(), 49)
        self.assertIsNone(reiniciado.buscar_por_folio("PAC-010"))

    def test_los_50_ficticios_no_se_regeneran_en_cada_arranque(self):
        gestor = self.abrir_gestor()
        gestor.eliminar("PAC-001")
        gestor.eliminar("PAC-002")
        self.assertEqual(self.abrir_gestor().total(), 48)

    def test_borrar_todos_no_vuelve_a_crear_los_ficticios(self):
        gestor = self.abrir_gestor()
        for paciente in gestor.listar_todos():
            gestor.eliminar(paciente.folio)
        self.assertEqual(self.abrir_gestor().total(), 0)

    def test_archivo_dañado_muestra_error_claro(self):
        self.ruta.write_text("esto no es json {{{", encoding="utf-8")
        with self.assertRaises(AlmacenamientoError):
            self.abrir_gestor()
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "esto no es json {{{")

    def test_archivo_con_folios_repetidos_es_rechazado(self):
        registro = crear_paciente("DUP-1").a_dict()
        self.ruta.write_text(json.dumps([registro, registro]), encoding="utf-8")
        with self.assertRaises(AlmacenamientoError):
            self.abrir_gestor()

    def test_el_json_conserva_acentos_legibles(self):
        self.abrir_gestor()
        contenido = self.ruta.read_text(encoding="utf-8")
        self.assertTrue(any(letra in contenido for letra in "áéíóúñ"))
        self.assertNotIn("\\u00", contenido)


class PruebasDatosFicticios(unittest.TestCase):
    def test_genera_50_registros_validos_con_folios_unicos(self):
        pacientes = generar_pacientes_ficticios(50)
        self.assertEqual(len(pacientes), 50)
        self.assertEqual(len({p.folio for p in pacientes}), 50)
        self.assertEqual([p.folio for p in pacientes][:3], ["PAC-001", "PAC-002", "PAC-003"])

    def test_algunos_pacientes_tienen_varios_folios_con_distinto_diagnostico(self):
        pacientes = generar_pacientes_ficticios(50)
        por_nombre = {}
        for p in pacientes:
            por_nombre.setdefault(p.nombre, []).append(p)
        self.assertEqual(len(por_nombre), 44)
        con_varios = [folios for folios in por_nombre.values() if len(folios) > 1]
        self.assertEqual(len(con_varios), 5)
        self.assertEqual(max(len(folios) for folios in por_nombre.values()), 3)
        for folios in con_varios:
            self.assertEqual(len({f.diagnostico for f in folios}), len(folios))
            self.assertEqual(len({f.telefono for f in folios}), 1)
            self.assertEqual(len({f.tipo_sangre for f in folios}), 1)
            self.assertEqual(len({f.genero for f in folios}), 1)
            edades = [f.edad for f in folios]
            self.assertEqual(edades, sorted(edades))

    def test_incluye_los_8_tipos_de_sangre(self):
        tipos = {p.tipo_sangre for p in generar_pacientes_ficticios(50)}
        self.assertEqual(tipos, set(TIPOS_SANGRE))

    def test_telefonos_son_de_10_digitos_juntos(self):
        for p in generar_pacientes_ficticios(50):
            self.assertRegex(p.telefono, r"[0-9]{10}")

    def test_es_repetible(self):
        self.assertEqual(generar_pacientes_ficticios(50), generar_pacientes_ficticios(50))

    def test_hay_pacientes_mayores_y_menores(self):
        edades = [p.edad for p in generar_pacientes_ficticios(50)]
        self.assertTrue(any(e > 60 for e in edades))
        self.assertTrue(any(e < 18 for e in edades))


if __name__ == "__main__":
    unittest.main()
