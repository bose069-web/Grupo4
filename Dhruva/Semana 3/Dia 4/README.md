# Día 4 - Pruebas de carga y optimización

Contenido listo para entregar:

- `load_test.py`: pruebas concurrentes con asyncio y aiohttp.
- `graficar_resultados.py`: genera las gráficas comparativas.
- `informe-carga.md`: metodología, optimizaciones y resultados.
- `resultados/`: JSON, CSV y gráficas de la ejecución local.
- `api/` y `docker-compose.yml`: API y configuración Docker.
- `.env.example`: plantilla segura de configuración.

## Ejecutar

```bash
python3 -m pip install -r requirements-load.txt
python3 load_test.py --backend local --url http://127.0.0.1:8084/chat --protocol proxy --output resultados/local.json
python3 graficar_resultados.py resultados/local.json
```

Para Azure, usa el comando documentado en `informe-carga.md` con la URL real de la VM.
No subas claves API ni un archivo `.env` con secretos.
