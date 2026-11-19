"""Cuadros de mensaje propios (avisos, errores y preguntas) que sí cambian con el zoom."""

from __future__ import annotations

import math
import tkinter
from tkinter import messagebox

import customtkinter as ctk

from interfaz.estilo import ACENTO, AVISO, PELIGRO, boton, fuente

# tipo -> (símbolo, color)
_TIPOS = {
    "info": ("i", ACENTO),
    "advertencia": ("!", AVISO),
    "error": ("×", PELIGRO),
    "pregunta": ("?", ACENTO),
}


class Dialogo(ctk.CTkToplevel):
    """Ventana con título, mensaje y uno o dos botones."""

    ANCHO_TEXTO = 520
    TAMANO_TEXTO = 15

    def __init__(self, padre, titulo: str, mensaje: str, tipo: str,
                 botones: list[tuple[str, object, str]], defecto: object, cancelar: object) -> None:
        super().__init__(padre)
        self.resultado: object = None
        self._defecto = defecto
        self._cancelar = cancelar
        self._cerrado = False
        self._intentos_foco = 0
        try:
            self._construir(padre, titulo, mensaje, tipo, botones)
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass
            raise

    def _escala(self) -> float:
        try:
            return max(0.5, float(self._get_widget_scaling()))
        except Exception:
            return 1.0

    def _alto_estimado(self, mensaje: str, ancho: int) -> int:
        caracteres_por_linea = max(1, int(ancho / (self.TAMANO_TEXTO * 0.56)))
        lineas = sum(max(1, math.ceil(len(parrafo) / caracteres_por_linea))
                     for parrafo in mensaje.split("\n"))
        return int(lineas * self.TAMANO_TEXTO * 1.55) + 16

    def _construir(self, padre, titulo, mensaje, tipo, botones) -> None:
        self.title(titulo)
        self.resizable(False, False)
        try:
            self.transient(padre)
        except Exception:
            pass

        # El cuadro no debe ser más grande que la pantalla.
        escala = self._escala()
        pantalla_ancho = self.winfo_screenwidth() / escala
        pantalla_alto = self.winfo_screenheight() / escala
        ancho_texto = max(280, min(self.ANCHO_TEXTO, int(pantalla_ancho * 0.7) - 140))
        alto_texto = max(40, min(self._alto_estimado(mensaje, ancho_texto), int(pantalla_alto * 0.5)))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=26, pady=(24, 8))

        simbolo, color = _TIPOS[tipo]
        ctk.CTkLabel(
            cuerpo, text=simbolo, width=48, height=48, corner_radius=24, fg_color=color,
            text_color="white", font=fuente(24, True),
        ).grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 20))
        ctk.CTkLabel(cuerpo, text=titulo, font=fuente(19, True), anchor="w", justify="left").grid(
            row=0, column=1, sticky="w", pady=(2, 8))

        texto = ctk.CTkTextbox(
            cuerpo, width=ancho_texto, height=alto_texto, wrap="word", fg_color="transparent",
            border_width=0, font=fuente(self.TAMANO_TEXTO), activate_scrollbars=True,
        )
        texto.grid(row=1, column=1, sticky="nsew")
        texto.insert("1.0", mensaje)
        texto.configure(state="disabled")

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=26, pady=(8, 22))
        # El primer botón queda a la izquierda.
        for etiqueta, valor, estilo in reversed(botones):
            boton(pie, etiqueta, lambda v=valor: self._elegir(v), estilo, width=120).pack(
                side="right", padx=(10, 0))

        self.protocol("WM_DELETE_WINDOW", lambda: self._elegir(self._cancelar))
        self.bind("<Return>", lambda _evento: self._elegir(self._defecto))
        self.bind("<Escape>", lambda _evento: self._elegir(self._cancelar))

        self.update_idletasks()
        self._centrar(padre)
        self.after(120, self._tomar_foco)

    def _centrar(self, padre) -> None:
        try:
            ancho, alto = self.winfo_reqwidth(), self.winfo_reqheight()
            x = padre.winfo_rootx() + (padre.winfo_width() - ancho) // 2
            y = padre.winfo_rooty() + (padre.winfo_height() - alto) // 3
            x = max(0, min(x, self.winfo_screenwidth() - ancho))
            y = max(0, min(y, self.winfo_screenheight() - alto - 40))
            tkinter.Wm.wm_geometry(self, f"{ancho}x{alto}+{x}+{y}")
        except Exception:
            pass

    def _tomar_foco(self) -> None:
        """Hace el cuadro modal (bloquea la ventana de atrás)."""
        if self._cerrado:
            return
        try:
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            self._intentos_foco += 1
            if self._intentos_foco < 5:
                self.after(150, self._tomar_foco)

    def _elegir(self, valor: object) -> None:
        if self._cerrado:
            return
        self._cerrado = True
        self.resultado = valor
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def esperar(self) -> object:
        self.wait_window(self)
        return self.resultado


def _nativo(tipo: str, titulo: str, mensaje: str, padre, pregunta: bool = False) -> object:
    """Si falla el cuadro propio, usa el de Windows."""
    if pregunta:
        return messagebox.askyesno(titulo, mensaje, parent=padre)
    funcion = {"info": messagebox.showinfo, "advertencia": messagebox.showwarning,
               "error": messagebox.showerror}[tipo]
    funcion(titulo, mensaje, parent=padre)
    return None


def _mostrar(padre, titulo, mensaje, tipo, botones, defecto, cancelar, pregunta: bool = False) -> object:
    if padre is None:
        return _nativo(tipo, titulo, mensaje, padre, pregunta)
    try:
        dialogo = Dialogo(padre, titulo, mensaje, tipo, botones, defecto, cancelar)
    except Exception:
        return _nativo(tipo, titulo, mensaje, padre, pregunta)
    return dialogo.esperar()


def informar(titulo: str, mensaje: str, parent=None) -> None:
    _mostrar(parent, titulo, mensaje, "info", [("Aceptar", None, "primario")], None, None)


def advertir(titulo: str, mensaje: str, parent=None) -> None:
    _mostrar(parent, titulo, mensaje, "advertencia", [("Aceptar", None, "primario")], None, None)


def error(titulo: str, mensaje: str, parent=None) -> None:
    _mostrar(parent, titulo, mensaje, "error", [("Aceptar", None, "primario")], None, None)


def preguntar(titulo: str, mensaje: str, parent=None, icon: str = "question") -> bool:
    """Pregunta Sí/No y devuelve True o False. Con icon="warning" el botón por defecto es No."""
    peligro = icon == "warning"
    botones = [("No", False, "neutro"), ("Sí", True, "peligro" if peligro else "primario")]
    resultado = _mostrar(
        parent, titulo, mensaje, "advertencia" if peligro else "pregunta",
        botones, False if peligro else True, False, pregunta=True,
    )
    return bool(resultado)
