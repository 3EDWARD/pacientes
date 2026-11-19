"""Crea los pacientes ficticios del primer arranque."""

from __future__ import annotations

import random

from modelos.paciente import EDAD_MAXIMA, TIPOS_SANGRE, Paciente

NOMBRES_MASCULINOS = (
    "José", "Juan", "Luis", "Carlos", "Miguel", "Jorge", "Francisco", "Alejandro",
    "Ricardo", "Fernando", "Daniel", "Eduardo", "Javier", "Roberto", "Héctor",
    "Andrés", "Raúl", "Sergio", "Pedro", "Manuel", "Óscar", "Diego", "Iván",
    "Arturo", "Gabriel",
)
NOMBRES_FEMENINOS = (
    "María", "Guadalupe", "Ana", "Laura", "Patricia", "Sofía", "Fernanda",
    "Gabriela", "Verónica", "Lucía", "Rosa", "Carmen", "Daniela", "Elena",
    "Mariana", "Alejandra", "Paola", "Claudia", "Isabel", "Karla", "Teresa",
    "Leticia", "Natalia", "Valeria", "Irma",
)
APELLIDOS = (
    "García", "Hernández", "Martínez", "López", "González", "Pérez", "Rodríguez",
    "Sánchez", "Ramírez", "Cruz", "Flores", "Gómez", "Morales", "Vázquez",
    "Jiménez", "Reyes", "Díaz", "Torres", "Gutiérrez", "Ruiz", "Mendoza",
    "Aguilar", "Ortiz", "Castillo", "Moreno", "Romero", "Álvarez", "Chávez",
    "Rivera", "Juárez",
)
DIAGNOSTICOS = (
    "Hipertensión arterial", "Diabetes mellitus tipo 2", "Gripe estacional",
    "Asma bronquial", "Gastritis", "Migraña", "Fractura de tobillo",
    "Infección de vías urinarias", "Anemia", "Bronquitis aguda", "Neumonía",
    "Dermatitis atópica", "Lumbalgia", "Hipotiroidismo", "Apendicitis",
    "Rinitis alérgica", "Faringitis", "Gastroenteritis",
)
# Inicio del teléfono (lada).
LADAS = ("55", "56", "712", "722", "728", "777", "33", "81")

# Qué tan común es cada tipo de sangre, en el orden de TIPOS_SANGRE.
PESOS_SANGRE = (20, 3, 10, 2, 3, 1, 55, 6)


def _telefono(azar: random.Random) -> str:
    lada = azar.choice(LADAS)
    resto = "".join(str(azar.randint(0, 9)) for _ in range(10 - len(lada)))
    return lada + resto


def generar_pacientes_ficticios(
    cantidad: int = 50, semilla: int = 2025, con_antecedentes: int = 6
) -> list[Paciente]:
    """Crea los folios ficticios; algunos son de pacientes que ya tenían otro folio."""
    azar = random.Random(semilla)
    adicionales = min(con_antecedentes, max(0, cantidad - len(TIPOS_SANGRE)))
    cantidad_personas = cantidad - adicionales

    # Los primeros 8 son uno de cada tipo, así todos tienen datos.
    tipos = list(TIPOS_SANGRE)
    tipos += azar.choices(TIPOS_SANGRE, weights=PESOS_SANGRE, k=max(0, cantidad_personas - len(tipos)))
    tipos = tipos[:cantidad_personas]
    azar.shuffle(tipos)

    personas = []
    nombres_usados: set[str] = set()
    for numero in range(cantidad_personas):
        genero = azar.choice(("Masculino", "Femenino"))
        nombres = NOMBRES_MASCULINOS if genero == "Masculino" else NOMBRES_FEMENINOS
        while True:
            primer_apellido, segundo_apellido = azar.sample(APELLIDOS, 2)
            nombre = f"{azar.choice(nombres)} {primer_apellido} {segundo_apellido}"
            if nombre not in nombres_usados:
                nombres_usados.add(nombre)
                break
        personas.append(dict(
            nombre=nombre, genero=genero, telefono=_telefono(azar),
            tipo_sangre=tipos[numero], edad=azar.randint(1, 90),
        ))

    # Primer folio de cada persona: (índice de la persona, diagnóstico).
    registros = [(numero, azar.choice(DIAGNOSTICOS)) for numero in range(cantidad_personas)]

    # Folios nuevos de pacientes que ya existían, con otro diagnóstico.
    if adicionales:
        elegidos = azar.sample(range(cantidad_personas), adicionales - 1)
        # Uno de ellos llega a tener 3 folios.
        elegidos.append(elegidos[0])
        for persona in elegidos:
            previos = {dx for indice, dx in registros if indice == persona}
            diagnostico = azar.choice([d for d in DIAGNOSTICOS if d not in previos])
            primero = next(pos for pos, (indice, _) in enumerate(registros) if indice == persona)
            registros.insert(azar.randint(primero + 1, len(registros)), (persona, diagnostico))

    pacientes: list[Paciente] = []
    ultima_edad: dict[int, int] = {}
    for numero, (indice, diagnostico) in enumerate(registros, start=1):
        persona = personas[indice]
        # Es un folio posterior: la persona es un poco mayor.
        if indice in ultima_edad:
            edad = min(EDAD_MAXIMA, ultima_edad[indice] + azar.randint(0, 2))
        else:
            edad = persona["edad"]
        ultima_edad[indice] = edad
        pacientes.append(
            Paciente(
                folio=f"PAC-{numero:03d}",
                nombre=persona["nombre"],
                edad=edad,
                genero=persona["genero"],
                telefono=persona["telefono"],
                tipo_sangre=persona["tipo_sangre"],
                diagnostico=diagnostico,
            )
        )
    return pacientes
