"""Lógica del sistema: registrar, buscar, modificar, eliminar y reportes."""

from __future__ import annotations

import re
import statistics
from collections import Counter

from logica.almacenamiento import Almacenamiento, AlmacenamientoError
from logica.datos_ficticios import generar_pacientes_ficticios
from modelos.paciente import (
    TIPOS_SANGRE,
    Paciente,
    ValidacionError,
    normalizar_texto,
    partes_nombre,
    validar_edad,
    validar_folio,
    validar_tipo_sangre,
)

CANTIDAD_INICIAL = 50

ORDENES_SANGRE = ("tipo", "menor", "mayor")
CRITERIOS_NOMBRE = ("nombre", "apellido")


class FolioDuplicadoError(ValidacionError):
    """Se intentó registrar un folio que ya existe."""

    def __init__(self, folio: str) -> None:
        super().__init__(
            f"Ya existe un paciente con el folio {folio}. Escriba un folio diferente.",
            "folio",
        )
        self.folio = folio


class PacienteNoEncontradoError(Exception):
    def __init__(self, folio: str) -> None:
        super().__init__(f"No existe ningún paciente con el folio {folio}.")
        self.folio = folio


def _coincide(texto: str, consulta: str) -> bool:
    """True si todas las palabras de la consulta están en el texto."""
    palabras = normalizar_texto(consulta).split()
    base = normalizar_texto(texto)
    return bool(palabras) and all(palabra in base for palabra in palabras)


def clave_paciente(nombre: str) -> str:
    """Nombre normalizado; sirve para saber si dos folios son de la misma persona."""
    return " ".join(normalizar_texto(nombre).split())


def clave_apellido(nombre: str) -> tuple[str, str, str]:
    """Clave para ordenar por apellido paterno, materno y nombres."""
    nombres, paterno, materno = partes_nombre(nombre)
    return (
        normalizar_texto(paterno or nombres),
        normalizar_texto(materno),
        normalizar_texto(nombres),
    )


class GestorPacientes:
    """Guarda los pacientes en memoria (un diccionario por folio) y en el archivo."""
    def __init__(self, almacenamiento: Almacenamiento) -> None:
        self._almacenamiento = almacenamiento
        self._pacientes: dict[str, Paciente] = {}
        self._cargar()

    def _cargar(self) -> None:
        """Lee los pacientes del archivo; si no existe, crea los 50 ficticios."""
        if self._almacenamiento.existe():
            pacientes = self._almacenamiento.cargar()
        else:
            pacientes = generar_pacientes_ficticios(CANTIDAD_INICIAL)
            self._almacenamiento.guardar(pacientes)
        self._pacientes = {paciente.folio: paciente for paciente in pacientes}

    def guardar(self) -> None:
        self._almacenamiento.guardar(self._pacientes.values())

    def _confirmar_cambio(self, estado_anterior: dict[str, Paciente]) -> None:
        """Guarda en el archivo; si falla, regresa al estado anterior."""
        try:
            self.guardar()
        except AlmacenamientoError:
            self._pacientes = estado_anterior
            raise

    def registrar(self, paciente: Paciente) -> None:
        """Agrega un paciente nuevo (el folio no puede repetirse)."""
        if paciente.folio in self._pacientes:
            raise FolioDuplicadoError(paciente.folio)
        # Copia por si falla el guardado.
        anterior = dict(self._pacientes)
        self._pacientes[paciente.folio] = paciente
        self._confirmar_cambio(anterior)

    def modificar(
        self,
        folio: str,
        *,
        nombre: str,
        edad: object,
        genero: str,
        telefono: str,
        tipo_sangre: str,
        diagnostico: str,
    ) -> Paciente:
        """Cambia los datos de un paciente; el folio no cambia."""
        clave = validar_folio(folio)
        if clave not in self._pacientes:
            raise PacienteNoEncontradoError(clave)
        actualizado = Paciente(clave, nombre, edad, genero, telefono, tipo_sangre, diagnostico)
        anterior = dict(self._pacientes)
        self._pacientes[clave] = actualizado
        self._confirmar_cambio(anterior)
        return actualizado

    def eliminar(self, folio: str) -> Paciente:
        clave = str(folio).strip().upper()
        if clave not in self._pacientes:
            raise PacienteNoEncontradoError(clave)
        anterior = dict(self._pacientes)
        eliminado = self._pacientes.pop(clave)
        self._confirmar_cambio(anterior)
        return eliminado

    def total(self) -> int:
        return len(self._pacientes)

    def listar_todos(self) -> list[Paciente]:
        return list(self._pacientes.values())

    def buscar_por_folio(self, folio: str) -> Paciente | None:
        return self._pacientes.get(str(folio).strip().upper())

    def buscar_por_nombre(self, texto: str) -> list[Paciente]:
        """Coincidencia parcial, sin distinguir mayúsculas ni acentos."""
        return [p for p in self._pacientes.values() if _coincide(p.nombre, texto)]

    def buscar_por_telefono(self, texto: str) -> list[Paciente]:
        """Coincidencia parcial con los dígitos escritos."""
        digitos = re.sub(r"[\s().+-]", "", str(texto))
        if len(digitos) == 12 and digitos.startswith("52"):
            digitos = digitos[2:]
        if not re.fullmatch(r"[0-9]{1,10}", digitos):
            raise ValidacionError(
                "Para buscar por teléfono escriba solo números (hasta 10 dígitos).", "telefono"
            )
        return [p for p in self._pacientes.values() if digitos in p.telefono]

    def buscar_por_tipo_sangre(self, tipo: str) -> list[Paciente]:
        tipo = validar_tipo_sangre(tipo)
        return [p for p in self._pacientes.values() if p.tipo_sangre == tipo]

    def buscar_por_diagnostico(self, texto: str) -> list[Paciente]:
        return [p for p in self._pacientes.values() if _coincide(p.diagnostico, texto)]

    def mayores_de(self, edad: object) -> list[Paciente]:
        limite = validar_edad(edad, etiqueta="La edad indicada")
        return [p for p in self._pacientes.values() if p.edad > limite]

    def antecedentes_por_nombre(self, nombre: str) -> list[Paciente]:
        """Folios que ya tiene una persona con ese nombre."""
        clave = clave_paciente(nombre)
        if not clave:
            return []
        return [p for p in self._pacientes.values() if clave_paciente(p.nombre) == clave]

    def coincidencias_de_registro(self, paciente: Paciente) -> tuple[list[Paciente], list[Paciente]]:
        """Devuelve (folios con el mismo nombre, folios con el mismo teléfono y otro nombre)."""
        clave = clave_paciente(paciente.nombre)
        mismo_nombre = self.antecedentes_por_nombre(paciente.nombre)
        mismo_telefono = [
            p for p in self._pacientes.values()
            if p.telefono == paciente.telefono and clave_paciente(p.nombre) != clave
        ]
        return mismo_nombre, mismo_telefono

    def folios_relacionados(self) -> dict[str, list[str]]:
        """Para cada folio, la lista de todos los folios de su paciente."""
        grupos: dict[str, list[str]] = {}
        for paciente in self._pacientes.values():
            grupos.setdefault(clave_paciente(paciente.nombre), []).append(paciente.folio)
        return {p.folio: grupos[clave_paciente(p.nombre)] for p in self._pacientes.values()}

    def con_antecedentes(self, pacientes: list[Paciente]) -> list[Paciente]:
        """Agrega a la lista todos los folios de los pacientes que ya aparecen."""
        claves = {clave_paciente(p.nombre) for p in pacientes}
        orden = {folio: posicion for posicion, folio in enumerate(self._pacientes)}
        incluidos = [p for p in self._pacientes.values() if clave_paciente(p.nombre) in claves]
        return sorted(incluidos, key=lambda p: (clave_paciente(p.nombre), orden[p.folio]))

    def conteo_por_tipo_sangre(self) -> dict[str, int]:
        """Cantidad de pacientes por tipo de sangre (incluye los de 0)."""
        conteo = Counter(p.tipo_sangre for p in self._pacientes.values())
        return {tipo: conteo.get(tipo, 0) for tipo in TIPOS_SANGRE}

    def promedio_edad(self) -> float:
        if not self._pacientes:
            return 0.0
        return float(statistics.mean(p.edad for p in self._pacientes.values()))

    def reporte_tipo_sangre(self, tipo: str | None = None, orden: str = "tipo") -> list[tuple[str, int]]:
        """Filas (tipo, cantidad); si se da un tipo, solo esa fila."""
        if orden not in ORDENES_SANGRE:
            raise ValueError(f"Orden no válido: {orden!r}. Use uno de {ORDENES_SANGRE}.")
        conteo = self.conteo_por_tipo_sangre()
        if tipo is not None:
            tipo = validar_tipo_sangre(tipo)
            return [(tipo, conteo[tipo])]
        filas = list(conteo.items())
        if orden == "menor":
            filas.sort(key=lambda fila: fila[1])
        elif orden == "mayor":
            filas.sort(key=lambda fila: fila[1], reverse=True)
        return filas

    def ordenados_por_nombre(self, por: str = "nombre", descendente: bool = False) -> list[Paciente]:
        """Orden alfabético por nombre o por apellido."""
        if por not in CRITERIOS_NOMBRE:
            raise ValueError(f"Criterio no válido: {por!r}. Use uno de {CRITERIOS_NOMBRE}.")
        if por == "apellido":
            def clave(p: Paciente):
                return clave_apellido(p.nombre)
        else:
            def clave(p: Paciente):
                return normalizar_texto(p.nombre)
        # Primero por folio, para que los empates salgan siempre en el mismo orden.
        por_folio = sorted(self._pacientes.values(), key=lambda p: p.folio)
        return sorted(por_folio, key=clave, reverse=descendente)

    def edades_registradas(self) -> list[int]:
        return sorted({p.edad for p in self._pacientes.values()})

    def ordenados_por_edad(self, descendente: bool = False, edad: object = None) -> list[Paciente]:
        """Ordena por edad; si se da una edad, solo los de esa edad."""
        pacientes = list(self._pacientes.values())
        if edad is not None:
            exacta = validar_edad(edad, etiqueta="La edad indicada")
            pacientes = [p for p in pacientes if p.edad == exacta]
        # Los empates se ordenan por nombre.
        por_nombre = sorted(pacientes, key=lambda p: (normalizar_texto(p.nombre), p.folio))
        return sorted(por_nombre, key=lambda p: p.edad, reverse=descendente)

    def siguiente_folio(self) -> str:
        """Sugiere el siguiente folio libre (PAC-###)."""
        numeros = [
            int(coincidencia.group(1))
            for folio in self._pacientes
            if (coincidencia := re.fullmatch(r"PAC-(\d+)", folio))
        ]
        return f"PAC-{max(numeros, default=0) + 1:03d}"
