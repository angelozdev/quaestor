"""Tool registration and the growth pattern.

`register_core_tools(mcp)` registers the P2 core tools. P3/P4/P5 add their own
`register_<feature>_tools(mcp)` and `server.py` calls each — growing the surface
means one extra line of wiring, never a change to transport or auth.

Each tool opens ONE Session per call, bound to ``db.engine`` resolved
dynamically (so tests can swap the engine), and delegates to a `core` impl that
already translates domain errors to text.
"""
from sqlmodel import Session

from .. import db
from .tools import core
from .tools.core import (
    ConsultarTasaInput,
    ConsultarTxInput,
    FijarTasaInput,
    RegistrarGastoInput,
    RegistrarIngresoInput,
    TransferirInput,
)

CORE_TOOL_NAMES = (
    "registrar_gasto",
    "registrar_ingreso",
    "transferir",
    "fijar_tasa_fx",
    "consultar_transacciones",
    "consultar_tasa_fx",
    "listar_cuentas",
    "listar_categorias",
    "listar_tags",
)


def register_core_tools(mcp) -> None:
    """Register the 9 P2 core tools on the given FastMCP instance."""

    @mcp.tool(name="registrar_gasto", description="Registra un gasto en una cuenta.")
    def registrar_gasto(gasto: RegistrarGastoInput) -> str:
        with Session(db.engine) as session:
            return core.registrar_gasto(session, gasto)

    @mcp.tool(name="registrar_ingreso", description="Registra un ingreso en una cuenta.")
    def registrar_ingreso(ingreso: RegistrarIngresoInput) -> str:
        with Session(db.engine) as session:
            return core.registrar_ingreso(session, ingreso)

    @mcp.tool(name="transferir", description="Transfiere dinero entre dos cuentas.")
    def transferir(transferencia: TransferirInput) -> str:
        with Session(db.engine) as session:
            return core.transferir(session, transferencia)

    @mcp.tool(name="fijar_tasa_fx", description="Fija la tasa USD→COP de una fecha.")
    def fijar_tasa_fx(tasa: FijarTasaInput) -> str:
        with Session(db.engine) as session:
            return core.fijar_tasa_fx(session, tasa)

    @mcp.tool(
        name="consultar_transacciones",
        description="Lista transacciones con filtros opcionales (fechas, cuenta, categoría, tag, tipo, estado).",
    )
    def consultar_transacciones(filtros: ConsultarTxInput) -> str:
        with Session(db.engine) as session:
            return core.consultar_transacciones(session, filtros)

    @mcp.tool(name="consultar_tasa_fx", description="Consulta la tasa USD→COP vigente para una fecha.")
    def consultar_tasa_fx(consulta: ConsultarTasaInput) -> str:
        with Session(db.engine) as session:
            return core.consultar_tasa_fx(session, consulta)

    @mcp.tool(name="listar_cuentas", description="Lista las cuentas con su balance y moneda.")
    def listar_cuentas() -> str:
        with Session(db.engine) as session:
            return core.listar_cuentas(session)

    @mcp.tool(name="listar_categorias", description="Lista las categorías y su grupo.")
    def listar_categorias() -> str:
        with Session(db.engine) as session:
            return core.listar_categorias(session)

    @mcp.tool(name="listar_tags", description="Lista las etiquetas existentes.")
    def listar_tags() -> str:
        with Session(db.engine) as session:
            return core.listar_tags(session)
