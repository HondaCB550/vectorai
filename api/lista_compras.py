"""Lista de compras: la comparativa reagrupada como el pedido de cada proveedor.

La regla ("de este proveedor, los ítems donde tiene el mejor precio") la usan
los tres exportadores — Excel, PDF e imagen — más el tab de compras del
frontend. Vivía duplicada en exportar_excel y en el frontend; acá queda una
sola fuente para el lado Python, así los tres archivos que descarga el usuario
dicen siempre lo mismo.

IMPORTANTE — de dónde sale el ganador: se confía en `mejor_proveedor` de cada
fila, que `_aplicar_filtros()` (main.py) ya recalculó para la vista activa
(IVA sí/no, descuento). En vista efectivo el ranking puede diferir del neto
guardado, por eso NO hay que recalcularlo acá: llega listo.
"""


def _cant_de(fila: dict, prov: str) -> float:
    """Cantidad del ítem: la de la fila, o la que trajo el precio del proveedor."""
    return fila.get("cant") or (fila.get("precios", {}).get(prov) or {}).get("cant") or 1


def pedidos_por_proveedor(comparativo: list[dict]) -> list[dict]:
    """Agrupa la comparativa en un pedido por proveedor.

    Devuelve una lista de dicts:
        {"proveedor": str, "filas": [fila...], "total": float, "n_items": int}

    - Solo entran filas donde el proveedor es `mejor_proveedor` Y tiene precio.
    - Las filas van ordenadas por (rubro, material), igual que las hojas del Excel.
    - Los proveedores van ordenados por total descendente, igual que el tab de
      compras en pantalla: primero el pedido más grande.
    - Un proveedor sin ítems ganadores no aparece.
    """
    por_prov: dict[str, list[dict]] = {}
    for fila in comparativo:
        prov = fila.get("mejor_proveedor")
        if not prov or prov not in (fila.get("precios") or {}):
            continue
        por_prov.setdefault(prov, []).append(fila)

    pedidos = []
    for prov, filas in por_prov.items():
        filas_ord = sorted(filas, key=lambda f: (f.get("rubro") or "", f.get("material") or ""))
        total = 0.0
        for f in filas_ord:
            precio = (f["precios"][prov] or {}).get("precio_sin_iva") or 0
            total += precio * _cant_de(f, prov)
        pedidos.append({
            "proveedor": prov,
            "filas":     filas_ord,
            "total":     round(total, 2),
            "n_items":   len(filas_ord),
        })

    pedidos.sort(key=lambda p: -p["total"])
    return pedidos


def subtotal_fila(fila: dict, prov: str) -> tuple[float, float, float]:
    """(precio_unitario, cantidad, subtotal) del ítem para ese proveedor.

    Que el subtotal se calcule en un solo lugar evita que Excel, PDF e imagen
    redondeen distinto y muestren totales que no coinciden entre sí.
    """
    precio = (fila.get("precios", {}).get(prov) or {}).get("precio_sin_iva") or 0
    cant   = _cant_de(fila, prov)
    return precio, cant, round(precio * cant, 2)
