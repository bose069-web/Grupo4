"""Pruebas de las reglas y del tablero inicial (sin abrir la ventana)."""

import unittest

import numpy as np

from codigo_cursor import (
    CELULAS_INICIALES,
    aplicar_regla_en_celda,
    contar_vecinos,
    crear_tablero_inicial,
    siguiente_generacion,
)


class TableroInicialTests(unittest.TestCase):
    def test_tiene_las_mismas_celulas_vivas_que_el_original(self):
        tablero = crear_tablero_inicial()
        esperadas = set(CELULAS_INICIALES)

        self.assertEqual(int(tablero.sum()), len(esperadas))
        for columna, fila in esperadas:
            self.assertEqual(tablero[columna, fila], 1)

    def test_el_resto_del_tablero_esta_muerto(self):
        tablero = crear_tablero_inicial()
        for columna, fila in CELULAS_INICIALES:
            tablero[columna, fila] = 0
        self.assertEqual(int(tablero.sum()), 0)


class VecinosTests(unittest.TestCase):
    def test_cuenta_las_ocho_celulas_alrededor(self):
        tablero = np.zeros((5, 5))
        tablero[1:4, 1:4] = 1  # bloque 3x3
        # El centro tiene 8 vecinos vivos.
        self.assertEqual(contar_vecinos(tablero, 2, 2), 8)

    def test_los_bordes_se_conectan_como_un_toro(self):
        tablero = np.zeros((3, 3))
        tablero[0, 0] = 1
        tablero[0, 2] = 1
        tablero[2, 0] = 1
        # Esquina (2, 2): envuelve y ve las tres células.
        self.assertEqual(contar_vecinos(tablero, 2, 2), 3)


class ReglasDeConwayTests(unittest.TestCase):
    def test_nace_con_exactamente_tres_vecinos(self):
        tablero = np.zeros((3, 3))
        tablero[0, 1] = 1
        tablero[1, 0] = 1
        tablero[1, 2] = 1
        siguiente = siguiente_generacion(tablero)
        self.assertEqual(siguiente[1, 1], 1)

    def test_muere_con_menos_de_dos_vecinos(self):
        tablero = np.zeros((3, 3))
        tablero[1, 1] = 1
        siguiente = siguiente_generacion(tablero)
        self.assertEqual(siguiente[1, 1], 0)

    def test_sobrevive_con_dos_o_tres_vecinos(self):
        tablero = np.zeros((3, 3))
        tablero[1, 1] = 1
        tablero[0, 1] = 1
        tablero[1, 0] = 1
        siguiente = siguiente_generacion(tablero)
        self.assertEqual(siguiente[1, 1], 1)

    def test_muere_con_mas_de_tres_vecinos(self):
        tablero = np.ones((3, 3))
        siguiente = siguiente_generacion(tablero)
        self.assertEqual(siguiente[1, 1], 0)

    def test_el_blinker_gira_de_horizontal_a_vertical(self):
        tablero = np.zeros((5, 5))
        tablero[1:4, 2] = 1  # tres células en vertical (eje columna)

        siguiente = siguiente_generacion(tablero)

        esperado = np.zeros((5, 5))
        esperado[2, 1:4] = 1
        np.testing.assert_array_equal(siguiente, esperado)

    def test_el_bloque_2x2_no_cambia(self):
        tablero = np.zeros((5, 5))
        tablero[1:3, 1:3] = 1
        siguiente = siguiente_generacion(tablero)
        np.testing.assert_array_equal(siguiente, tablero)

    def test_el_clic_se_conserva_si_la_regla_no_reescribe_la_celda(self):
        # Célula muerta, 0 vecinos: la regla no nace ni muere; el 1 del clic queda.
        tablero_actual = np.zeros((3, 3))
        tablero_siguiente = np.copy(tablero_actual)
        tablero_siguiente[1, 1] = 1

        aplicar_regla_en_celda(tablero_actual, tablero_siguiente, 1, 1)

        self.assertEqual(tablero_siguiente[1, 1], 1)


if __name__ == "__main__":
    unittest.main()
