"""Clase Paciente y validación de sus datos."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

TIPOS_SANGRE = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
GENEROS = ("Masculino", "Femenino", "Otro")
EDAD_MINIMA = 0
EDAD_MAXIMA = 120

# Cualquier letra, con o sin acento.
_LETRA = r"[^\W\d_]"
_PATRON_FOLIO = re.compile(r"[A-Z0-9][A-Z0-9_-]{0,14}")
_PATRON_NOMBRE = re.compile(rf"{_LETRA}(?:{_LETRA}| ){{2,79}}")

# Lo que se permite escribir en el formulario.
PATRON_ESCRITURA_NOMBRE = rf"(?:{_LETRA}| ){{0,80}}"
PATRON_ESCRITURA_EDAD = r"[0-9]{0,3}"
PATRON_ESCRITURA_TELEFONO = r"[0-9]{0,10}"


class ValidacionError(ValueError):
    """Error cuando un dato no cumple las reglas."""

    def __init__(self, mensaje: str, campo: str | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor)


def normalizar_texto(texto: str) -> str:
    """Pasa a minúsculas y quita acentos (para buscar y ordenar)."""
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return sin_acentos.casefold()


def validar_folio(valor: object) -> str:
    folio = _texto(valor).strip().upper()
    if not folio:
        raise ValidacionError("El folio es obligatorio.", "folio")
    if not _PATRON_FOLIO.fullmatch(folio):
        raise ValidacionError(
            "El folio solo puede tener letras, números, guion (-) o guion bajo (_), "
            "sin espacios, y un máximo de 15 caracteres.",
            "folio",
        )
    return folio


def formato_nombre(nombre: str) -> str:
    """Primera letra de cada palabra en mayúscula."""
    return " ".join(palabra.capitalize() for palabra in nombre.split())


# Palabras que se unen al apellido: "De la Cruz".
PARTICULAS_APELLIDO = frozenset({"de", "del", "la", "las", "los", "y"})


def partes_nombre(nombre: str) -> tuple[str, str, str]:
    """Separa el nombre en (nombres, apellido paterno, apellido materno)."""
    grupos: list[str] = []
    pendientes: list[str] = []
    for palabra in nombre.split():
        if normalizar_texto(palabra) in PARTICULAS_APELLIDO:
            pendientes.append(palabra)
        else:
            grupos.append(" ".join(pendientes + [palabra]))
            pendientes = []
    if pendientes:
        grupos.append(" ".join(pendientes))

    if len(grupos) >= 3:
        return " ".join(grupos[:-2]), grupos[-2], grupos[-1]
    if len(grupos) == 2:
        return grupos[0], grupos[1], ""
    return (grupos[0] if grupos else ""), "", ""


def validar_nombre(valor: object) -> str:
    nombre = " ".join(_texto(valor).split())
    if not nombre:
        raise ValidacionError("El nombre completo es obligatorio.", "nombre")
    if not _PATRON_NOMBRE.fullmatch(nombre):
        raise ValidacionError(
            "El nombre debe tener entre 3 y 80 caracteres y solo puede contener "
            "letras y espacios.",
            "nombre",
        )
    # Se guarda en mayúsculas.
    return nombre.upper()


def validar_edad(valor: object, etiqueta: str = "La edad", campo: str = "edad") -> int:
    if isinstance(valor, bool):
        raise ValidacionError(f"{etiqueta} debe ser un número entero.", campo)
    if isinstance(valor, int):
        edad = valor
    else:
        texto = _texto(valor).strip()
        if not texto:
            raise ValidacionError(f"{etiqueta} es obligatoria.", campo)
        if not re.fullmatch(r"[0-9]+", texto):
            raise ValidacionError(
                f"{etiqueta} debe ser un número entero entre {EDAD_MINIMA} y {EDAD_MAXIMA} "
                "(sin letras, signos ni decimales).",
                campo,
            )
        edad = int(texto)
    if not EDAD_MINIMA <= edad <= EDAD_MAXIMA:
        raise ValidacionError(
            f"{etiqueta} debe estar entre {EDAD_MINIMA} y {EDAD_MAXIMA} años.", campo
        )
    return edad


def validar_genero(valor: object) -> str:
    texto = _texto(valor).strip()
    for genero in GENEROS:
        if texto.casefold() == genero.casefold():
            return genero
    raise ValidacionError("Seleccione el género (Masculino, Femenino u Otro).", "genero")


def validar_telefono(valor: object) -> str:
    texto = _texto(valor).strip()
    if not texto:
        raise ValidacionError("El teléfono es obligatorio.", "telefono")
    # Se guarda solo con los 10 dígitos.
    digitos = re.sub(r"[\s().+-]", "", texto)
    # Quita la lada de México (+52).
    if len(digitos) == 12 and digitos.startswith("52"):
        digitos = digitos[2:]
    if not re.fullmatch(r"[0-9]{10}", digitos):
        raise ValidacionError(
            "El teléfono debe tener exactamente 10 dígitos, por ejemplo 7121020166.",
            "telefono",
        )
    return digitos


def validar_tipo_sangre(valor: object) -> str:
    texto = _texto(valor).strip().upper()
    if texto not in TIPOS_SANGRE:
        raise ValidacionError(
            "Seleccione un tipo de sangre válido (A+, A-, B+, B-, AB+, AB-, O+ u O-).",
            "tipo_sangre",
        )
    return texto


def validar_diagnostico(valor: object) -> str:
    diagnostico = " ".join(_texto(valor).split())
    if not diagnostico:
        raise ValidacionError("El diagnóstico es obligatorio.", "diagnostico")
    if len(diagnostico) > 120:
        raise ValidacionError("El diagnóstico no puede superar los 120 caracteres.", "diagnostico")
    return diagnostico


@dataclass
class Paciente:
    """Una persona atendida. El nombre se guarda en mayúsculas."""

    folio: str
    nombre: str
    edad: int
    genero: str
    telefono: str
    tipo_sangre: str
    diagnostico: str

    def __post_init__(self) -> None:
        """Valida cada campo al crear el paciente."""
        self.folio = validar_folio(self.folio)
        self.nombre = validar_nombre(self.nombre)
        self.edad = validar_edad(self.edad)
        self.genero = validar_genero(self.genero)
        self.telefono = validar_telefono(self.telefono)
        self.tipo_sangre = validar_tipo_sangre(self.tipo_sangre)
        self.diagnostico = validar_diagnostico(self.diagnostico)

    def a_dict(self) -> dict:
        """Diccionario para guardar en JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, datos: object) -> "Paciente":
        """Crea un paciente desde un diccionario del JSON."""
        if not isinstance(datos, dict):
            raise ValidacionError("El registro no tiene el formato esperado.")
        return cls(
            folio=datos.get("folio", ""),
            nombre=datos.get("nombre", ""),
            edad=datos.get("edad", ""),
            genero=datos.get("genero", ""),
            telefono=datos.get("telefono", ""),
            tipo_sangre=datos.get("tipo_sangre", ""),
            diagnostico=datos.get("diagnostico", ""),
        )

    @property
    def nombre_visible(self) -> str:
        return formato_nombre(self.nombre)

    def a_fila(self) -> tuple:
        """Valores en el orden de las columnas de la tabla."""
        return (
            self.folio,
            self.nombre_visible,
            self.edad,
            self.genero,
            self.telefono,
            self.tipo_sangre,
            self.diagnostico,
        )

    def __str__(self) -> str:
        return f"[{self.folio}] {self.nombre_visible}, {self.edad} años, sangre {self.tipo_sangre}"
