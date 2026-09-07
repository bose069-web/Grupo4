# cursor
from typing import Any


# FUNCIÓN 1: Nombres de variables crípticos (a, b, c, temp)
def calc(
    precio_unitario: float, cantidad: int, porcentaje_descuento: float
) -> float:
    subtotal = precio_unitario * cantidad
    importe_descuento = subtotal * porcentaje_descuento
    total = subtotal - importe_descuento
    return total


# FUNCIÓN 2: Condicionales muy anidados (Nido de IFs)
def validar_acceso(user: dict[str, Any] | None) -> str:
    if user is None:
        return "Usuario no existe"
    if user.get("activo") is not True:
        return "Usuario inactivo"
    if user.get("edad", 0) < 18:
        return "Menor de edad"
    if user.get("rol") == "admin":
        return "Acceso total"
    return "Acceso limitado"


# FUNCIÓN 3: Hace demasiadas cosas (Validación + Cálculo + Formato)
def validar_email(email: str) -> bool:
    return "@" in email and "." in email


def calcular_total_con_descuento(productos: list[dict[str, Any]]) -> float:
    total = sum(producto["precio"] for producto in productos)
    if total > 100:
        total = total * 0.9
    return total


def procesar_pedido(
    cliente: str, productos: list[dict[str, Any]], email: str
) -> str:
    if not validar_email(email):
        return "Email no válido"

    total = calcular_total_con_descuento(productos)
    # Generar resumen
    resumen = (
        f"Pedido de {cliente}: Total a pagar {total}€ "
        f"(Notificación enviada a {email})"
    )
    return resumen
