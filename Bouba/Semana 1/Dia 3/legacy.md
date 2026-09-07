# FUNCIÓN 1: Nombres de variables crípticos (a, b, c, temp)
def calc(a, b, c):
    sub = a * b
    temp = sub * c
    res = sub - temp
    return res


# FUNCIÓN 2: Condicionales muy anidados (Nido de IFs)
def validar_acceso(user):
    if user != None:
        if user.get("activo") == True:
            if user.get("edad") >= 18:
                if user.get("rol") == "admin":
                    return "Acceso total"
                else:
                    return "Acceso limitado"
            else:
                return "Menor de edad"
        else:
            return "Usuario inactivo"
    else:
        return "Usuario no existe"


# FUNCIÓN 3: Hace demasiadas cosas (Validación + Cálculo + Formato)
def procesar_pedido(cliente, productos, email):
    # Validar email
    if "@" not in email or "." not in email:
        return "Email no válido"
    
    # Calcular total
    total = 0
    for p in productos:
        total = total + p["precio"]
    
    # Aplicar descuento si supera 100
    if total > 100:
        total = total * 0.9
        
    # Generar resumen
    resumen = f"Pedido de {cliente}: Total a pagar {total}€ (Notificación enviada a {email})"
    return resumen
