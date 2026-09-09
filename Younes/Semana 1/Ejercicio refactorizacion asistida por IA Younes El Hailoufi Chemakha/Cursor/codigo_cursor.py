"""
Juego de la Vida de Conway.

Misma ventana, colores, patrones iniciales y reglas que el programa original.
Cualquier tecla pausa o reanuda; el clic del ratón enciende una célula.
"""

import time

import numpy as np
import pygame

# --- Apariencia (igual que el original) ---
ANCHO_VENTANA = 400
ALTO_VENTANA = 400
COLOR_FONDO = (25, 25, 25)
COLOR_CELULA_MUERTA = (40, 40, 40)
COLOR_CELULA_VIVA = (200, 100, 100)
SEGUNDOS_ENTRE_FOTOGRAMAS = 0.1

# Tablero toroidal: el borde derecho conecta con el izquierdo (y arriba con abajo).
NUM_COLUMNAS = 60
NUM_FILAS = 60

# Células vivas al arrancar: (columna, fila), como en el original.
# El oscilador se escribía dos veces; aquí basta una.
CELULAS_INICIALES = (
    (38, 20), (39, 20), (40, 20),  # oscilador (blinker)
    (10, 5), (12, 5), (11, 6), (12, 6), (11, 7),
    (5, 10), (5, 12), (6, 11), (6, 12), (7, 11),
    (18, 15), (17, 16), (17, 15), (18, 16),  # bloque 2x2
    (30, 20), (31, 20), (32, 20), (32, 19), (33, 19), (34, 19),
)


def crear_tablero_inicial():
    """Tablero 60x60 con las mismas células vivas de partida."""
    tablero = np.zeros((NUM_COLUMNAS, NUM_FILAS))
    for columna, fila in CELULAS_INICIALES:
        tablero[columna, fila] = 1
    return tablero


def contar_vecinos(tablero, columna, fila):
    """Suma las 8 células alrededor, envolviendo los bordes."""
    columnas, filas = tablero.shape
    total = 0
    for delta_columna in (-1, 0, 1):
        for delta_fila in (-1, 0, 1):
            if delta_columna == 0 and delta_fila == 0:
                continue
            columna_vecina = (columna + delta_columna) % columnas
            fila_vecina = (fila + delta_fila) % filas
            total += tablero[columna_vecina, fila_vecina]
    return total


def aplicar_regla_en_celda(tablero_actual, tablero_siguiente, columna, fila):
    """
    Conway: nace con 3 vecinos; vive con 2 o 3; muere en el resto.

    Solo escribe en tablero_siguiente si la regla cambia la célula.
    Así un clic del ratón (poner a 1) se conserva si la regla no aplica.
    """
    vecinos = contar_vecinos(tablero_actual, columna, fila)
    esta_viva = tablero_actual[columna, fila] == 1
    nace = not esta_viva and vecinos == 3
    muere = esta_viva and vecinos not in (2, 3)

    if nace:
        tablero_siguiente[columna, fila] = 1
    elif muere:
        tablero_siguiente[columna, fila] = 0


def siguiente_generacion(tablero):
    """Una generación completa, sin pintura del ratón."""
    tablero_siguiente = np.copy(tablero)
    columnas, filas = tablero.shape
    for columna in range(columnas):
        for fila in range(filas):
            aplicar_regla_en_celda(tablero, tablero_siguiente, columna, fila)
    return tablero_siguiente


def rectangulo_celda(columna, fila, ancho_celda, alto_celda):
    """Cuatro esquinas de la celda, en el mismo orden que el original."""
    x0 = columna * ancho_celda
    y0 = fila * alto_celda
    x1 = (columna + 1) * ancho_celda
    y1 = (fila + 1) * alto_celda
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def dibujar_tablero(pantalla, tablero, ancho_celda, alto_celda):
    """Célula viva: relleno rosa. Muerta: solo borde gris."""
    columnas, filas = tablero.shape
    for columna in range(columnas):
        for fila in range(filas):
            poligono = rectangulo_celda(columna, fila, ancho_celda, alto_celda)
            if tablero[columna, fila] == 0:
                pygame.draw.polygon(pantalla, COLOR_CELULA_MUERTA, poligono, 1)
            else:
                pygame.draw.polygon(pantalla, COLOR_CELULA_VIVA, poligono, 0)


def celda_bajo_raton(ancho_celda, alto_celda):
    """Convierte píxeles del ratón en índices de columna y fila."""
    posicion_x, posicion_y = pygame.mouse.get_pos()
    columna = int(np.floor(posicion_x / ancho_celda))
    fila = int(np.floor(posicion_y / alto_celda))
    return columna, fila


def ejecutar():
    pygame.init()
    # El original usaba set_mode((alto, ancho)); ambos valen 400.
    pantalla = pygame.display.set_mode((ALTO_VENTANA, ANCHO_VENTANA))
    pantalla.fill(COLOR_FONDO)

    ancho_celda = ANCHO_VENTANA / NUM_COLUMNAS
    alto_celda = ALTO_VENTANA / NUM_FILAS
    tablero = crear_tablero_inicial()
    pausado = False

    while True:
        # Copia al inicio de cada vuelta, como el original (no en cada evento).
        tablero_siguiente = np.copy(tablero)
        time.sleep(SEGUNDOS_ENTRE_FOTOGRAMAS)
        pantalla.fill(COLOR_FONDO)

        eventos = pygame.event.get()
        # El original actualiza y dibuja *dentro* del bucle de eventos:
        # sin eventos no hay generación ni flip; con varios, avanza varias veces.
        for evento in eventos:
            if evento.type == pygame.KEYDOWN:
                pausado = not pausado

            if sum(pygame.mouse.get_pressed()) > 0:
                columna, fila = celda_bajo_raton(ancho_celda, alto_celda)
                tablero_siguiente[columna, fila] = 1

            if not pausado:
                columnas, filas = tablero.shape
                for columna in range(columnas):
                    for fila in range(filas):
                        aplicar_regla_en_celda(
                            tablero, tablero_siguiente, columna, fila
                        )

            dibujar_tablero(pantalla, tablero_siguiente, ancho_celda, alto_celda)
            tablero = np.copy(tablero_siguiente)
            pygame.display.flip()


if __name__ == "__main__":
    ejecutar()
