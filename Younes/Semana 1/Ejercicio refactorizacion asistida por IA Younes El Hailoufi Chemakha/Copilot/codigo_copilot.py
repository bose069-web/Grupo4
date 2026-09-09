import time

import numpy as np

ANCHO = 400
ALTO = 400
COLOR_FONDO = (25, 25, 25)
FILAS = 60
COLUMNAS = 60


def crear_estado_inicial():
    """Crea la misma configuracion inicial que usaba el programa original."""
    estado = np.zeros((FILAS, COLUMNAS))
    celulas_vivas = [
        (38, 20), (39, 20), (40, 20),
        (10, 5), (12, 5), (11, 6), (12, 6), (11, 7),
        (5, 10), (5, 12), (6, 11), (6, 12), (7, 11),
        (18, 15), (17, 16), (17, 15), (18, 16),
        (30, 20), (31, 20), (32, 20), (32, 19), (33, 19), (34, 19),
    ]
    for fila, columna in celulas_vivas:
        estado[fila, columna] = 1
    return estado


def contar_vecinos(estado, fila, columna):
    """Cuenta vecinos conectando los bordes de la cuadricula."""
    filas, columnas = estado.shape
    desplazamientos = (-1, 0, 1)
    return sum(
        estado[(fila + desplazamiento_fila) % filas,
               (columna + desplazamiento_columna) % columnas]
        for desplazamiento_fila in desplazamientos
        for desplazamiento_columna in desplazamientos
        if (desplazamiento_fila, desplazamiento_columna) != (0, 0)
    )


def avanzar_estado(estado):
    """Aplica una generacion de las reglas del Juego de la Vida."""
    siguiente_estado = np.copy(estado)
    filas, columnas = estado.shape

    for fila in range(filas):
        for columna in range(columnas):
            vecinos = contar_vecinos(estado, fila, columna)
            celula_viva = estado[fila, columna] == 1
            debe_nacer = not celula_viva and vecinos == 3
            debe_morir = celula_viva and vecinos not in (2, 3)

            if debe_nacer:
                siguiente_estado[fila, columna] = 1
            elif debe_morir:
                siguiente_estado[fila, columna] = 0

    return siguiente_estado


def dibujar_estado(pantalla, estado, ancho_celula, alto_celula, pygame):
    """Dibuja las celdas con los mismos colores y dimensiones."""
    filas, columnas = estado.shape
    for fila in range(filas):
        for columna in range(columnas):
            poligono = [
                (fila * ancho_celula, columna * alto_celula),
                ((fila + 1) * ancho_celula, columna * alto_celula),
                ((fila + 1) * ancho_celula, (columna + 1) * alto_celula),
                (fila * ancho_celula, (columna + 1) * alto_celula),
            ]
            esta_viva = estado[fila, columna] == 1
            color = (200, 100, 100) if esta_viva else (40, 40, 40)
            grosor = 0 if esta_viva else 1
            pygame.draw.polygon(pantalla, color, poligono, grosor)


def ejecutar():
    """Inicia la ventana y el ciclo de interaccion del juego."""
    import pygame

    pygame.init()
    pantalla = pygame.display.set_mode((ALTO, ANCHO))
    ancho_celula = ANCHO / FILAS
    alto_celula = ALTO / COLUMNAS
    estado = crear_estado_inicial()
    pausado = False

    while True:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                return
            if evento.type == pygame.KEYDOWN:
                pausado = not pausado

            if sum(pygame.mouse.get_pressed()) > 0:
                posicion_x, posicion_y = pygame.mouse.get_pos()
                fila = int(np.floor(posicion_x / ancho_celula))
                columna = int(np.floor(posicion_y / alto_celula))
                estado[fila, columna] = 1

        if not pausado:
            estado = avanzar_estado(estado)

        pantalla.fill(COLOR_FONDO)
        dibujar_estado(pantalla, estado, ancho_celula, alto_celula, pygame)
        pygame.display.flip()
        time.sleep(0.1)


if __name__ == "__main__":
    ejecutar()