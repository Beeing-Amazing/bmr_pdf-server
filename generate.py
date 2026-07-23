from typing import BinaryIO, Annotated, Optional, Any
from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import pandas as pd
import xlsxwriter

import utils
from utils import authenticate

router = APIRouter(prefix="/generate", tags=["excel","files"])


class OverviewRow(BaseModel):
    mail_ID: str
    mail_threadID: str
    numero_ec: Optional[str] = None
    cliente: Optional[str] = None
    proyecto: Optional[str] = None
    resumen: Optional[str] = None
    correo_estado: str
    overview_estado: Optional[str] = None
    plazos: bool
    incidencias: bool
    correo_id: int
    overview_id: Optional[int] = None
    correo_created_at: Optional[datetime] = None
    overview_created_at: Optional[datetime] = None
    pedido_created_at: Optional[datetime] = None
    prep_created_at: Optional[datetime] = None
    fabr_created_at: Optional[datetime] = None
MAX_ROWS = 100_000

@router.post("/overview-excel")
async def json_to_excel(
    values: Annotated[list[OverviewRow], Body(min_length=1)],
    user: str = Depends(authenticate)
):
    SHEET1_NAME = "Correos"
    SHEET2_NAME = "Proyectos"
    if len(values) < MAX_ROWS: 
        # NOTE: 1. PREP DF
        df = pd.DataFrame([row.model_dump() for row in values])
        dtype_map = {
            "mail_ID": "string",
            "mail_threadID": "string",
            "numero_ec": "string",
            "cliente": "string",
            "proyecto": "string",
            "resumen": "string",
            "correo_estado": "string",
            "overview_estado": "string",
            "plazos": "boolean",
            "incidencias": "boolean",
            "correo_id": "Int64",
            "overview_id": "Int64",
        }
        cols_rename_correos = {
            "mail_ID": "",
            "mail_threadID": "",
            "numero_ec": "Num EC",
            "cliente": "Cliente",
            "proyecto": "Proyecto",
            "resumen": "Resumen",
            "correo_estado": "Estado",
            "overview_estado": "",
            "plazos": "",
            "incidencias": "",
            "correo_id": "",
            "overview_id": "",
            "correo_created_at": "Fecha" # in CORREOS omit datetime cols, only received date
        }
        cols_rename_overview = {
            "mail_ID": "",
            "mail_threadID": "",
            "numero_ec": "Num EC",
            "cliente": "Cliente",
            "proyecto": "Proyecto",
            "resumen": "",
            "correo_estado": "",
            "overview_estado": "Estado",
            "plazos": "Plazos",
            "incidencias": "Incidencias",
            "correo_id": "",
            "overview_id": "",
            "correo_created_at": "",
            "overview_created_at": "",
            "pedido_created_at": "Pedido Fecha",
            "prep_created_at": "Preparacion Fecha",
            "fabr_created_at": "Fabricacion Fecha",
        }
        datetime_cols = df.filter(regex="_created_at$").columns

        # astype non-datetime columns
        df = df.astype(dtype_map)
        # convert datetimes
        for col in datetime_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            if df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_convert("Europe/Madrid").dt.tz_localize(None)

        df_correos = (
            df.loc[:, list(cols_rename_correos.keys())]
              .rename(columns=cols_rename_correos)
              .loc[:, lambda x: x.columns != ""]
        )
        df_overview = (
            df.loc[:, list(cols_rename_overview.keys())]
            .rename(columns=cols_rename_overview)
            .loc[:, lambda x: x.columns != ""]
        )
        proyectos = (
            df_overview
            .groupby(["Num EC", "Cliente", "Proyecto"], as_index=False)
            .agg({
                # "Estado": "first",
                # "Plazos": "first",
                # "Incidencias": "first",
                **{
                    col: "first"
                    for col in df_overview.columns
                    if col not in {
                        "Num EC", "Cliente", "Proyecto",
                        # "Estado", "Plazos", "Incidencias"
                    }
                }
            })
        )
        estado_col_correos = df_correos.columns.get_loc("Estado")
        estado_col_proyectos = proyectos.columns.get_loc("Estado")
        incid_col_proyectos = proyectos.columns.get_loc("Incidencias")
        plaz_col_proyectos = proyectos.columns.get_loc("Plazos")

        # NOTE: 2. CREATE WRITER
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            workbook = writer.book

            # NOTE: 2.1 SHEETS FORMATS
            wrap_format = workbook.add_format({
                "text_wrap": True,
                "valign": "top",
            })
            header_format = workbook.add_format({
                "bold": True,
                "text_wrap": True,
                "valign": "top",
                "fg_color": "#D7E4BC",
                "border": 1,
            })
            red_warn = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})

            # NOTE: 3. FORMAT EXCEL SHEET CORREOS
            df_correos.to_excel(
                writer,
                sheet_name=SHEET1_NAME,
                startrow=1,
                header=False,
                index=False
            )
            worksheet_correos = writer.sheets[SHEET1_NAME]
            worksheet_correos.autofit()
            worksheet_correos.conditional_format(
                1, estado_col_correos, len(df_correos), estado_col_correos,
                {
                    "type": "cell",
                    "criteria": "==",
                    "value": '"INCIDENCIA"',
                    "format": red_warn
                },
            )
            worksheet_correos.autofilter(0, 0, len(df_correos), len(df_correos.columns) - 1)

            column_widths = { "Resumen": 60, "Nº Correos": 15, "Nº ECs": 12 }
            default_width = 20

            for col_num, col_name in enumerate(df_correos.columns):
                worksheet_correos.write(0, col_num, col_name, header_format)
                worksheet_correos.set_column(
                    col_num,
                    col_num,
                    column_widths.get(col_name, default_width),
                    wrap_format,
                )

            # NOTE: 4.1 PROYECTOS DF
            proyectos["Nº Correos"] = proyectos.apply(
                lambda row: (
                    (df_correos["Cliente"] == row["Cliente"]) &
                    (df_correos["Proyecto"] == row["Proyecto"])
                    ).sum(),
                axis=1)

            proyectos["Nº ECs"] = proyectos.apply(
                lambda row: (
                    df_correos.loc[
                        (df_correos["Cliente"] == row["Cliente"]) &
                        (df_correos["Proyecto"] == row["Proyecto"]),
                        "Num EC"
                        ].nunique()),
                axis=1)

            # NOTE: 4.2 FORMAT EXCEL SHEET OVERVIEW
            proyectos.to_excel(
                writer,
                sheet_name=SHEET2_NAME,
                startrow=1,
                header=False,
                index=False
            )
            worksheet_overview = writer.sheets[SHEET2_NAME]
            worksheet_overview.autofit()
            worksheet_overview.conditional_format(
                1, estado_col_proyectos, len(proyectos), estado_col_proyectos,
                {
                    "type": "cell",
                    "criteria": "==",
                    "value": '"INCIDENCIA"',
                    "format": red_warn
                }
            )
            worksheet_overview.conditional_format(
                1, incid_col_proyectos, len(proyectos), incid_col_proyectos,
                {
                    "type": "cell",
                    "criteria": "==",
                    "value": 'TRUE',
                    "format": red_warn
                }
            )
            worksheet_overview.conditional_format(
                1, plaz_col_proyectos, len(proyectos), plaz_col_proyectos,
                {
                    "type": "cell",
                    "criteria": "==",
                    "value": 'TRUE',
                    "format": red_warn
                }
            )
            worksheet_overview.autofilter(0, 0, len(proyectos), len(proyectos.columns) - 1)

            # Write all overview values
            for col_num, col_name in enumerate(proyectos.columns):
                worksheet_overview.write(0, col_num, col_name, header_format)
                worksheet_overview.set_column(
                    col_num,
                    col_num,
                    column_widths.get(col_name, default_width),
                    wrap_format,
                )
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=BMR_EC_seguimiento.xlsx"
            }
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Too many rows."
        )
