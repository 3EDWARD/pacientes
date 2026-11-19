"""Colores, fuente y botones que usa toda la interfaz."""

from __future__ import annotations

import customtkinter as ctk

FUENTE = "Segoe UI"
ACENTO = "#0f766e"
ACENTO_HOVER = "#115e59"
PELIGRO = "#b42318"
PELIGRO_HOVER = "#912018"
AVISO = "#b45309"
# Los pares son (modo claro, modo oscuro).
NEUTRO = ("#e5e7eb", "#3b4048")
NEUTRO_HOVER = ("#d1d5db", "#4b5260")
TEXTO_NEUTRO = ("#1f2937", "#e5e7eb")
TEXTO_SUAVE = ("#4b5563", "#9ca3af")
TEXTO_OK = ("#166534", "#6ee7a0")
TEXTO_ERROR = ("#b42318", "#ff9d94")
SUPERFICIE = ("#f1f5f5", "#262a2e")


def fuente(tamano: int = 13, negrita: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=FUENTE, size=tamano, weight="bold" if negrita else "normal")


def boton(master, texto: str, comando, tipo: str = "primario", **extra) -> ctk.CTkButton:
    colores = {
        "primario": dict(fg_color=ACENTO, hover_color=ACENTO_HOVER, text_color="white"),
        "peligro": dict(fg_color=PELIGRO, hover_color=PELIGRO_HOVER, text_color="white"),
        "neutro": dict(fg_color=NEUTRO, hover_color=NEUTRO_HOVER, text_color=TEXTO_NEUTRO),
    }[tipo]
    return ctk.CTkButton(
        master, text=texto, command=comando, height=36, corner_radius=8,
        font=fuente(13, True), **colores, **extra,
    )
