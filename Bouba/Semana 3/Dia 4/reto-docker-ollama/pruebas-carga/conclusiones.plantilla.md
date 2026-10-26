# Análisis de cuellos de botella

## ¿Dónde falla primero el modelo local?
- Con cuántos usuarios empieza a fallar y qué métrica lo muestra (TTFT, errores, timeouts).
- Qué recurso se satura (cola, CPU, RAM). Usad las gráficas de evolución y la sección 4 del informe.

## ¿Y el remoto?
- Lo mismo para el backend remoto.
- Qué parte de su latencia es red y cuál es cálculo.

# Optimizaciones implementadas
- Optimización 1: qué hace y por qué la elegimos.
- Optimización 2: qué hace y por qué la elegimos.
- (Opcional) Optimización 3.

# Resultados antes / después
- Mejora más importante, con números (p. ej. «p95 con 10 usuarios: 95 s → 28 s»).
- Qué ha empeorado o qué coste tiene (respuestas más cortas, calidad del modelo cuantizado, respuestas iguales por la caché).

# Local vs remoto
- Cuándo compensa usar cada uno (coste, latencia, privacidad, capacidad).

# Limitaciones de la prueba
- Por ejemplo: «el remoto era el PC de un compañero, no la VM de Azure», «solo 2 preguntas por usuario», «el portátil tenía otros programas abiertos».
