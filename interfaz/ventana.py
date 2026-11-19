"""Interfaz gráfica: ventana principal y sus cuatro secciones."""

from __future__ import annotations

import re
import tkinter
from tkinter import ttk

import customtkinter as ctk

from interfaz import dialogos
from interfaz.estilo import (
    ACENTO,
    ACENTO_HOVER,
    FUENTE,
    NEUTRO,
    NEUTRO_HOVER,
    SUPERFICIE,
    TEXTO_ERROR,
    TEXTO_NEUTRO,
    TEXTO_OK,
    TEXTO_SUAVE,
    boton,
    fuente,
)
from logica.almacenamiento import AlmacenamientoError
from logica.gestor import (
    FolioDuplicadoError,
    GestorPacientes,
    PacienteNoEncontradoError,
    clave_paciente,
)
from logica.preferencias import Preferencias, nivel_mas_cercano, nivel_siguiente
from modelos.paciente import (
    GENEROS,
    PATRON_ESCRITURA_EDAD,
    PATRON_ESCRITURA_NOMBRE,
    PATRON_ESCRITURA_TELEFONO,
    TIPOS_SANGRE,
    Paciente,
    ValidacionError,
)

SELECCIONE = "Seleccione..."

# La tabla (ttk) no entiende los pares claro/oscuro, por eso tiene su propia paleta.
PALETAS = {
    "Light": {"fondo": "#ffffff", "texto": "#1f2937", "cabecera": "#e3ecec",
              "par": "#ffffff", "impar": "#f3f7f7", "seleccion": ACENTO},
    "Dark": {"fondo": "#2b2f33", "texto": "#e5e7eb", "cabecera": "#3b4248",
             "par": "#2b2f33", "impar": "#31363b", "seleccion": ACENTO},
}

# (id, título, ancho, alineación)
COLUMNAS_PACIENTE = (
    ("folio", "Folio", 78, "center"),
    ("nombre", "Nombre completo", 200, "w"),
    ("edad", "Edad", 50, "center"),
    ("genero", "Género", 90, "center"),
    ("telefono", "Teléfono", 105, "center"),
    ("sangre", "Sangre", 70, "center"),
    ("diagnostico", "Diagnóstico", 200, "w"),
)
# En Buscar se agrega la columna con todos los folios del paciente.
COLUMNAS_BUSQUEDA = COLUMNAS_PACIENTE + (("folios", "Folios del paciente", 190, "w"),)
COLUMNAS_SANGRE = (
    ("sangre", "Tipo de sangre", 160, "center"),
    ("cantidad", "Cantidad de folios", 200, "center"),
    ("porcentaje", "Porcentaje", 160, "center"),
)


def limitar_entrada(entrada: ctk.CTkEntry, patron: str) -> None:
    """Solo deja escribir en la caja texto que cumpla el patrón."""
    regla = re.compile(patron)
    try:
        ayuda = entrada.cget("placeholder_text") or ""
    except Exception:
        ayuda = ""

    def permitido(propuesto: str) -> bool:
        return propuesto == ayuda or regla.fullmatch(propuesto) is not None

    comando = (entrada.register(permitido), "%P")
    try:
        entrada.configure(validate="key", validatecommand=comando)
    except Exception:
        try:
            # Versiones de CustomTkinter que no reenvían validate.
            entrada._entry.configure(validate="key", validatecommand=comando)
        except Exception:
            pass


def _fraccion(posicion) -> float:
    try:
        return float(posicion[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def folios_texto(cantidad: int) -> str:
    return f"{cantidad} folio" if cantidad == 1 else f"{cantidad} folios"


def pacientes_texto(cantidad: int) -> str:
    return f"{cantidad} paciente" if cantidad == 1 else f"{cantidad} pacientes"


# Zoom con el que se dibujan las tablas.
_zoom_tablas = 1.0


def aplicar_estilo_tabla(zoom: float = 1.0) -> None:
    """Aspecto de las tablas según el modo claro/oscuro y el zoom."""
    global _zoom_tablas
    _zoom_tablas = zoom
    paleta = PALETAS.get(ctk.get_appearance_mode(), PALETAS["Light"])
    estilo = ttk.Style()
    # Aplicar el mismo tema otra vez haría parpadear todo.
    if estilo.theme_use() != "clam":
        estilo.theme_use("clam")
    try:
        escala = max(1.0, estilo.master.winfo_fpixels("1i") / 96)
    except Exception:
        escala = 1.0
    relleno = round(8 * zoom)
    estilo.layout("Pacientes.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    estilo.configure(
        "Pacientes.Treeview", background=paleta["fondo"], fieldbackground=paleta["fondo"],
        foreground=paleta["texto"], rowheight=round(30 * escala * zoom), borderwidth=0,
        font=(FUENTE, round(11 * zoom)),
    )
    estilo.configure(
        "Pacientes.Treeview.Heading", background=paleta["cabecera"], foreground=paleta["texto"],
        relief="flat", borderwidth=0, padding=(relleno, relleno),
        font=(FUENTE, round(11 * zoom), "bold"),
    )
    estilo.map(
        "Pacientes.Treeview",
        background=[("selected", paleta["seleccion"])],
        foreground=[("selected", "#ffffff")],
    )
    estilo.map("Pacientes.Treeview.Heading", background=[("active", paleta["cabecera"])])


class Encabezado(ctk.CTkFrame):
    """Título de la sección con una línea de explicación."""

    def __init__(self, master, titulo: str, subtitulo: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self._lbl_titulo = ctk.CTkLabel(self, text=titulo, font=fuente(26, True), anchor="w")
        self._lbl_titulo.pack(anchor="w")
        self._lbl_subtitulo = ctk.CTkLabel(
            self, text=subtitulo, font=fuente(13), text_color=TEXTO_SUAVE, anchor="w"
        )
        self._lbl_subtitulo.pack(anchor="w", pady=(2, 0))

    def cambiar(self, titulo: str, subtitulo: str) -> None:
        self._lbl_titulo.configure(text=titulo)
        self._lbl_subtitulo.configure(text=subtitulo)


class PanelTabla(ctk.CTkFrame):
    """Tabla con barra de desplazamiento; cada fila usa su folio como identificador."""

    _instancias: list["PanelTabla"] = []

    def __init__(self, master, columnas=COLUMNAS_PACIENTE, estirar=("nombre", "diagnostico")) -> None:
        super().__init__(master, fg_color="transparent")
        PanelTabla._instancias.append(self)
        self._columnas = columnas
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabla = ttk.Treeview(
            self, columns=[c[0] for c in columnas], show="headings",
            selectmode="browse", style="Pacientes.Treeview",
        )
        for id_columna, titulo, ancho, alineacion in columnas:
            self.tabla.heading(id_columna, text=titulo, anchor="center" if alineacion == "center" else "w")
            self.tabla.column(
                id_columna, width=ancho, minwidth=60, anchor=alineacion, stretch=id_columna in estirar
            )

        barra = ctk.CTkScrollbar(self, orientation="vertical", command=self.tabla.yview)
        # Barra horizontal: solo se ve cuando las columnas no caben.
        self.barra_h = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tabla.xview)
        self.tabla.configure(yscrollcommand=barra.set, xscrollcommand=self._desplazar_horizontal)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        self.barra_h.grid(row=1, column=0, sticky="ew")
        self.barra_h.grid_remove()
        self.actualizar_colores()
        self.escalar(_zoom_tablas)

    def _desplazar_horizontal(self, inicio, fin) -> None:
        self.barra_h.set(inicio, fin)
        if float(inicio) <= 0.0 and float(fin) >= 1.0:
            self.barra_h.grid_remove()
        else:
            self.barra_h.grid()

    def escalar(self, zoom: float) -> None:
        for id_columna, _titulo, ancho, _alineacion in self._columnas:
            self.tabla.column(
                id_columna, width=round(ancho * zoom), minwidth=max(60, round(ancho * zoom * 0.6))
            )

    def actualizar_colores(self) -> None:
        paleta = PALETAS.get(ctk.get_appearance_mode(), PALETAS["Light"])
        self.tabla.tag_configure("par", background=paleta["par"])
        self.tabla.tag_configure("impar", background=paleta["impar"])

    def limpiar(self) -> None:
        self.tabla.delete(*self.tabla.get_children())

    def mostrar(self, filas) -> None:
        """Muestra las filas: (identificador, valores)."""
        self.limpiar()
        for posicion, (identificador, valores) in enumerate(filas):
            etiqueta = "par" if posicion % 2 == 0 else "impar"
            self.tabla.insert("", "end", iid=identificador, values=valores, tags=(etiqueta,))

    def mostrar_pacientes(self, pacientes, folios_relacionados: dict[str, list[str]] | None = None) -> None:
        """Muestra pacientes; con folios_relacionados agrega la columna de folios."""
        def valores(paciente: Paciente) -> tuple:
            fila = paciente.a_fila()
            if folios_relacionados is not None:
                fila += (", ".join(folios_relacionados.get(paciente.folio, [paciente.folio])),)
            return fila

        self.mostrar((p.folio, valores(p)) for p in pacientes)

    def folio_seleccionado(self) -> str | None:
        seleccion = self.tabla.selection()
        return seleccion[0] if seleccion else None


class VistaBase(ctk.CTkFrame):
    """Base de las secciones de la ventana."""

    nombre = ""

    def __init__(self, app: "AplicacionGUI") -> None:
        super().__init__(app.contenedor, fg_color="transparent")
        self.app = app
        self.gestor: GestorPacientes = app.gestor

    def al_mostrar(self) -> None:
        """Se ejecuta cada vez que aparece la sección (aquí se recargan los datos)."""

    def al_cambiar_zoom(self) -> None:
        """Se ejecuta cuando cambia el tamaño de pantalla."""

    def _pedir_seleccion(self, tabla: PanelTabla) -> str | None:
        folio = tabla.folio_seleccionado()
        if folio is None:
            dialogos.advertir(
                "Seleccione un paciente",
                "Primero haga clic sobre un paciente de la tabla.",
                parent=self.app,
            )
        return folio

    def modificar_seleccionado(self, tabla: PanelTabla) -> None:
        folio = self._pedir_seleccion(tabla)
        if folio:
            self.app.editar_paciente(folio, origen=self.nombre)

    def eliminar_seleccionado(self, tabla: PanelTabla) -> None:
        folio = self._pedir_seleccion(tabla)
        if not folio:
            return
        paciente = self.gestor.buscar_por_folio(folio)
        if paciente is None:
            dialogos.error(
                "Paciente no encontrado",
                f"El paciente con folio {folio} ya no existe. Se actualizará la tabla.",
                parent=self.app,
            )
            self.app.datos_cambiaron()
            return

        otros = [a.folio for a in self.gestor.antecedentes_por_nombre(paciente.nombre) if a.folio != folio]
        aviso = (
            f"\n\nSolo se elimina este folio. Los demás folios del paciente se conservan: {', '.join(otros)}."
            if otros else ""
        )
        confirmado = dialogos.preguntar(
            "Confirmar eliminación",
            f"¿Desea eliminar el folio {paciente.folio} del paciente {paciente.nombre_visible}?{aviso}\n\n"
            "Esta acción no se puede deshacer.",
            icon="warning",
            parent=self.app,
        )
        if not confirmado:
            return

        try:
            self.gestor.eliminar(folio)
        except (PacienteNoEncontradoError, AlmacenamientoError) as error:
            dialogos.error("No se pudo eliminar", str(error), parent=self.app)
            self.app.datos_cambiaron()
            return
        dialogos.informar(
            "Paciente eliminado",
            f"El folio {paciente.folio} del paciente {paciente.nombre_visible} se eliminó correctamente.",
            parent=self.app,
        )
        self.app.datos_cambiaron()


class VistaPacientes(VistaBase):
    nombre = "pacientes"

    def __init__(self, app: "AplicacionGUI") -> None:
        super().__init__(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        Encabezado(
            self, "Pacientes registrados",
            "Seleccione un paciente de la tabla para modificarlo o eliminarlo.",
        ).grid(row=0, column=0, sticky="w")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", pady=(16, 10))
        boton(barra, "Modificar",
              lambda: self.modificar_seleccionado(self.tabla), "primario").pack(side="left")
        boton(barra, "Eliminar",
              lambda: self.eliminar_seleccionado(self.tabla), "peligro").pack(side="left", padx=10)
        boton(barra, "Actualizar", self.al_mostrar, "neutro").pack(side="left")
        self.lbl_total = ctk.CTkLabel(barra, text="", font=fuente(13), text_color=TEXTO_SUAVE)
        self.lbl_total.pack(side="right")

        self.tabla = PanelTabla(self)
        self.tabla.grid(row=2, column=0, sticky="nsew")

    def al_mostrar(self) -> None:
        pacientes = self.gestor.listar_todos()
        self.tabla.mostrar_pacientes(pacientes)
        if pacientes:
            self.lbl_total.configure(text=f"Mostrando {folios_texto(len(pacientes))}")
        else:
            self.lbl_total.configure(text="No hay pacientes registrados.")


class VistaFormulario(VistaBase):
    """Formulario para registrar y para modificar (al modificar, el folio queda bloqueado)."""

    nombre = "formulario"

    def __init__(self, app: "AplicacionGUI") -> None:
        super().__init__(app)
        # Modo del formulario: "registro" o "edicion".
        self.modo = "registro"
        # Sección a la que se vuelve al terminar de editar.
        self.origen = "pacientes"
        self.folio_edicion: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        # Con zoom alto el formulario no cabe: la zona se puede desplazar.
        zona = ctk.CTkScrollableFrame(self, fg_color="transparent")
        zona.grid(row=0, column=0, sticky="nsew")
        app.registrar_desplazable(zona)
        zona.grid_columnconfigure(0, weight=1)
        self.encabezado = Encabezado(zona, "", "")
        self.encabezado.grid(row=0, column=0, sticky="w")

        tarjeta = ctk.CTkFrame(zona, corner_radius=12, fg_color=SUPERFICIE)
        tarjeta.grid(row=1, column=0, sticky="new", pady=(16, 0))
        tarjeta.grid_columnconfigure((0, 1), weight=1, uniform="campos")

        altura = 38
        self.widgets = {
            "folio": ctk.CTkEntry(tarjeta, height=altura, placeholder_text="Ej. PAC-051"),
            "nombre": ctk.CTkEntry(tarjeta, height=altura, placeholder_text="Nombre y apellidos"),
            "edad": ctk.CTkEntry(tarjeta, height=altura, placeholder_text="De 0 a 120"),
            "genero": ctk.CTkComboBox(tarjeta, values=list(GENEROS), state="readonly", height=altura),
            "telefono": ctk.CTkEntry(tarjeta, height=altura, placeholder_text="10 dígitos, ej. 7121020166"),
            "tipo_sangre": ctk.CTkComboBox(tarjeta, values=list(TIPOS_SANGRE), state="readonly", height=altura),
            "diagnostico": ctk.CTkEntry(tarjeta, height=altura, placeholder_text="Diagnóstico del paciente"),
        }
        # Solo letras en el nombre y solo números en edad y teléfono.
        limitar_entrada(self.widgets["nombre"], PATRON_ESCRITURA_NOMBRE)
        limitar_entrada(self.widgets["edad"], PATRON_ESCRITURA_EDAD)
        limitar_entrada(self.widgets["telefono"], PATRON_ESCRITURA_TELEFONO)

        self.etiquetas: dict[str, ctk.CTkLabel] = {}

        def colocar(fila, columna, clave, texto, columnas=1):
            etiqueta = ctk.CTkLabel(tarjeta, text=texto, font=fuente(13, True), anchor="w")
            etiqueta.grid(row=fila * 2, column=columna, columnspan=columnas, sticky="w",
                          padx=22, pady=(18 if fila == 0 else 14, 4))
            self.widgets[clave].grid(row=fila * 2 + 1, column=columna, columnspan=columnas,
                                     sticky="ew", padx=22)
            self.etiquetas[clave] = etiqueta

        colocar(0, 0, "folio", "Folio *")
        colocar(0, 1, "nombre", "Nombre completo *")
        colocar(1, 0, "edad", "Edad *")
        colocar(1, 1, "genero", "Género *")
        colocar(2, 0, "telefono", "Teléfono *")
        colocar(2, 1, "tipo_sangre", "Tipo de sangre *")
        colocar(3, 0, "diagnostico", "Diagnóstico *", columnas=2)

        # Enter en el último campo equivale a pulsar el botón principal.
        self.widgets["diagnostico"].bind("<Return>", lambda _evento: self.guardar())

        acciones = ctk.CTkFrame(tarjeta, fg_color="transparent")
        acciones.grid(row=8, column=0, columnspan=2, sticky="w", padx=22, pady=(24, 22))
        self.btn_guardar = boton(acciones, "Registrar paciente", self.guardar, "primario", width=190)
        self.btn_guardar.pack(side="left")
        self.btn_restablecer = boton(acciones, "Limpiar formulario", self.restablecer, "neutro", width=170)
        self.btn_restablecer.pack(side="left", padx=10)
        boton(acciones, "Cancelar", self.cancelar, "neutro", width=110).pack(side="left")

    @staticmethod
    def _poner_texto(entrada: ctk.CTkEntry, texto: str) -> None:
        entrada.configure(state="normal")
        entrada.delete(0, "end")
        if texto:
            entrada.insert(0, texto)

    def _limpiar_campos(self) -> None:
        for clave, widget in self.widgets.items():
            if clave in ("genero", "tipo_sangre"):
                widget.set(SELECCIONE)
            else:
                self._poner_texto(widget, "")

    def _leer_campos(self) -> dict[str, str]:
        return {clave: widget.get().strip() for clave, widget in self.widgets.items()}

    def _enfocar(self, campo: str | None) -> None:
        widget = self.widgets.get(campo or "")
        if widget is not None:
            try:
                widget.focus()
            except Exception:
                pass

    def preparar_registro(self) -> None:
        self.modo = "registro"
        self.folio_edicion = None
        self.encabezado.cambiar(
            "Registrar paciente",
            "Complete todos los datos. Los campos con * son obligatorios y el folio no puede repetirse.",
        )
        self.etiquetas["folio"].configure(text="Folio *")
        self._limpiar_campos()
        self._poner_texto(self.widgets["folio"], self.gestor.siguiente_folio())
        self.btn_guardar.configure(text="Registrar paciente")
        self.btn_restablecer.configure(text="Limpiar formulario")

    def preparar_edicion(self, paciente: Paciente, origen: str) -> None:
        self.modo = "edicion"
        self.folio_edicion = paciente.folio
        self.origen = origen
        self.encabezado.cambiar(
            "Modificar paciente",
            "Cambie los datos que necesite. El folio identifica al paciente y no se puede modificar.",
        )
        self.etiquetas["folio"].configure(text="Folio (no se puede modificar)")
        self._poner_texto(self.widgets["folio"], paciente.folio)
        self.widgets["folio"].configure(state="disabled")
        self._poner_texto(self.widgets["nombre"], paciente.nombre_visible)
        self._poner_texto(self.widgets["edad"], str(paciente.edad))
        self.widgets["genero"].set(paciente.genero)
        self._poner_texto(self.widgets["telefono"], paciente.telefono)
        self.widgets["tipo_sangre"].set(paciente.tipo_sangre)
        self._poner_texto(self.widgets["diagnostico"], paciente.diagnostico)
        self.btn_guardar.configure(text="Guardar cambios")
        self.btn_restablecer.configure(text="Restablecer datos")

    def restablecer(self) -> None:
        if self.modo == "edicion" and self.folio_edicion:
            paciente = self.gestor.buscar_por_folio(self.folio_edicion)
            if paciente is not None:
                self.preparar_edicion(paciente, self.origen)
                return
        self.preparar_registro()

    def cancelar(self) -> None:
        destino = self.origen if self.modo == "edicion" else "pacientes"
        self.preparar_registro()
        self.app.mostrar_vista(destino)

    @staticmethod
    def _lineas_de_folios(registros: list[Paciente], con_nombre: bool) -> str:
        """Texto con los folios para el aviso (máximo los 8 más recientes)."""
        visibles = registros[-8:]
        lineas = []
        if len(registros) > len(visibles):
            lineas.append(f"   (y {len(registros) - len(visibles)} folio(s) anterior(es))")
        for r in visibles:
            detalle = f"{r.nombre_visible}  -  {r.diagnostico}" if con_nombre else r.diagnostico
            lineas.append(f"   •  {r.folio}  -  {detalle}")
        return "\n".join(lineas)

    def _confirmar_folio_nuevo(
        self, paciente: Paciente, mismo_nombre: list[Paciente], mismo_telefono: list[Paciente]
    ) -> bool:
        """Avisa que el nombre o el teléfono ya tienen folio y pregunta si se registra otro."""
        bloques = []
        if mismo_nombre:
            situacion = ("1 folio registrado" if len(mismo_nombre) == 1
                         else f"{len(mismo_nombre)} folios registrados")
            bloques.append(
                f"El paciente {paciente.nombre_visible} ya cuenta con {situacion}:\n\n"
                + self._lineas_de_folios(mismo_nombre, con_nombre=False)
            )
        if mismo_telefono:
            situacion = ("el folio de otro paciente" if len(mismo_telefono) == 1
                         else f"{len(mismo_telefono)} folios de otros pacientes")
            bloques.append(
                f"El teléfono {paciente.telefono} ya está registrado en {situacion}:\n\n"
                + self._lineas_de_folios(mismo_telefono, con_nombre=True)
            )
        titulo = "Paciente con antecedentes" if mismo_nombre else "Teléfono ya registrado"
        return dialogos.preguntar(
            titulo,
            "\n\n".join(bloques)
            + f"\n\n¿Desea confirmar el ingreso del folio nuevo {paciente.folio}?\n"
            "Cada folio conserva su propio diagnóstico; los anteriores no se modifican.",
            icon="question",
            parent=self.app,
        )

    def guardar(self) -> None:
        datos = self._leer_campos()
        antecedentes: list[Paciente] = []
        try:
            if self.modo == "registro":
                # Aquí se validan todos los campos.
                paciente = Paciente(**datos)
                if self.gestor.buscar_por_folio(paciente.folio) is not None:
                    raise FolioDuplicadoError(paciente.folio)
                antecedentes, mismo_telefono = self.gestor.coincidencias_de_registro(paciente)
                if (antecedentes or mismo_telefono) and not self._confirmar_folio_nuevo(
                    paciente, antecedentes, mismo_telefono
                ):
                    return
                self.gestor.registrar(paciente)
            else:
                # El folio no se puede cambiar.
                datos.pop("folio")
                paciente = self.gestor.modificar(self.folio_edicion, **datos)
        except FolioDuplicadoError as error:
            dialogos.error("Folio duplicado", error.mensaje, parent=self.app)
            self._enfocar("folio")
            return
        except ValidacionError as error:
            dialogos.error("Datos no válidos", error.mensaje, parent=self.app)
            self._enfocar(error.campo)
            return
        except (PacienteNoEncontradoError, AlmacenamientoError) as error:
            dialogos.error("No se pudo guardar", str(error), parent=self.app)
            return

        if self.modo == "registro":
            mensaje = f"El paciente {paciente.nombre_visible} se registró correctamente con el folio {paciente.folio}."
            if antecedentes:
                folios = [a.folio for a in antecedentes] + [paciente.folio]
                mensaje += f"\n\nAhora cuenta con {len(folios)} folios: {', '.join(folios)}."
            dialogos.informar("Registro exitoso", mensaje, parent=self.app)
            self.preparar_registro()
            self.app.datos_cambiaron()
        else:
            dialogos.informar(
                "Cambios guardados",
                f"Los datos del paciente {paciente.nombre_visible} (folio {paciente.folio}) "
                "se actualizaron correctamente.",
                parent=self.app,
            )
            destino = self.origen
            self.preparar_registro()
            self.app.mostrar_vista(destino)


class VistaBusqueda(VistaBase):
    nombre = "busqueda"

    CRITERIOS = ("Folio", "Nombre", "Teléfono", "Tipo de sangre", "Diagnóstico", "Edad mayor a")
    AYUDAS = {
        "Folio": "Ej. PAC-001",
        "Nombre": "Nombre o parte del nombre",
        "Teléfono": "Teléfono o parte del número (solo números)",
        "Diagnóstico": "Diagnóstico o parte de él",
        "Edad mayor a": "Edad en años (número entero)",
    }

    def __init__(self, app: "AplicacionGUI") -> None:
        super().__init__(app)
        # Última búsqueda: (criterio, valor).
        self._consulta: tuple[str, str] | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        Encabezado(
            self, "Buscar pacientes",
            "Elija el criterio, escriba el valor y pulse Buscar. La última columna muestra "
            "todos los folios del paciente.",
        ).grid(row=0, column=0, sticky="w")

        tarjeta = ctk.CTkFrame(self, corner_radius=12, fg_color=SUPERFICIE)
        tarjeta.grid(row=1, column=0, sticky="ew", pady=(16, 8))
        tarjeta.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(tarjeta, text="Buscar por", font=fuente(13, True)).grid(
            row=0, column=0, padx=(18, 8), pady=(16, 8))

        self.var_criterio = ctk.StringVar(value=self.CRITERIOS[0])
        ctk.CTkOptionMenu(
            tarjeta, values=list(self.CRITERIOS), variable=self.var_criterio,
            command=self._cambiar_criterio, width=170, height=38, dynamic_resizing=False,
            fg_color=ACENTO, button_color=ACENTO_HOVER, button_hover_color=ACENTO_HOVER,
        ).grid(row=0, column=1, padx=8, pady=(16, 8))

        self.ent_valor = ctk.CTkEntry(tarjeta, width=200, height=38, placeholder_text=self.AYUDAS["Folio"])
        self.ent_valor.grid(row=0, column=2, padx=(8, 18), pady=(16, 8), sticky="ew")
        self.ent_valor.bind("<Return>", lambda _evento: self.buscar())
        self.cmb_sangre = ctk.CTkComboBox(tarjeta, values=list(TIPOS_SANGRE), state="readonly",
                                          width=200, height=38)
        self.cmb_sangre.grid(row=0, column=2, padx=(8, 18), pady=(16, 8), sticky="ew")
        self.cmb_sangre.grid_remove()

        acciones = ctk.CTkFrame(tarjeta, fg_color="transparent")
        acciones.grid(row=1, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 16))
        boton(acciones, "Buscar", self.buscar, "primario", width=110).pack(side="left")
        boton(acciones, "Limpiar", self.limpiar, "neutro", width=100).pack(side="left", padx=(10, 0))

        self.lbl_estado = ctk.CTkLabel(self, text="", font=fuente(13), text_color=TEXTO_SUAVE, anchor="w")
        self.lbl_estado.grid(row=2, column=0, sticky="w", pady=(4, 6))

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        boton(barra, "Modificar",
              lambda: self.modificar_seleccionado(self.tabla), "primario").pack(side="left")
        boton(barra, "Eliminar",
              lambda: self.eliminar_seleccionado(self.tabla), "peligro").pack(side="left", padx=10)

        self.tabla = PanelTabla(self, columnas=COLUMNAS_BUSQUEDA, estirar=("nombre", "diagnostico", "folios"))
        self.tabla.grid(row=4, column=0, sticky="nsew")
        self._reiniciar_resultados()

    def _cambiar_criterio(self, criterio: str) -> None:
        if criterio == "Tipo de sangre":
            self.ent_valor.grid_remove()
            self.cmb_sangre.grid()
            self.cmb_sangre.set(TIPOS_SANGRE[0])
        else:
            self.cmb_sangre.grid_remove()
            self.ent_valor.grid()
            self.ent_valor.configure(placeholder_text=self.AYUDAS[criterio])
            self.ent_valor.delete(0, "end")
        self._consulta = None
        self._reiniciar_resultados()

    def limpiar(self) -> None:
        self.ent_valor.delete(0, "end")
        self._consulta = None
        self._reiniciar_resultados()

    def _reiniciar_resultados(self) -> None:
        self.tabla.limpiar()
        self.lbl_estado.configure(
            text="Elija un criterio, escriba el valor y pulse Buscar.", text_color=TEXTO_SUAVE
        )

    def buscar(self) -> None:
        criterio = self.var_criterio.get()
        if criterio == "Tipo de sangre":
            valor = self.cmb_sangre.get().strip()
        else:
            valor = self.ent_valor.get().strip()
            if not valor:
                dialogos.advertir(
                    "Dato requerido",
                    f"Escriba un valor para buscar por {criterio.lower()}.",
                    parent=self.app,
                )
                self.ent_valor.focus()
                return
        self._consulta = (criterio, valor)
        self._ejecutar(avisar=True)

    def _ejecutar(self, avisar: bool) -> None:
        """Repite la última búsqueda con los datos actuales."""
        criterio, valor = self._consulta
        try:
            if criterio == "Folio":
                encontrado = self.gestor.buscar_por_folio(valor)
                resultados = [encontrado] if encontrado else []
                descripcion = f"número {valor.upper()}"
            elif criterio == "Nombre":
                resultados = self.gestor.con_antecedentes(self.gestor.buscar_por_nombre(valor))
                descripcion = f"nombre que contiene «{valor}»"
            elif criterio == "Teléfono":
                resultados = self.gestor.con_antecedentes(self.gestor.buscar_por_telefono(valor))
                descripcion = f"teléfono que contiene «{valor}»"
            elif criterio == "Tipo de sangre":
                resultados = self.gestor.buscar_por_tipo_sangre(valor)
                descripcion = f"tipo de sangre {valor}"
            elif criterio == "Diagnóstico":
                resultados = self.gestor.buscar_por_diagnostico(valor)
                descripcion = f"diagnóstico que contiene «{valor}»"
            else:
                resultados = self.gestor.mayores_de(valor)
                descripcion = f"edad mayor a {int(valor)} años"
        except ValidacionError as error:
            self._consulta = None
            self._reiniciar_resultados()
            dialogos.error("Dato no válido", error.mensaje, parent=self.app)
            return

        self.tabla.mostrar_pacientes(resultados, self.gestor.folios_relacionados())
        if resultados:
            verbo = "encontró" if len(resultados) == 1 else "encontraron"
            texto = f"Se {verbo} {folios_texto(len(resultados))}"
            if criterio in ("Nombre", "Teléfono"):
                pacientes = len({clave_paciente(p.nombre) for p in resultados})
                texto += f" de {pacientes_texto(pacientes)}"
                if len(resultados) > pacientes:
                    texto += " (los folios de un mismo paciente aparecen juntos)"
            self.lbl_estado.configure(text=f"{texto} con {descripcion}.", text_color=TEXTO_OK)
            return

        if criterio == "Folio":
            mensaje = f"El folio {valor.upper()} no existe en el sistema."
        else:
            mensaje = f"No se encontraron pacientes con {descripcion}."
        self.lbl_estado.configure(text=mensaje, text_color=TEXTO_ERROR)
        if avisar:
            dialogos.informar("Sin resultados", mensaje, parent=self.app)

    def al_mostrar(self) -> None:
        """Repite la búsqueda para no mostrar datos desactualizados."""
        if self._consulta is not None:
            self._ejecutar(avisar=False)
        else:
            self._reiniciar_resultados()


class BarraOpciones(ctk.CTkFrame):
    """Fila de listas desplegables de un reporte."""

    def __init__(self, master) -> None:
        super().__init__(master, fg_color="transparent")
        self._grupos: list[ctk.CTkFrame] = []
        self._vertical = False

    def agregar(self, titulo: str, valores: list[str], comando, ancho: int = 230) -> ctk.CTkOptionMenu:
        grupo = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(grupo, text=titulo, font=fuente(12, True), text_color=TEXTO_SUAVE, anchor="w").pack(
            anchor="w")
        menu = ctk.CTkOptionMenu(
            grupo, values=list(valores), command=comando, width=ancho, height=36,
            dynamic_resizing=False, font=fuente(13), dropdown_font=fuente(13),
            fg_color=NEUTRO, button_color=NEUTRO_HOVER, button_hover_color=NEUTRO_HOVER,
            text_color=TEXTO_NEUTRO,
        )
        menu.set(valores[0])
        menu.pack(anchor="w", pady=(2, 0))
        self._grupos.append(grupo)
        self._colocar()
        return menu

    def acomodar(self, vertical: bool) -> None:
        if vertical != self._vertical:
            self._vertical = vertical
            self._colocar()

    def _colocar(self) -> None:
        for posicion, grupo in enumerate(self._grupos):
            if self._vertical:
                grupo.grid(row=posicion, column=0, sticky="w", pady=(0, 8))
            else:
                grupo.grid(row=0, column=posicion, sticky="w", padx=(0, 20))


def anios_texto(edad: int | str) -> str:
    return f"{edad} año" if str(edad) == "1" else f"{edad} años"


class VistaReportes(VistaBase):
    nombre = "reportes"

    REPORTES = (
        ("sangre", "Pacientes por tipo de sangre"),
        ("promedio", "Promedio de edad"),
        ("listado", "Listado completo"),
        ("nombre", "Orden alfabético por nombre"),
        ("edad", "Orden por edad"),
    )

    TODOS = "Todos"
    TODAS = "Todas"
    CRITERIO_NOMBRE = {"Nombre": "nombre", "Apellido": "apellido"}
    SENTIDO_NOMBRE = {"De A a Z": False, "De Z a A": True}
    SENTIDO_EDAD = {"De menor a mayor": False, "De mayor a menor": True}
    # Desde este zoom las listas se acomodan una debajo de otra.
    ZOOM_PARA_APILAR = 1.5

    def __init__(self, app: "AplicacionGUI") -> None:
        super().__init__(app)
        # Reporte abierto: (clave, edad).
        self._reporte: tuple[str, str | None] | None = None
        self.botones: dict[str, ctk.CTkButton] = {}
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        Encabezado(
            self, "Reportes y estadísticas",
            "Cada reporte se calcula con la información actual del sistema.",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        izquierda = ctk.CTkScrollableFrame(self, width=282, corner_radius=12, fg_color=SUPERFICIE)
        izquierda.grid(row=1, column=0, sticky="ns", padx=(0, 18), pady=(16, 0))
        app.registrar_desplazable(izquierda)
        ctk.CTkLabel(izquierda, text="Elija un reporte", font=fuente(14, True), anchor="w").pack(
            anchor="w", padx=16, pady=(16, 8))
        for clave, texto in self.REPORTES:
            boton_reporte = boton(
                izquierda, texto, lambda c=clave: self._pedir_reporte(c), "neutro",
                width=250, anchor="w",
            )
            boton_reporte.pack(padx=16, pady=4)
            self.botones[clave] = boton_reporte

        ctk.CTkLabel(izquierda, text="Pacientes mayores de (años)", font=fuente(13, True), anchor="w").pack(
            anchor="w", padx=16, pady=(18, 6))
        fila = ctk.CTkFrame(izquierda, fg_color="transparent")
        fila.pack(anchor="w", padx=16, pady=(0, 16))
        self.ent_edad = ctk.CTkEntry(fila, width=100, height=36, placeholder_text="Ej. 60")
        self.ent_edad.pack(side="left")
        self.ent_edad.bind("<Return>", lambda _evento: self._pedir_reporte("mayores"))
        self.botones["mayores"] = boton(
            fila, "Consultar", lambda: self._pedir_reporte("mayores"), "neutro", width=140)
        self.botones["mayores"].pack(side="left", padx=(10, 0))

        derecha = ctk.CTkFrame(self, fg_color="transparent")
        derecha.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        derecha.grid_columnconfigure(0, weight=1)
        derecha.grid_rowconfigure(3, weight=1)

        self.lbl_titulo = ctk.CTkLabel(derecha, text="", font=fuente(20, True), anchor="w")
        self.lbl_titulo.grid(row=0, column=0, sticky="w")
        self.lbl_resumen = ctk.CTkLabel(derecha, text="", font=fuente(13), text_color=TEXTO_SUAVE, anchor="w")
        self.lbl_resumen.grid(row=1, column=0, sticky="w", pady=(2, 10))

        # Listas desplegables de cada reporte (solo se ven las del reporte abierto).
        self.opciones: dict[str, BarraOpciones] = {}

        barra = BarraOpciones(derecha)
        self.menu_sangre_tipo = barra.agregar(
            "Tipo de sangre", [self.TODOS, *TIPOS_SANGRE], self._opcion_cambiada)
        self.opciones["sangre"] = barra

        barra = BarraOpciones(derecha)
        self.menu_nombre_por = barra.agregar(
            "Ordenar por", list(self.CRITERIO_NOMBRE), self._opcion_cambiada)
        self.menu_nombre_sentido = barra.agregar(
            "Sentido", list(self.SENTIDO_NOMBRE), self._opcion_cambiada)
        self.opciones["nombre"] = barra

        barra = BarraOpciones(derecha)
        self.menu_edad = barra.agregar("Edad (años)", [self.TODAS], self._opcion_cambiada)
        self.menu_edad_sentido = barra.agregar(
            "Sentido", list(self.SENTIDO_EDAD), self._opcion_cambiada)
        self.opciones["edad"] = barra

        for barra in self.opciones.values():
            barra.grid(row=2, column=0, sticky="w", pady=(0, 12))
            barra.grid_remove()
        self.al_cambiar_zoom()

        self.tabla_pacientes = PanelTabla(derecha)
        self.tabla_sangre = PanelTabla(derecha, columnas=COLUMNAS_SANGRE,
                                       estirar=("sangre", "cantidad", "porcentaje"))
        self.tarjeta = ctk.CTkFrame(derecha, corner_radius=12, fg_color=SUPERFICIE)
        self.lbl_valor = ctk.CTkLabel(self.tarjeta, text="", font=fuente(48, True), text_color=ACENTO)
        self.lbl_valor.pack(padx=40, pady=(28, 4))
        self.lbl_detalle = ctk.CTkLabel(self.tarjeta, text="", font=fuente(14), text_color=TEXTO_SUAVE)
        self.lbl_detalle.pack(padx=40, pady=(0, 28))

        self.tabla_pacientes.grid(row=3, column=0, sticky="nsew")
        self.tabla_sangre.grid(row=3, column=0, sticky="nsew")
        self.tarjeta.grid(row=3, column=0, sticky="new")
        self._mostrar_solo(None)

    def _mostrar_solo(self, widget) -> None:
        for candidato in (self.tabla_pacientes, self.tabla_sangre, self.tarjeta):
            if candidato is widget:
                candidato.grid()
            else:
                candidato.grid_remove()

    def _mostrar_opciones(self, clave: str) -> None:
        for nombre_reporte, barra in self.opciones.items():
            if nombre_reporte == clave:
                barra.grid()
            else:
                barra.grid_remove()

    def _marcar(self, clave: str) -> None:
        for nombre_boton, widget in self.botones.items():
            if nombre_boton == clave:
                widget.configure(fg_color=ACENTO, hover_color=ACENTO_HOVER, text_color="white")
            else:
                widget.configure(fg_color=NEUTRO, hover_color=NEUTRO_HOVER, text_color=TEXTO_NEUTRO)

    def _opcion_cambiada(self, _valor: str | None = None) -> None:
        if self._reporte is not None:
            self._mostrar_reporte(*self._reporte)

    def _actualizar_edades(self) -> None:
        valores = [self.TODAS, *(str(edad) for edad in self.gestor.edades_registradas())]
        self.menu_edad.configure(values=valores)
        # Esa edad ya no existe (se modificó o eliminó).
        if self.menu_edad.get() not in valores:
            self.menu_edad.set(self.TODAS)

    def al_cambiar_zoom(self) -> None:
        apilar = self.app.zoom >= self.ZOOM_PARA_APILAR
        for barra in self.opciones.values():
            barra.acomodar(apilar)

    def _pedir_reporte(self, clave: str) -> None:
        """Se ejecuta al pulsar un botón de reporte."""
        edad = None
        if clave == "mayores":
            edad = self.ent_edad.get().strip()
            if not edad:
                dialogos.advertir(
                    "Dato requerido",
                    "Escriba la edad para consultar a los pacientes mayores de esa edad.",
                    parent=self.app,
                )
                self.ent_edad.focus()
                return
        self._mostrar_reporte(clave, edad)

    def _mostrar_reporte(self, clave: str, edad: str | None = None) -> None:
        g = self.gestor
        total = g.total()

        if clave == "sangre":
            tipo = None if self.menu_sangre_tipo.get() == self.TODOS else self.menu_sangre_tipo.get()

            filas = []
            for tipo_fila, cantidad in g.reporte_tipo_sangre(tipo):
                porcentaje = f"{cantidad / total * 100:.1f} %" if total else "0.0 %"
                filas.append((tipo_fila, (tipo_fila, cantidad, porcentaje)))
            self.tabla_sangre.mostrar(filas)
            if tipo is None:
                self.lbl_titulo.configure(text="Pacientes por tipo de sangre")
                self.lbl_resumen.configure(text=f"Total de folios registrados: {total}")
            else:
                self.lbl_titulo.configure(text=f"Pacientes con tipo de sangre {tipo}")
                self.lbl_resumen.configure(
                    text=f"{folios_texto(filas[0][1][1])} de {total} registrados")
            self._mostrar_solo(self.tabla_sangre)

        elif clave == "promedio":
            self.lbl_titulo.configure(text="Promedio de edad")
            self.lbl_resumen.configure(text="")
            if total:
                self.lbl_valor.configure(text=f"{g.promedio_edad():.2f} años")
                self.lbl_detalle.configure(text=f"Calculado con {folios_texto(total)} registrados")
            else:
                self.lbl_valor.configure(text="Sin datos")
                self.lbl_detalle.configure(text="No hay pacientes registrados para calcular el promedio.")
            self._mostrar_solo(self.tarjeta)

        else:
            if clave == "listado":
                pacientes, titulo = g.listar_todos(), "Listado completo de pacientes"
            elif clave == "nombre":
                criterio = self.CRITERIO_NOMBRE[self.menu_nombre_por.get()]
                descendente = self.SENTIDO_NOMBRE[self.menu_nombre_sentido.get()]
                pacientes = g.ordenados_por_nombre(criterio, descendente)
                titulo = (f"Pacientes por {criterio}, de la Z a la A" if descendente
                          else f"Pacientes por {criterio}, de la A a la Z")
            elif clave == "edad":
                self._actualizar_edades()
                elegida = self.menu_edad.get()
                descendente = self.SENTIDO_EDAD[self.menu_edad_sentido.get()]
                if elegida == self.TODAS:
                    pacientes = g.ordenados_por_edad(descendente)
                    titulo = ("Pacientes por edad, de mayor a menor" if descendente
                              else "Pacientes por edad, de menor a mayor")
                else:
                    pacientes = g.ordenados_por_edad(descendente, int(elegida))
                    titulo = f"Pacientes de {anios_texto(elegida)}"
                # Con una edad elegida todos son iguales, así que el sentido no cambia nada.
                self.menu_edad_sentido.configure(state="normal" if elegida == self.TODAS else "disabled")
            else:
                try:
                    pacientes = g.mayores_de(edad)
                except ValidacionError as error:
                    dialogos.error("Dato no válido", error.mensaje, parent=self.app)
                    return
                edad = str(int(edad))
                titulo = f"Pacientes mayores de {anios_texto(edad)}"

            self.tabla_pacientes.mostrar_pacientes(pacientes)
            self.lbl_titulo.configure(text=titulo)
            if pacientes:
                self.lbl_resumen.configure(text=f"{folios_texto(len(pacientes))} en este reporte")
            elif clave == "mayores":
                self.lbl_resumen.configure(text=f"Ningún paciente tiene más de {anios_texto(edad)}.")
            else:
                self.lbl_resumen.configure(text="No hay pacientes registrados.")
            self._mostrar_solo(self.tabla_pacientes)

        self._mostrar_opciones(clave)
        self._reporte = (clave, edad)
        self._marcar(clave)

    def al_mostrar(self) -> None:
        """Vuelve a generar el reporte abierto para mostrar datos actuales."""
        clave, edad = self._reporte or ("sangre", None)
        self._mostrar_reporte(clave, edad)


class AplicacionGUI(ctk.CTk):
    """Ventana principal con la barra lateral y las secciones."""
    def __init__(self, gestor: GestorPacientes, preferencias: Preferencias | None = None) -> None:
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.gestor = gestor
        self.preferencias = preferencias or Preferencias()
        self.desplazables: list = []

        # Se aplica el zoom guardado antes de crear los elementos.
        self.nivel_zoom = self.preferencias.zoom
        self.zoom = self.nivel_zoom / 100
        ctk.set_widget_scaling(self.zoom)
        self._zoom_pedido = self.nivel_zoom
        self._zoom_idle = None
        self._estado_visual: dict | None = None
        self._restauracion = None

        self.title("Sistema de gestión de pacientes")
        self._ajustar_tamano()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        aplicar_estilo_tabla(self.zoom)

        self.botones_navegacion: dict[str, ctk.CTkButton] = {}
        self._crear_barra_lateral()

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.contenedor.grid_columnconfigure(0, weight=1)
        self.contenedor.grid_rowconfigure(0, weight=1)

        self.vistas: dict[str, VistaBase] = {
            "pacientes": VistaPacientes(self),
            "formulario": VistaFormulario(self),
            "busqueda": VistaBusqueda(self),
            "reportes": VistaReportes(self),
        }
        for vista in self.vistas.values():
            vista.grid(row=0, column=0, sticky="nsew")

        self.vista_actual = "pacientes"
        self.vistas["formulario"].preparar_registro()
        self.mostrar_vista("pacientes")
        self._configurar_atajos_zoom()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        # Con un zoom guardado grande, abre maximizada.
        if self.zoom > 1:
            self.after(300, self._maximizar)

    def _ajustar_tamano(self) -> None:
        """Tamaño inicial de 1260x780, más pequeño si la pantalla es pequeña."""
        try:
            escala = float(self._get_window_scaling())
        except Exception:
            escala = 1.0
        ancho = min(1260, int(self.winfo_screenwidth() / escala * 0.94))
        alto = min(780, int(self.winfo_screenheight() / escala * 0.86))
        self.geometry(f"{ancho}x{alto}")
        self.minsize(min(1100, ancho), min(640, alto))

    def _crear_barra_lateral(self) -> None:
        # La barra se puede desplazar: con zoom alto no cabe completa.
        barra = ctk.CTkScrollableFrame(self, width=232, corner_radius=0, fg_color=("#dbdbdb", "#2b2b2b"))
        barra.grid(row=0, column=0, sticky="ns")
        self.registrar_desplazable(barra)

        ctk.CTkLabel(barra, text="Gestión de\npacientes", font=fuente(24, True), justify="left",
                     anchor="w").pack(anchor="w", padx=8, pady=(18, 18))

        opciones = (
            ("pacientes", "Pacientes", lambda: self.mostrar_vista("pacientes")),
            ("formulario", "Registrar paciente", self._ir_a_registro),
            ("busqueda", "Buscar", lambda: self.mostrar_vista("busqueda")),
            ("reportes", "Reportes", lambda: self.mostrar_vista("reportes")),
        )
        for clave, texto, comando in opciones:
            boton_nav = ctk.CTkButton(
                barra, text=texto, command=comando, anchor="w", height=42, corner_radius=8,
                font=fuente(14, True), fg_color="transparent", hover_color=NEUTRO_HOVER,
                text_color=TEXTO_NEUTRO,
            )
            boton_nav.pack(fill="x", pady=3)
            self.botones_navegacion[clave] = boton_nav

        tarjeta = ctk.CTkFrame(barra, corner_radius=12, fg_color=SUPERFICIE)
        tarjeta.pack(fill="x", pady=(22, 16))
        self.lbl_total = ctk.CTkLabel(tarjeta, text="0", font=fuente(34, True), text_color=ACENTO)
        self.lbl_total.pack(pady=(12, 0))
        ctk.CTkLabel(tarjeta, text="folios registrados", font=fuente(12),
                     text_color=TEXTO_SUAVE).pack(pady=(0, 12))

        ctk.CTkLabel(barra, text="Apariencia", font=fuente(12), text_color=TEXTO_SUAVE,
                     anchor="w").pack(anchor="w", padx=8)
        selector = ctk.CTkOptionMenu(
            barra, values=["Claro", "Oscuro"], command=self.cambiar_apariencia,
            width=200, height=34, dynamic_resizing=False,
            fg_color=NEUTRO, button_color=NEUTRO_HOVER, button_hover_color=NEUTRO_HOVER,
            text_color=TEXTO_NEUTRO,
        )
        selector.set("Claro")
        selector.pack(anchor="w", pady=(4, 18))

    def _marcar_navegacion(self, activa: str) -> None:
        for clave, widget in self.botones_navegacion.items():
            if clave == activa:
                widget.configure(fg_color=ACENTO, hover_color=ACENTO_HOVER, text_color="white")
            else:
                widget.configure(fg_color="transparent", hover_color=NEUTRO_HOVER, text_color=TEXTO_NEUTRO)

    def _ir_a_registro(self) -> None:
        formulario = self.vistas["formulario"]
        # Venía de modificar: se parte de un formulario limpio.
        if formulario.modo != "registro":
            formulario.preparar_registro()
        self.mostrar_vista("formulario")

    def actualizar_contador(self) -> None:
        self.lbl_total.configure(text=str(self.gestor.total()))

    def mostrar_vista(self, nombre: str, marcar: str | None = None) -> None:
        for clave, vista in self.vistas.items():
            if clave == nombre:
                vista.grid()
            else:
                vista.grid_remove()
        self.vista_actual = nombre
        self.vistas[nombre].al_mostrar()
        self._marcar_navegacion(marcar or nombre)
        self.actualizar_contador()

    def editar_paciente(self, folio: str, origen: str) -> None:
        paciente = self.gestor.buscar_por_folio(folio)
        if paciente is None:
            dialogos.error(
                "Paciente no encontrado",
                f"El paciente con folio {folio} ya no existe.",
                parent=self,
            )
            self.datos_cambiaron()
            return
        self.vistas["formulario"].preparar_edicion(paciente, origen)
        self.mostrar_vista("formulario", marcar=origen)

    def datos_cambiaron(self) -> None:
        """Refresca lo que se ve después de registrar, modificar o eliminar."""
        self.actualizar_contador()
        self.vistas[self.vista_actual].al_mostrar()

    RETARDO_RESTAURACION_MS = 120

    def registrar_desplazable(self, zona) -> None:
        """Anota las zonas con desplazamiento para conservar su posición al cambiar el zoom."""
        self.desplazables.append(zona)

    def cambiar_zoom(self, direccion: int) -> None:
        """Un paso más grande (+1) o más pequeño (-1)."""
        self._pedir_zoom(nivel_siguiente(self._zoom_pedido, direccion))

    def _pedir_zoom(self, nivel: int) -> None:
        """Junta los cambios seguidos para cambiar el tamaño una sola vez."""
        self._zoom_pedido = nivel
        if self._zoom_idle is None:
            self._zoom_idle = self.after_idle(self._aplicar_zoom_pedido)

    def _aplicar_zoom_pedido(self) -> None:
        self._zoom_idle = None
        self.aplicar_zoom(self._zoom_pedido)

    def aplicar_zoom(self, nivel: int) -> None:
        """Agranda o reduce toda la aplicación y recuerda el tamaño elegido."""
        nivel = nivel_mas_cercano(nivel)
        self._zoom_pedido = nivel
        if nivel == self.nivel_zoom:
            return

        if self._estado_visual is None:
            self._estado_visual = self._capturar_estado()

        self.nivel_zoom = nivel
        self.zoom = nivel / 100
        ctk.set_widget_scaling(self.zoom)
        aplicar_estilo_tabla(self.zoom)
        for panel in PanelTabla._instancias:
            panel.escalar(self.zoom)
        for vista in self.vistas.values():
            vista.al_cambiar_zoom()

        self._restaurar_estado(self._estado_visual)
        if self._restauracion is not None:
            self._cancelar(self._restauracion)
        self._restauracion = self.after(self.RETARDO_RESTAURACION_MS, self._terminar_restauracion)
        self.preferencias.guardar_zoom(nivel)

    def _terminar_restauracion(self) -> None:
        self._restauracion = None
        estado, self._estado_visual = self._estado_visual, None
        if estado is not None:
            self._restaurar_estado(estado)

    def _cancelar(self, identificador) -> None:
        try:
            self.after_cancel(identificador)
        except Exception:
            pass

    def _capturar_estado(self) -> dict:
        """Anota lo que se está viendo para dejarlo igual después del cambio de zoom."""
        estado: dict = {"ventana": None, "foco": None, "tablas": [], "zonas": []}
        try:
            estado["ventana"] = (self.state(), tkinter.Wm.wm_geometry(self))
        except Exception:
            pass
        try:
            estado["foco"] = self.focus_get()
        except Exception:
            pass
        for panel in PanelTabla._instancias:
            try:
                tabla = panel.tabla
                seleccion = tuple(tabla.selection())
                a_la_vista = (not seleccion or not tabla.winfo_ismapped()
                              or bool(tabla.bbox(seleccion[0])))
                estado["tablas"].append(
                    (tabla, seleccion, _fraccion(tabla.yview()), _fraccion(tabla.xview()), a_la_vista))
            except Exception:
                pass
        for zona in self.desplazables:
            try:
                estado["zonas"].append((zona, _fraccion(zona._parent_canvas.yview())))
            except Exception:
                pass
        return estado

    def _restaurar_estado(self, estado: dict) -> None:
        """Deja todo como estaba antes del cambio de zoom."""
        try:
            modo, geometria = estado["ventana"]
            if modo == "normal" and self.state() == "normal" and tkinter.Wm.wm_geometry(self) != geometria:
                tkinter.Wm.wm_geometry(self, geometria)
        except Exception:
            pass
        for tabla, seleccion, vertical, horizontal, a_la_vista in estado["tablas"]:
            try:
                vigentes = tuple(fila for fila in seleccion if tabla.exists(fila))
                if vigentes != tuple(tabla.selection()):
                    tabla.selection_set(vigentes)
                tabla.yview_moveto(vertical)
                tabla.xview_moveto(horizontal)
                if vigentes and a_la_vista:
                    tabla.see(vigentes[0])
            except Exception:
                pass
        for zona, vertical in estado["zonas"]:
            try:
                zona._parent_canvas.yview_moveto(vertical)
            except Exception:
                pass
        try:
            foco = estado["foco"]
            if foco is not None and self.focus_get() is not foco:
                foco.focus_set()
        except Exception:
            pass

    def _maximizar(self) -> None:
        """Maximiza la ventana al abrir con un zoom grande."""
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass

    def _configurar_atajos_zoom(self) -> None:
        """Ctrl y + agranda, Ctrl y - reduce, Ctrl y 0 vuelve al tamaño normal."""
        atajos = (
            (("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"), lambda _evento: self.cambiar_zoom(1)),
            (("<Control-minus>", "<Control-KP_Subtract>"), lambda _evento: self.cambiar_zoom(-1)),
            (("<Control-Key-0>", "<Control-KP_0>"), lambda _evento: self._pedir_zoom(100)),
        )
        for secuencias, accion in atajos:
            for secuencia in secuencias:
                try:
                    self.bind(secuencia, accion)
                except Exception:
                    pass

    def cambiar_apariencia(self, opcion: str) -> None:
        ctk.set_appearance_mode("Dark" if opcion == "Oscuro" else "Light")
        aplicar_estilo_tabla(self.zoom)
        for panel in PanelTabla._instancias:
            panel.actualizar_colores()

    def cerrar(self) -> None:
        """Guarda por última vez y cierra la ventana."""
        for pendiente in (self._zoom_idle, self._restauracion):
            if pendiente is not None:
                self._cancelar(pendiente)
        try:
            self.gestor.guardar()
        except AlmacenamientoError as error:
            if not dialogos.preguntar(
                "No se pudo guardar",
                f"{error}\n\n¿Desea cerrar la aplicación de todos modos?",
                icon="warning", parent=self,
            ):
                return
        self.destroy()
