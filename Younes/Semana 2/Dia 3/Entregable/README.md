# Reto 1: Voz a Texto

Web React responsive con un único botón de grabación. Web Speech API muestra la transcripción en vivo y, al detener, el mismo audio se envía al backend Python para transcribirlo por lotes con Gemini.

## Requisitos

- Node.js 20.19+ o 22.12+ y npm.
- Python 3.10+ con `google-genai` instalado.
- Chrome o Edge para Web Speech API; Safari puede usar `webkitSpeechRecognition` si está disponible.

## Configurar Gemini

Pega una clave nueva de Google AI Studio en `GEMINI_API_KEY` dentro de `reto1.py`. La clave permanece en Python y no se expone al navegador. Si el SDK falta:

```powershell
python -m pip install -U google-genai
```

## Ejecutar en desarrollo

En una terminal, desde `Dia 3/Reto 1`:

```powershell
python .\reto1.py
```

En otra terminal:

```powershell
cd .\frontend
npm install
npm run dev
```

Abre la URL de Vite, normalmente `http://localhost:5173`.

## Micrófono en móvil

La interfaz se adapta a pantallas pequeñas. Los navegadores requieren un contexto seguro para el micrófono: `localhost` funciona en el ordenador, pero al abrir la web desde otro dispositivo hay que publicarla o servirla por HTTPS. Web Speech API depende del navegador, idioma y servicio de reconocimiento del dispositivo; Gemini procesa el audio completo después de detener la grabación.

## Producción

```powershell
cd .\frontend
npm run build
```

Publica el contenido de `frontend/dist` detrás de HTTPS y configura el servidor para que `/transcribe` llegue al backend Python. El backend local acepta audios WAV de hasta 25 MB; no publiques tu puerto ni la clave de Gemini directamente.