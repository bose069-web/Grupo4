import pygame
import numpy as np
import time

pygame.init()
width, height = 400, 400
bg = 25, 25, 25
screen  = pygame.display.set_mode((height, width))
screen.fill(bg)

nxC, nyC = 60, 60

gameState = np.zeros((nxC,  nyC))

dimCW = width / nxC
dimCH = height / nyC


gameState[38, 20] = 1
gameState[39, 20] = 1
gameState[40, 20] = 1# Oscilador.
gameState[38, 20] = 1
gameState[39, 20] = 1
gameState[40, 20] = 1

gameState[10,5] = 1
gameState[12,5] = 1
gameState[11,6] = 1
gameState[12,6] = 1
gameState[11,7] = 1

gameState[5,10] = 1
gameState[5,12] = 1
gameState[6,11] = 1
gameState[6,12] = 1
gameState[7,11] = 1

gameState[18,15] = 1
gameState[17,16] = 1
gameState[17,15] = 1
gameState[18,16] = 1

gameState[30,20] = 1
gameState[31,20] = 1
gameState[32,20] = 1
gameState[32,19] = 1
gameState[33,19] = 1
gameState[34,19] = 1

pauseExect = False

while True:

    newGameState = np.copy(gameState)

    time.sleep(0.1)

    screen.fill(bg)

    ev = pygame.event.get()

    for event in ev:
        if event.type == pygame.KEYDOWN:
            pauseExect = not pauseExect

        mouseClick = pygame.mouse.get_pressed()

        if sum(mouseClick) > 0:
            posX, posY = pygame.mouse.get_pos()
            celX, celY = int(np.floor(posX / dimCW)), int(np.floor(posY / dimCH))
            newGameState[celX, celY] = 1

        for y in range(0, nxC):
            for x in range (0, nyC):
                if not pauseExect:
                    n_neigh =   gameState[(x - 1) % nxC, (y - 1)  % nyC] + \
                            gameState[(x)     % nxC, (y - 1)  % nyC] + \
                            gameState[(x + 1) % nxC, (y - 1)  % nyC] + \
                            gameState[(x - 1) % nxC, (y)      % nyC] + \
                            gameState[(x + 1) % nxC, (y)      % nyC] + \
                            gameState[(x - 1) % nxC, (y + 1)  % nyC] + \
                            gameState[(x)     % nxC, (y + 1)  % nyC] + \
                            gameState[(x + 1) % nxC, (y + 1)  % nyC]
                    if gameState[x, y] == 0 and n_neigh == 3:
                        newGameState[x, y] = 1

                    elif gameState[x, y] == 1 and (n_neigh < 2 or n_neigh > 3):
                        newGameState[x, y] = 0

                poly = [((x)   * dimCW, y * dimCH),
                    ((x+1) * dimCW, y * dimCH),
                    ((x+1) * dimCW, (y+1) * dimCH),
                    ((x)   * dimCW, (y+1) * dimCH)]

                if newGameState[x, y] == 0:
                    pygame.draw.polygon(screen, (40, 40, 40), poly, 1)

                else:
                    pygame.draw.polygon(screen, (200, 100, 100), poly, 0)

        gameState = np.copy(newGameState)

        pygame.display.flip()