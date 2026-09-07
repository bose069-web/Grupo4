import pytest

from legacy import (
    calc,
    calcular_total_con_descuento,
    procesar_pedido,
    validar_acceso,
    validar_email,
)


class TestCalc:
    def test_calcula_total_con_descuento(self):
        assert calc(100, 2, 0.15) == pytest.approx(170)

    @pytest.mark.parametrize(
        ("precio_unitario", "cantidad", "porcentaje_descuento", "esperado"),
        [
            (0, 5, 0.2, 0),
            (50, 0, 0.2, 0),
            (50, 2, 0, 100),
            (50, 2, 1, 0),
        ],
    )
    def test_valores_limite(self, precio_unitario, cantidad, porcentaje_descuento, esperado):
        assert calc(precio_unitario, cantidad, porcentaje_descuento) == pytest.approx(esperado)

    @pytest.mark.parametrize(
        "argumentos",
        [(None, 1, 0.1), (10, None, 0.1), (10, 1, None)],
    )
    def test_rechaza_argumentos_none(self, argumentos):
        with pytest.raises(TypeError):
            calc(*argumentos)


class TestValidarAcceso:
    @pytest.mark.parametrize(
        ("usuario", "esperado"),
        [
            (None, "Usuario no existe"),
            ({}, "Usuario inactivo"),
            ({"activo": False, "edad": 30}, "Usuario inactivo"),
            ({"activo": True, "edad": 17}, "Menor de edad"),
            ({"activo": True, "edad": 18, "rol": "admin"}, "Acceso total"),
            ({"activo": True, "edad": 18, "rol": "user"}, "Acceso limitado"),
        ],
    )
    def test_devuelve_resultado_segun_estado(self, usuario, esperado):
        assert validar_acceso(usuario) == esperado

    def test_usuario_activo_sin_edad_es_menor(self):
        assert validar_acceso({"activo": True}) == "Menor de edad"

    @pytest.mark.parametrize("usuario", [[], "usuario", 0])
    def test_rechaza_usuario_que_no_es_diccionario(self, usuario):
        with pytest.raises(AttributeError):
            validar_acceso(usuario)


class TestValidarEmail:
    @pytest.mark.parametrize("email", ["persona@example.com", "a@b.c"])
    def test_acepta_email_con_arroba_y_punto(self, email):
        assert validar_email(email) is True

    @pytest.mark.parametrize("email", ["", "persona.example.com", "persona@example"])
    def test_rechaza_email_invalido_o_vacio(self, email):
        assert validar_email(email) is False

    def test_rechaza_none(self):
        with pytest.raises(TypeError):
            validar_email(None)


class TestCalcularTotalConDescuento:
    def test_suma_productos_sin_descuento(self):
        productos = [{"precio": 25}, {"precio": 30}]
        assert calcular_total_con_descuento(productos) == 55

    @pytest.mark.parametrize(
        ("productos", "esperado"),
        [
            ([], 0),
            ([{"precio": 100}], 100),
            ([{"precio": 100.01}], 90.009),
        ],
    )
    def test_cubre_vacios_y_limite_de_descuento(self, productos, esperado):
        assert calcular_total_con_descuento(productos) == pytest.approx(esperado)

    def test_falla_si_falta_el_precio(self):
        with pytest.raises(KeyError):
            calcular_total_con_descuento([{"nombre": "producto"}])

    def test_falla_con_none(self):
        with pytest.raises(TypeError):
            calcular_total_con_descuento(None)


class TestProcesarPedido:
    def test_procesa_pedido_valido(self):
        resultado = procesar_pedido(
            "Ana", [{"precio": 60}, {"precio": 50}], "ana@example.com"
        )
        assert resultado == (
            "Pedido de Ana: Total a pagar 99.0€ "
            "(Notificación enviada a ana@example.com)"
        )

    @pytest.mark.parametrize(
        ("productos", "esperado"),
        [
            ([], "Pedido de Ana: Total a pagar 0€ (Notificación enviada a ana@example.com)"),
            (
                [{"precio": 100}],
                "Pedido de Ana: Total a pagar 100€ (Notificación enviada a ana@example.com)",
            ),
        ],
    )
    def test_procesa_vacios_y_umbral_sin_descuento(self, productos, esperado):
        assert procesar_pedido("Ana", productos, "ana@example.com") == esperado

    @pytest.mark.parametrize("email", ["", "ana.example.com", "ana@example"])
    def test_rechaza_email_invalido_antes_de_calcular(self, email):
        assert procesar_pedido("Ana", [{"precio": 50}], email) == "Email no válido"

    def test_email_invalido_no_falla_con_productos_invalidos(self):
        assert procesar_pedido("Ana", None, "sin-email") == "Email no válido"

    def test_propaga_error_de_producto_con_email_valido(self):
        with pytest.raises(KeyError):
            procesar_pedido("Ana", [{"nombre": "producto"}], "ana@example.com")

    def test_propaga_none_en_email(self):
        with pytest.raises(TypeError):
            procesar_pedido("Ana", [], None)
