# Reto del Día — Instalación y Despliegue Local de Ollama + Gemma 4

Guía reproducible de lo que se hizo para dejar `gemma4:e4b` corriendo en local,
verificado por CLI y por API REST.

**Fecha:** 2026-10-06
**Equipo de ejecución:** `ITMES5CD1471SL9` — HP ProBook 440 G8, `ibl\boubacar.seck.ext`

---

## 0. Aviso importante sobre el equipo

Este reto se ejecutó en el **portátil corporativo**, no en el equipo personal.
`AGENTS.md` recomienda expresamente no instalar nada ahí por Ivanti Application
Control y Cortex XDR.

Lo único que se escribió fue `C:\Users\<usuario>\.ollama\models`. No se instaló
software, no se tocó el venv de Python ni el registro. Ivanti no bloqueó nada.
Aun así: **los modelos hay que volver a descargarlos en el equipo personal.**
Las rutas de `OLLAMA_MODELS` no son portables y este `pull` no se transfiere.

---

## 1. Fase 0 — Inspección (solo lectura)

Todo esto es `[LECTURA]`. Sirve para decidir si el modelo cabe antes de gastar
6.6 GB de descarga.

```powershell
# SO y hardware
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, OSArchitecture
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object @{n='RAM_GB';e={[math]::Round($_.TotalPhysicalMemory/1GB,1)}}

# GPU (crítico para decidir tamaño de modelo)
Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM
nvidia-smi --query-gpu=name,memory.total --format=csv 2>$null

# Python disponible
py -0p

# Espacio en disco
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}

# ¿Ollama ya instalado?
ollama --version 2>$null
ollama list 2>$null
```

Resultado en este equipo:

| Dato | Valor | Lectura |
|---|---|---|
| SO | Windows 11 Enterprise 64-bit | OK |
| CPU | i5-1135G7, 4 núcleos / 8 hilos | lento pero suficiente |
| RAM | 15.7 GB | E4B (7.5B params) cabe |
| GPU | Intel Iris Xe, **sin NVIDIA** | inferencia **solo por CPU** |
| Disco C: | 350.5 GB libres | sobra |
| Python | solo 3.14.7 | no hay 3.12 |
| Ollama | **v0.35.1 ya instalado**, lista vacía | paso 1 ya cumplido |

**Decisión:** sin GPU NVIDIA se espera 3-10 tok/s en CPU. Con 15.7 GB de RAM el
E4B es viable, así que se prueban primero `e4b` y `e2b` como plan B.

---

## 2. Confirmar que el modelo existe antes de descargar

`gemma4:e4b` no es inventado, pero conviene comprobarlo en la librería oficial
en vez de asumirlo:

```powershell
Invoke-RestMethod -Uri "https://ollama.com/search?q=gemma"
```

Tag oficial confirmado: **6.6 GB, contexto 128K, Text + Image + Audio.**

Nota: `registry.ollama.ai/v2/library/gemma/tags/list` devuelve **404**. La vía
que funciona es la web, no el registro OCI v2.

---

## 3. Arrancar el motor

```powershell
ollama serve
```

En Windows, si Ollama está instalado, `serve` ya corre como proceso en segundo
plano. Se comprueba sin abrir nada más:

```powershell
Invoke-RestMethod -Uri "http://localhost:11434/api/version"
# -> 0.35.1

Get-CimInstance Win32_Process -Filter "Name='ollama.exe'" | Select-Object ProcessId, CommandLine
# PID 4016 -> ollama.exe serve
```

Si `/api/version` no responde, `ollama serve` no está corriendo. Eso es todo.

---

## 4. Descargar el modelo

`[RED]` `[LENTO]` — 6.6 GB, entre 9 y 10 minutos a 12-17 MB/s.

```powershell
ollama pull gemma4:e4b
```

### Truco: ejecutar el pull en segundo plano

Un `pull` en primer plano mata la barra de progreso con el timeout de la terminal
y además escupe caracteres ANSI que revientan el log. Mejor en background:

```powershell
$err = "$env:TEMP\pull_e4b.err"
$p = Start-Process -FilePath "C:\Users\<usuario>\AppData\Local\Programs\Ollama\ollama.exe" `
  -ArgumentList "pull","gemma4:e4b" `
  -RedirectStandardError $err -NoNewWindow -PassThru
"PID=$($p.Id)"
```

Se sondea el progreso leyendo el log y parseando solo el último porcentaje:

```powershell
$raw = (Get-Content $err -Tail 400) -join ' '
$m = [regex]::Matches($raw, '(\d+)%.*?([\d\.]+) GB/([\d\.]+) GB\s+([\d\.]+) MB/s')
if ($m.Count) { "progreso: $($m[$m.Count-1].Groups[1].Value)%" }
[bool](Get-Process -Id $p.Id -ErrorAction SilentlyContinue)   # ¿sigue vivo?
```

Dos errores que cuestan tiempo aquí:

- `Get-Content -Raw -Tail N` **no es válido** en PowerShell 5.1. Son excluyentes.
  Hay que leer el array y unirlo: `(Get-Content $f -Tail 400) -join ' '`.

### Confirmar el resultado

```powershell
ollama list
# NAME          ID              SIZE      MODIFIED
# gemma4:e4b    dc35e8d9c606    6.6 GB    3 minutes ago
```

Detalle técnico del modelo instalado:

```
format=gguf   family=gemma4   parameter_size=7.5B
quantization_level=Q4_K_M     context_length=131072
embedding_length=2560         size=6583656505 bytes
```

---

## 5. Verificación real (Fase 3)

**Un `ollama list` con el modelo presente NO es un éxito.** Sin texto generado no
se sabe si arranca. Estas dos pruebas son las que cuentan.

### 5.1 CLI

```powershell
ollama run gemma4:e4b "Responde en una sola frase: que es un vector de contexto?"
```

53 s la primera vez (incluye cargar 6.6 GB en RAM), correcto a partir de ahí.

Respuesta obtenida:

> Un vector de contexto es una representación numérica (un *embedding*) que
> codifica el significado semántico de una pieza de información o un fragmento
> de texto, permitiendo a los modelos de IA procesarlo y relacionarlo
> matemáticamente.

Para ver rates en la CLI hay que redirigir a fichero: el spinner ANSI
inutiliza la consola cuando se captura la salida.

### 5.2 API REST — `/api/chat`

```powershell
$body = @{
  model  = "gemma4:e4b"
  stream = $false
  think  = $false
  messages = @(@{ role = "user"; content = "Responde en una sola frase: que es un vector de contexto?" })
  options  = @{ temperature = 1.0; top_p = 0.95; top_k = 64; num_predict = 300 }
} | ConvertTo-Json -Depth 6

$r = Invoke-RestMethod -Uri "http://localhost:11434/api/chat" `
  -Method Post -ContentType "application/json" -Body $body -TimeoutSec 600

"done: $($r.done_reason)"
"tok/s: $([math]::Round($r.eval_count / ($r.eval_duration/1e9),2))"
$r.message.content
```

```
done: stop
tok/s: 9.49
Un vector de contexto es una representación numérica densa y continua de un
fragmento de texto o datos que captura su significado semántico en relación con
otros textos.
```

### 5.3 API REST — `/api/generate`

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$g = @{
  model = "gemma4:e4b"; stream = $false; think = $false
  prompt  = "Dime el nombre de la capital de Senegal y del Brasil, separados por una coma."
  options = @{ temperature = 1.0; top_p = 0.95; top_k = 64; num_predict = 120 }
} | ConvertTo-Json -Depth 6

$r = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($g)) -TimeoutSec 300
$r.response
```

```
Dakar, Brasília
```

Los acentos se conservan. La consola de PowerShell 5.1 muestra `?` si no se
fuerza UTF-8 — es un problema de la consola, **no** de la respuesta del modelo.

---

## 6. Trampas encontradas (leer antes de repetir esto)

### 6.1 `gemma4` piensa por defecto y se come los tokens

La primera llamada REST devolvió **texto vacío con `done_reason: length`**:

```
done_reason: length
eval_count: 200      <- todos en razonamiento
message.content: ""  <- vacío
```

No era un fallo del modelo ni de la RAM. Ollama 0.35.1 activa el bloque de
*thinking* por defecto en `gemma4`, y con `num_predict = 200` el modelo agotó el
presupuesto en el razonamiento interno sin llegar a la respuesta final.

Dos salidas:
- enviar **`"think": $false`** en el cuerpo, o
- subir `num_predict` y leer `message.thinking` aparte de `message.content`.

Con `think: false` el mismo prompt baja de 25.9 s a 6.2 s y responde limpio.

### 6.2 Parámetros de muestreo recomendados por Google

No son opcionales si se quiere el comportamiento de referencia:

```
temperature = 1.0
top_p       = 0.95
top_k       = 64
```

### 6.3 Console encoding

Acentos y `ñ` salen como `?` sin `[Console]::OutputEncoding = [UTF8]`. No tocar
el modelo: es la consola.

### 6.4 PowerShell 5.1

- `Get-Content -Raw` y `-Tail` no se pueden combinar.
- Los `\e` de escape ANSI no existen en 5.1 (son de PS 6+).
- `Start-Process` sobrevive al cierre del shell padre, pero el log hay que
  filtrarlo a mano.

### 6.5 rates de CPU

`ollama ps` durante la inferencia:

```
NAME          ID              SIZE    PROCESSOR    CONTEXT    UNTIL
gemma4:e4b    dc35e8d9c606    1.8 GB  100% CPU     4096       4 minutes from now
```

`PROCESSOR: 100% CPU` confirma que no hay aceleración por GPU. El GGUF se mapea
en memoria desde disco, así que el 1.8 GB de RSS es engañoso: el page cache de
Windows es lo que sostiene el ritmo.

---

## 7. Rendimiento medido

| Prueba | Tokens | Ritmo | Notas |
|---|---|---|---|
| CLI (1ª vez) | — | 53 s total | incluye carga del modelo |
| `/api/chat` con thinking | 200 | — | `length`, sin respuesta útil |
| `/api/chat` `think:false` | 33 | **9.49 tok/s** | `done: stop` |
| `/api/generate` | 5 | **9.42 tok/s** | correcto |

Sin GPU NVIDIA, ~9.4 tok/s es el techo realista en esta máquina. Aproximadamente
2x más rápido que en tiempo real, suficiente para uso interactivo.

**RAM con el modelo cargado:** 2.3 GB libres de 15.7. Funciona, pero sin abrir
mucho más cosas a la vez.

![Rendimiento medido de gemma4:e4b en CPU](Daily-page/images/rendimiento.png)

---

## 8. Conectar la web `Daily-page` a este modelo

![Arquitectura: del navegador a Ollama local](Daily-page/images/arquitectura.png)

La app del cuaderno diario que hice con un compañero (`yoel413/Daily-page`)
tenía la función `polish()` atada a Google Gemini. Se añadió Ollama como
**opción alternativa**, sin quitar Gemini: quien no tenga Ollama en su máquina
sigue funcionando igual.

### 8.1 Ficheros tocados

| Fichero | Cambio |
|---|---|
| `Daily-page/index.html` | selector de proveedor en el diálogo + `requestOllama()` |
| `Daily-page/Daily_automatica/index.html` | idéntico (los dos eran copia exacta) |

El diálogo de "Ajustes de IA" ahora ofrece:

- `Google Gemini (clave de AI Studio)` — como antes
- `Ollama local (este equipo, sin clave)` — lo nuevo

Tres claves nuevas en `localStorage`: `cuaderno-daily-provider`,
`cuaderno-daily-ollama-url`, `cuaderno-daily-ollama-model`. La clave de Gemini
sigue guardándose igual.

### 8.2 Abrir el CORS (imprescindible)

`OLLAMA_ORIGINS` **no estaba definida**: la lista que aceptaba `localhost:5500`
era la interna de Ollama, por eso GitHub Pages recibía 403.

```powershell
$origins = "https://yoel413.github.io,https://*.github.io,http://localhost:5500,http://127.0.0.1:5500,http://localhost:*,http://127.0.0.1:*,app://*,file://*"
[Environment]::SetEnvironmentVariable('OLLAMA_ORIGINS', $origins, 'User')
```

Reiniciar el stack entero, no solo `serve`: un hijo hereda el entorno del padre,
así que el supervisor relanzaría `serve` con la variable vieja.

```powershell
Get-Process -Name ollama, "ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
```

Verificado origen por origen:

| Origin | Resultado |
|---|---|
| `https://yoel413.github.io` | 200, permitido |
| `https://otro.github.io` | 200, permitido (wildcard) |
| `http://localhost:5500` | 200, permitido |
| `https://sitio-malicioso.com` | **403**, rechazado |

### 8.3 Servir la página por HTTP, no abrir el fichero

Doble clic en el `.html` **no funciona**. Una página `file://` envía
`Origin: null`, y la lista blanca lo rechaza con 403:

```
Origin: null -> RECHAZADO (403)
```

Hay que servirla en un puerto local:

```powershell
py -m http.server 5500 --bind 127.0.0.1 --directory "...\Daily-page"
# abrir http://localhost:5500/index.html
```

`py -m http.server` es módulo de la librería estándar de Python. No instala
nada y con `--bind 127.0.0.1` solo escucha en local.

### 8.4 El detalle que más fácil se olvida

`think: false` es obligatorio en el cuerpo de la petición. Es el mismo problema
de la sección 6.1: sin eso Gemma 4 gasta el presupuesto pensando y devuelve
`message.content` vacío. En la app está en `requestOllama()`:

```js
body: JSON.stringify({
  model: aiConfig.ollamaModel,
  stream: false,
  think: false,                       // <- sin esto devuelve vacio
  messages: [{ role: "user", content: POLISH_PROMPT + originalText }],
  options: { temperature: 0.2, top_p: 0.95, top_k: 64, num_predict: 2048 }
})
```

### 8.5 Resultado real

![Antes y después de la revisión de texto](Daily-page/images/antes-despues.png)

Corregido `tubei` → `tuve`, `porblema` → `problema`, `api` → `API`, y mantuvo
los saltos de línea como puntos separados.

Curiosidad fiel a la salida real: Gemma **no** puso los acentos en
`no se por qué` / `no sé por qué`. Se dejó tal cual-sale porque documentar lo que
el modelo hace de verdad vale más que retocar el ejemplo.

### 8.6 Verificación

| Comprobación | Estado |
|---|---|
| `node --check` sobre el JS extraído | OK |
| Balance de etiquetas `<dialog>`, `<div>`, `<form>`, `<script>` | OK |
| Petición real desde `Origin: http://localhost:5500` | `done: stop`, 8.25 tok/s |
| Preflight `OPTIONS` | 204 con cabeceras correctas |

**Pendiente:** subir el cambio al repo. GitHub Pages sigue sirviendo la versión
con Gemini hasta que se haga `commit` + `push`.

---

## 9. Rollback

Todo es reversible y barato. Lo único irrecuperable es el tiempo de descarga.

```powershell
ollama rm gemma4:e4b       # borra 6.6 GB
ollama list                # confirmar que quedó vacío
```

Desinstalar Ollama entero: desinstalador de Windows desde
`%LOCALAPPDATA%\Programs\Ollama`.

---

## 10. Resumen de comandos, en orden

```powershell
# 1. inspección
ollama --version
Invoke-RestMethod http://localhost:11434/api/version

# 2. descarga
ollama pull gemma4:e4b

# 3. comprobar
ollama list

# 4. generar (CLI)
ollama run gemma4:e4b "que es un vector de contexto?"

# 5. generar (REST, sin thinking)
$body = @{ model="gemma4:e4b"; stream=$false; think=$false;
          messages=@(@{role="user";content="hola"});
          options=@{temperature=1.0;top_p=0.95;top_k=64;num_predict=300} } | ConvertTo-Json -Depth 6
Invoke-RestMethod http://localhost:11434/api/chat -Method Post -ContentType "application/json" -Body $body
```

---

## 11. Estado del checklist original

- [x] Ollama instalado — ya estaba, v0.35.1
- [x] `gemma4:e4b` descargado y desplegado — 6.6 GB, Q4_K_M
- [x] Verificado por CLI — texto generado correcto
- [x] Verificado por API REST `localhost:11434` — `/api/chat` y `/api/generate`
- [x] **No** hizo falta `gemma4:e2b` ni `gemma3:4b` — el E4B rinde a 9.4 tok/s
- [ ] Repetir en el equipo personal — pendiente, aquí no aplica

### Checklist de la web

- [x] CORS abierto a `yoel413.github.io` — `OLLAMA_ORIGINS` persistente
- [x] Ollama añadido como proveedor, Gemini conservado
- [x] Probado desde `http://localhost:5500` con preflight y generación
- [ ] `git push` al repo — **pendiente de decidir con el compañero**
