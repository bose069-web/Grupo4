# Día 7 | Servicios de Voz e Interfaces

Prototipo DAW de Speech-to-Text en español. La interfaz usa la **Web Speech API** para mostrar la transcripción en tiempo real y `MediaRecorder` para comprobar que existe una captura de audio durante cada prueba.

## Ejecutar

La API de reconocimiento necesita un contexto seguro. `localhost` es válido:

```powershell
cd dia7-voz
python -m http.server 8000
```

Abre http://localhost:8000 en Google Chrome o Microsoft Edge, permite el micrófono y completa las pruebas 01, 02 y 03. El botón **descargar informe** exporta las transcripciones y las observaciones en un `.txt`.

## Entregable y verificación

1. Selecciona la prueba 01 y di la frase propuesta (puedes sustituir los puntos por tu nombre).
2. Repite el proceso con las pruebas 02 y 03.
3. Revisa cada transcripción, anota diferencias en la sección de comparativa y descarga el informe.
4. Para contrastar Gemini, sube cada audio `.wav` o `.mp3` a Google AI Studio y solicita: `Transcribe este audio exactamente en español. No resumas ni traduzcas.` Pega el resultado de Gemini junto al resultado del navegador en tus notas.

## Comparación

| Web Speech API | Gemini con audio |
| --- | --- |
| Tiempo real y respuesta inmediata | Procesamiento por lotes |
| Gratuita y sin API key | Requiere API key y conexión |
| Limitada al navegador y su motor | Mejor comprensión contextual |
| Sensible al ruido, acento y conexión | Admite ficheros WAV y MP3 |

No se incluye una API key en el frontend. Eso evita exponer credenciales; una integración de Gemini para producción debe pasar por un endpoint de servidor.
