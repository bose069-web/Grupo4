import pytest

from legacy import (
    calc,
    calcular_total_con_descuento,
    procesar_pedido,
    validar_acceso,
    validar_email,
)


# --- calc ---


class TestCalc:
    def test_sin_descuento(self):
        assert calc(10.0, 3, 0.0) == 30.0

    def test_con_descuento(self):
        assert calc(100.0, 2, 0.1) == 180.0

    def test_descuento_total(self):
        assert calc(50.0, 4, 1.0) == 0.0

    def test_precio_cero(self):
        assert calc(0.0, 10, 0.2) == 0.0

    def test_cantidad_cero(self):
        assert calc(25.0, 0, 0.15) == 0.0

    def test_descuento_cero_y_cantidad_cero(self):
        assert calc(0.0, 0, 0.0) == 0.0

    def test_precio_unitario_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            calc(None, 2, 0.1)  # type: ignore[arg-type]

    def test_cantidad_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            calc(10.0, None, 0.1)  # type: ignore[arg-type]

    def test_porcentaje_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            calc(10.0, 2, None)  # type: ignore[arg-type]


# --- validar_acceso ---


class TestValidarAcceso:
    def test_admin_activo_mayor_de_edad(self):
        user = {"activo": True, "edad": 30, "rol": "admin"}
        assert validar_acceso(user) == "Acceso total"

    def test_usuario_limitado_activo_mayor_de_edad(self):
        user = {"activo": True, "edad": 25, "rol": "cliente"}
        assert validar_acceso(user) == "Acceso limitado"

    def test_usuario_none(self):
        assert validar_acceso(None) == "Usuario no existe"

    def test_diccionario_vacio(self):
        assert validar_acceso({}) == "Usuario inactivo"

    def test_activo_false(self):
        user = {"activo": False, "edad": 40, "rol": "admin"}
        assert validar_acceso(user) == "Usuario inactivo"

    def test_activo_none(self):
        user = {"activo": None, "edad": 40, "rol": "admin"}
        assert validar_acceso(user) == "Usuario inactivo"

    def test_activo_ausente(self):
        user = {"edad": 40, "rol": "admin"}
        assert validar_acceso(user) == "Usuario inactivo"

    def test_menor_de_edad(self):
        user = {"activo": True, "edad": 17, "rol": "admin"}
        assert validar_acceso(user) == "Menor de edad"

    def test_edad_cero(self):
        user = {"activo": True, "edad": 0, "rol": "admin"}
        assert validar_acceso(user) == "Menor de edad"

    def test_edad_limite_18(self):
        user = {"activo": True, "edad": 18, "rol": "cliente"}
        assert validar_acceso(user) == "Acceso limitado"

    def test_edad_ausente_se_trata_como_cero(self):
        user = {"activo": True, "rol": "admin"}
        assert validar_acceso(user) == "Menor de edad"

    def test_rol_vacio(self):
        user = {"activo": True, "edad": 20, "rol": ""}
        assert validar_acceso(user) == "Acceso limitado"

    def test_rol_none(self):
        user = {"activo": True, "edad": 20, "rol": None}
        assert validar_acceso(user) == "Acceso limitado"


# --- validar_email ---


class TestValidarEmail:
    def test_email_valido(self):
        assert validar_email("ana@empresa.com") is True

    def test_cadena_vacia(self):
        assert validar_email("") is False

    def test_sin_arroba(self):
        assert validar_email("ana.empresa.com") is False

    def test_sin_punto(self):
        assert validar_email("ana@empresa") is False

    def test_solo_arroba_y_punto(self):
        assert validar_email("@.") is True

    def test_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            validar_email(None)  # type: ignore[arg-type]


# --- calcular_total_con_descuento ---


class TestCalcularTotalConDescuento:
    def test_sin_descuento_por_debajo_de_100(self):
        productos = [{"precio": 40.0}, {"precio": 50.0}]
        assert calcular_total_con_descuento(productos) == 90.0

    def test_limite_exacto_100_sin_descuento(self):
        productos = [{"precio": 100.0}]
        assert calcular_total_con_descuento(productos) == 100.0

    def test_justo_por_encima_de_100_aplica_descuento(self):
        productos = [{"precio": 100.01}]
        assert calcular_total_con_descuento(productos) == pytest.approx(90.009)

    def test_lista_vacia(self):
        assert calcular_total_con_descuento([]) == 0

    def test_precio_cero(self):
        productos = [{"precio": 0}, {"precio": 0}]
        assert calcular_total_con_descuento(productos) == 0

    def test_producto_sin_precio_lanza_key_error(self):
        with pytest.raises(KeyError):
            calcular_total_con_descuento([{}])

    def test_precio_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            calcular_total_con_descuento([{"precio": None}])


# --- procesar_pedido ---


class TestProcesarPedido:
    def test_pedido_valido_sin_descuento(self):
        resumen = procesar_pedido(
            "Ana",
            [{"precio": 20.0}, {"precio": 30.0}],
            "ana@tienda.es",
        )
        assert resumen == (
            "Pedido de Ana: Total a pagar 50.0€ "
            "(Notificación enviada a ana@tienda.es)"
        )

    def test_pedido_valido_con_descuento(self):
        resumen = procesar_pedido(
            "Luis",
            [{"precio": 80.0}, {"precio": 40.0}],
            "luis@tienda.es",
        )
        assert "Total a pagar 108.0€" in resumen
        assert "Pedido de Luis" in resumen
        assert "luis@tienda.es" in resumen

    def test_email_invalido(self):
        assert (
            procesar_pedido("Ana", [{"precio": 10}], "correo-sin-formato")
            == "Email no válido"
        )

    def test_email_vacio(self):
        assert procesar_pedido("Ana", [{"precio": 10}], "") == "Email no válido"

    def test_email_none_lanza_type_error(self):
        with pytest.raises(TypeError):
            procesar_pedido("Ana", [{"precio": 10}], None)  # type: ignore[arg-type]

    def test_productos_vacios_email_valido(self):
        resumen = procesar_pedido("Ana", [], "ana@tienda.es")
        assert resumen == (
            "Pedido de Ana: Total a pagar 0€ "
            "(Notificación enviada a ana@tienda.es)"
        )

    def test_cliente_vacio(self):
        resumen = procesar_pedido("", [{"precio": 10}], "ana@tienda.es")
        assert resumen.startswith("Pedido de : Total a pagar 10")

    def test_producto_sin_precio_lanza_key_error(self):
        with pytest.raises(KeyError):
            procesar_pedido("Ana", [{}], "ana@tienda.es")
