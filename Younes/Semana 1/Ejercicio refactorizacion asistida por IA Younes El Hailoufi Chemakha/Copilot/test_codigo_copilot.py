import unittest

import numpy as np

from codigo_copilot import avanzar_estado, contar_vecinos, crear_estado_inicial


class JuegoDeLaVidaTests(unittest.TestCase):
    def test_estado_inicial_contiene_las_celulas_originales(self):
        estado = crear_estado_inicial()

        self.assertEqual(int(estado.sum()), 23)
        self.assertEqual(estado[38, 20], 1)
        self.assertEqual(estado[40, 20], 1)

    def test_contador_de_vecinos_envuelve_los_bordes(self):
        estado = np.zeros((3, 3))
        estado[0, 0] = 1
        estado[0, 2] = 1
        estado[2, 0] = 1

        self.assertEqual(contar_vecinos(estado, 2, 2), 3)

    def test_un_blinker_cambia_de_horizontal_a_vertical(self):
        estado = np.zeros((5, 5))
        estado[2, 1:4] = 1

        siguiente_estado = avanzar_estado(estado)

        esperado = np.zeros((5, 5))
        esperado[1:4, 2] = 1
        np.testing.assert_array_equal(siguiente_estado, esperado)


if __name__ == "__main__":
    unittest.main()