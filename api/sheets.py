"""
sheets.py — Generador de Google Sheets para comparativas de presupuestos Vectorai

Crea un Google Sheet con la comparativa formateada:
  - Header con colores por proveedor
  - Celda con mejor precio en verde por fila
  - Totales al pie
  - Compartido como "cualquiera con el link puede ver"

Requiere: GOOGLE_SERVICE_ACCOUNT_FILE en .env (path al JSON de la service account)
"""
import os
import json
from datetime import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Colores por posición de proveedor (hasta 6 proveedores)
COLORES_PROV = [
    {"red": 0.20, "green": 0.45, "blue": 0.76},  # azul
    {"red": 0.83, "green": 0.36, "blue": 0.00},  # naranja
    {"red": 0.18, "green": 0.63, "blue": 0.37},  # verde oscuro
    {"red": 0.60, "green": 0.20, "blue": 0.60},  # violeta
    {"red": 0.75, "green": 0.15, "blue": 0.15},  # rojo
    {"red": 0.30, "green": 0.60, "blue": 0.70},  # celeste
]

COLOR_MEJOR   = {"red": 0.85, "green": 0.97, "blue": 0.86}   # verde claro
COLOR_HEADER  = {"red": 0.15, "green": 0.20, "blue": 0.30}   # azul oscuro
COLOR_SUBHDR  = {"red": 0.93, "green": 0.94, "blue": 0.96}   # gris claro
COLOR_BLANCO  = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
COLOR_TEXTO_W = {"red": 1.0,  "green": 1.0,  "blue": 1.0}


def sheets_disponible() -> bool:
    """True si hay credenciales de service account configuradas."""
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return True
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    return Path(sa_file).exists()


def _creds() -> Credentials:
    # Railway/hosting sin filesystem persistente: el JSON completo va en la env var
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        return Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if not Path(sa_file).exists():
        raise FileNotFoundError(
            f"Service account JSON no encontrado en '{sa_file}'. "
            "Descargalo de Google Cloud Console y configurá GOOGLE_SERVICE_ACCOUNT_FILE "
            "o pegá el contenido del JSON en GOOGLE_SERVICE_ACCOUNT_JSON."
        )
    return Credentials.from_service_account_file(sa_file, scopes=SCOPES)


def _cell(value, row: int, col: int) -> dict:
    """Construye un CellData con valor."""
    if isinstance(value, (int, float)):
        return {"userEnteredValue": {"numberValue": value},
                "userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}}
    return {"userEnteredValue": {"stringValue": str(value) if value is not None else ""}}


def _color_bg(color: dict) -> dict:
    return {"backgroundColor": color}


def _bold(bold=True) -> dict:
    return {"textFormat": {"bold": bold}}


def crear_sheet_comparativa(
    comparativo: list[dict],
    proveedores: list[str],
    titulo: str = None,
    user_mail: str = None,
) -> str:
    """
    Crea un Google Sheet con el comparativo y devuelve la URL pública.

    comparativo: lista de filas del endpoint /analizar
    proveedores: lista de nombres de proveedores (en orden de columnas)
    titulo: título del Sheet (default: "Vectorai — Comparativa YYYY-MM-DD")
    user_mail: si se pasa, comparte el Sheet con ese mail como editor
    """
    creds = _creds()
    sheets_svc = build("sheets", "v4", credentials=creds)
    drive_svc  = build("drive",  "v3", credentials=creds)

    fecha = datetime.now().strftime("%d/%m/%Y")
    titulo = titulo or f"Vectorai — Comparativa {datetime.now().strftime('%Y-%m-%d')}"

    # ── Armar datos ────────────────────────────────────────────────────────────
    # Columnas: RUBRO | MATERIAL | UNIDAD | [prov1] | [prov2] | ... | MEJOR | AHORRO
    col_rubro   = 0
    col_mat     = 1
    col_unidad  = 2
    col_provs   = list(range(3, 3 + len(proveedores)))
    col_mejor   = 3 + len(proveedores)
    col_ahorro  = col_mejor + 1
    total_cols  = col_ahorro + 1

    rows_data = []

    # Fila 0: título grande
    rows_data.append({
        "values": [
            {
                "userEnteredValue": {"stringValue": titulo},
                "userEnteredFormat": {
                    **_color_bg(COLOR_HEADER),
                    "textFormat": {"bold": True, "fontSize": 14,
                                   "foregroundColor": COLOR_TEXTO_W},
                    "verticalAlignment": "MIDDLE",
                    "horizontalAlignment": "LEFT",
                    "padding": {"left": 12},
                },
            }
        ] + [{"userEnteredFormat": _color_bg(COLOR_HEADER)} for _ in range(total_cols - 1)]
    })

    # Fila 1: subtítulo (fecha + "s/IVA")
    rows_data.append({
        "values": [
            {
                "userEnteredValue": {"stringValue": f"Generado el {fecha} · Precios sin IVA · Vectorai"},
                "userEnteredFormat": {
                    **_color_bg(COLOR_HEADER),
                    "textFormat": {"italic": True, "fontSize": 10,
                                   "foregroundColor": {"red": 0.75, "green": 0.80, "blue": 0.90}},
                    "horizontalAlignment": "LEFT",
                    "padding": {"left": 12},
                },
            }
        ] + [{"userEnteredFormat": _color_bg(COLOR_HEADER)} for _ in range(total_cols - 1)]
    })

    # Fila 2: vacía separadora
    rows_data.append({"values": [{"userEnteredValue": {"stringValue": ""}}]})

    # Fila 3: header de columnas
    header_values = []
    for label, col_idx in [("Rubro", col_rubro), ("Material", col_mat), ("Unidad", col_unidad)]:
        header_values.append({
            "userEnteredValue": {"stringValue": label},
            "userEnteredFormat": {
                **_color_bg(COLOR_SUBHDR),
                **_bold(),
                "horizontalAlignment": "LEFT",
                "padding": {"left": 8},
                "borders": {"bottom": {"style": "SOLID", "width": 2,
                                       "color": {"red": 0.70, "green": 0.72, "blue": 0.75}}},
            }
        })

    for i, prov in enumerate(proveedores):
        color = COLORES_PROV[i % len(COLORES_PROV)]
        header_values.append({
            "userEnteredValue": {"stringValue": prov},
            "userEnteredFormat": {
                "backgroundColor": color,
                "textFormat": {"bold": True, "foregroundColor": COLOR_TEXTO_W},
                "horizontalAlignment": "CENTER",
                "borders": {"bottom": {"style": "SOLID", "width": 2,
                                       "color": {"red": 0.0, "green": 0.0, "blue": 0.0, "alpha": 0.3}}},
            }
        })

    for label in ["Mejor precio", "Ahorro s/IVA"]:
        header_values.append({
            "userEnteredValue": {"stringValue": label},
            "userEnteredFormat": {
                **_color_bg(COLOR_SUBHDR),
                **_bold(),
                "horizontalAlignment": "CENTER",
                "borders": {"bottom": {"style": "SOLID", "width": 2,
                                       "color": {"red": 0.70, "green": 0.72, "blue": 0.75}}},
            }
        })

    rows_data.append({"values": header_values})

    # Filas de datos — agrupar por rubro
    ultimo_rubro = None
    totales = {p: 0.0 for p in proveedores}

    for row in comparativo:
        rubro   = row.get("rubro", "")
        mat     = row.get("material", "")
        unidad  = row.get("unidad", "")
        precios = row.get("precios", {})
        mejor   = row.get("mejor_proveedor", "")
        ahorro  = row.get("ahorro", 0) or 0

        # Separador de rubro
        if rubro != ultimo_rubro:
            if ultimo_rubro is not None:
                rows_data.append({"values": []})  # fila vacía entre rubros
            rubro_row = [{
                "userEnteredValue": {"stringValue": rubro.upper()},
                "userEnteredFormat": {
                    **_color_bg({"red": 0.91, "green": 0.93, "blue": 0.96}),
                    "textFormat": {"bold": True, "fontSize": 9,
                                   "foregroundColor": {"red": 0.25, "green": 0.35, "blue": 0.55}},
                    "horizontalAlignment": "LEFT",
                    "padding": {"left": 8},
                }
            }] + [{"userEnteredFormat": _color_bg({"red": 0.91, "green": 0.93, "blue": 0.96})}
                  for _ in range(total_cols - 1)]
            rows_data.append({"values": rubro_row})
            ultimo_rubro = rubro

        # Encontrar precio mínimo para colorear
        precios_vals = {p: precios[p]["precio_sin_iva"] for p in proveedores if p in precios}
        precio_min = min(precios_vals.values()) if len(precios_vals) > 1 else None

        cells = [
            # Rubro (vacío en fila de dato porque ya está en el separador)
            {"userEnteredValue": {"stringValue": ""},
             "userEnteredFormat": {"textFormat": {"fontSize": 9}}},
            # Material
            {"userEnteredValue": {"stringValue": mat},
             "userEnteredFormat": {
                 "textFormat": {"fontSize": 9},
                 "horizontalAlignment": "LEFT",
                 "padding": {"left": 12},
                 "wrapStrategy": "WRAP",
             }},
            # Unidad
            {"userEnteredValue": {"stringValue": unidad},
             "userEnteredFormat": {
                 "textFormat": {"fontSize": 9},
                 "horizontalAlignment": "CENTER",
             }},
        ]

        for prov in proveedores:
            val = precios_vals.get(prov)
            is_mejor = (precio_min is not None and val is not None and val == precio_min and len(precios_vals) > 1)
            if val is not None:
                totales[prov] += val
            cell = {
                "userEnteredValue": {"numberValue": val} if val is not None else {"stringValue": "—"},
                "userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                    "horizontalAlignment": "RIGHT",
                    "padding": {"right": 8},
                    "textFormat": {"bold": is_mejor, "fontSize": 9},
                    **({"backgroundColor": COLOR_MEJOR} if is_mejor else {}),
                }
            }
            cells.append(cell)

        # Mejor proveedor
        cells.append({
            "userEnteredValue": {"stringValue": mejor or ""},
            "userEnteredFormat": {
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": bool(mejor), "fontSize": 9,
                               "foregroundColor": {"red": 0.10, "green": 0.50, "blue": 0.25} if mejor else {}},
            }
        })

        # Ahorro
        cells.append({
            "userEnteredValue": {"numberValue": ahorro} if ahorro else {"stringValue": ""},
            "userEnteredFormat": {
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                "horizontalAlignment": "RIGHT",
                "padding": {"right": 8},
                "textFormat": {"fontSize": 9,
                               "foregroundColor": {"red": 0.10, "green": 0.50, "blue": 0.25} if ahorro else {}},
            }
        })

        rows_data.append({"values": cells})

    # Fila de totales
    rows_data.append({"values": []})
    total_row = [
        {"userEnteredValue": {"stringValue": ""},
         "userEnteredFormat": _color_bg(COLOR_SUBHDR)},
        {"userEnteredValue": {"stringValue": "TOTAL (matches OK+REVISAR)"},
         "userEnteredFormat": {**_color_bg(COLOR_SUBHDR), **_bold(),
                               "padding": {"left": 12}, "textFormat": {"bold": True, "fontSize": 9}}},
        {"userEnteredValue": {"stringValue": ""},
         "userEnteredFormat": _color_bg(COLOR_SUBHDR)},
    ]
    for prov in proveedores:
        total_row.append({
            "userEnteredValue": {"numberValue": round(totales[prov], 2)},
            "userEnteredFormat": {
                **_color_bg(COLOR_SUBHDR),
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                "horizontalAlignment": "RIGHT",
                "padding": {"right": 8},
                **_bold(),
                "textFormat": {"bold": True, "fontSize": 9},
            }
        })
    total_row += [{"userEnteredFormat": _color_bg(COLOR_SUBHDR)} for _ in range(2)]
    rows_data.append({"values": total_row})

    # ── Crear el Spreadsheet ───────────────────────────────────────────────────
    spreadsheet = sheets_svc.spreadsheets().create(body={
        "properties": {"title": titulo, "locale": "es_AR"},
        "sheets": [{
            "properties": {
                "title": "Comparativa",
                "gridProperties": {"frozenRowCount": 4, "frozenColumnCount": 2},
            },
            "data": [{"startRow": 0, "startColumn": 0, "rowData": rows_data}],
        }]
    }).execute()

    sheet_id      = spreadsheet["spreadsheetId"]
    sheet_tab_id  = spreadsheet["sheets"][0]["properties"]["sheetId"]
    sheet_url     = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    # ── Requests de formato adicional ──────────────────────────────────────────
    requests_fmt = [
        # Merge fila de título (fila 0) y subtítulo (fila 1)
        {"mergeCells": {"range": {"sheetId": sheet_tab_id,
                                  "startRowIndex": 0, "endRowIndex": 1,
                                  "startColumnIndex": 0, "endColumnIndex": total_cols},
                        "mergeType": "MERGE_ALL"}},
        {"mergeCells": {"range": {"sheetId": sheet_tab_id,
                                  "startRowIndex": 1, "endRowIndex": 2,
                                  "startColumnIndex": 0, "endColumnIndex": total_cols},
                        "mergeType": "MERGE_ALL"}},
        # Alto de fila título
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_tab_id, "dimension": "ROWS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 48}, "fields": "pixelSize"}},
        # Ancho columnas
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_tab_id, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 0}, "fields": "pixelSize"}},   # Rubro oculto
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_tab_id, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 320}, "fields": "pixelSize"}},  # Material
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_tab_id, "dimension": "COLUMNS",
                      "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 65}, "fields": "pixelSize"}},   # Unidad
    ]

    # Ancho columnas de precios
    for i in range(len(proveedores) + 2):
        requests_fmt.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_tab_id, "dimension": "COLUMNS",
                      "startIndex": 3 + i, "endIndex": 4 + i},
            "properties": {"pixelSize": 140 if i < len(proveedores) else 130},
            "fields": "pixelSize"}})

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests_fmt}
    ).execute()

    # ── Compartir como "cualquiera con el link puede ver" ─────────────────────
    drive_svc.permissions().create(
        fileId=sheet_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # Compartir con el usuario como editor (si se pasa mail)
    if user_mail:
        try:
            drive_svc.permissions().create(
                fileId=sheet_id,
                body={"type": "user", "role": "writer", "emailAddress": user_mail},
                sendNotificationEmail=False,
            ).execute()
        except HttpError:
            pass  # Si falla el compartido individual, el link público sigue funcionando

    return sheet_url
