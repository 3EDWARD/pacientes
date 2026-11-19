"""Abre el sistema de gestión de pacientes. Ejecutar con: python main.py"""

import sys
import tkinter as tk
from tkinter import messagebox

from logica.almacenamiento import Almacenamiento, AlmacenamientoError
from logica.gestor import GestorPacientes


def mostrar_error_inicial(mensaje: str) -> None:
    """Muestra un error en una ventana sencilla cuando el programa no puede abrir."""
    raiz = tk.Tk()
    raiz.withdraw()
    messagebox.showerror("No se pudo iniciar el sistema", mensaje)
    raiz.destroy()


def main() -> int:
    try:
        from interfaz.ventana import AplicacionGUI
    except ModuleNotFoundError as error:
        if error.name == "customtkinter":
            mostrar_error_inicial(
                "Falta instalar CustomTkinter.\n\n"
                "Abra la terminal en la carpeta del proyecto y ejecute:\n"
                "    pip install customtkinter"
            )
            return 1
        raise

    try:
        gestor = GestorPacientes(Almacenamiento())
    except AlmacenamientoError as error:
        mostrar_error_inicial(str(error))
        return 1

    AplicacionGUI(gestor).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
