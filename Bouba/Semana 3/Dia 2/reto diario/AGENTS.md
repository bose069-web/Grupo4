# AGENTS.md — Instalación de stack LLM local

Instrucciones para un agente de IA que ejecute esta instalación.
**Lee este archivo entero antes de tocar nada.**

---

## 1. Objetivo

Dejar funcionando un stack de LLM local en el **equipo personal** del usuario:

- Ollama (motor de inferencia)
- Cliente `ollama` de Python dentro de un venv
- 3 modelos: `qwen2.5-coder:7b`, `qwen2.5:7b`, `llama3.1:8b` (~14.3 GB)

El usuario lo hará **más adelante**, en otro equipo. No hay prisa, pero tampoco
que la IA "lo haga rápido".

---

## 2. Contexto: lo que ya se investigó (NO repetir este análisis)

Un intento previo falló. La causa real **no** fue la que se documentó antes:

| Creencia anterior | Realidad |
|---|---|
| `open-interpreter` es incompatible con Python 3.12 en Windows | **Falso.** El venv apuntaba a `C:\Users\secko\...`, un usuario inexistente en ese equipo. Los venv se crearon en otra máquina y se copiaron. Estaban muertos desde el origen. |
| `ollama` funcionaba | **Falso.** `ollama list` estaba vacío: no había ningún modelo. |
| Python 3.12 daba problemas | El equipo solo tenía **Python 3.14**. Nunca hubo 3.12. |

Corolario importante: **los venv no sobreviven a cambiar de equipo.** Guardan
rutas absolutas del intérprete. Crear el venv siempre en destino, nunca copiarlo.

### Trampas conocidas — no repetirlas

- `Python-3.12.14.tgz` está en `D:\` (portátil del trabajo). Es un **tarball de
  código fuente de Linux**. No se puede instalar en Windows. No usarlo.
- **No instalar nada en el portátil del trabajo** (`ibl\boubacar.seck.ext`).
  Es un equipo corporativo gestionado con **Cortex XDR** e **Ivanti Application
  Control**. El disco externo `D:` (WD Elements, `UnionSine`) bloquea toda
  escritura desde procesos no aprobados, aunque los permisos NTFS los permitan.
  `D:\AI_Agent` se queda como está: inerte, muerto e inofensivo.
- No usar `py -3.12`. Usar `py` a secas (whatever version) o el launcher que
  exista.
- **No instalar `open-interpreter`.** Es un wrapper pesado y frágil que ejecuta
  shell en la máquina. No es necesario para nada de lo que se pide aquí.

---

## 3. Leyenda de finalidad

Cada paso va anotado. **Respetar las anotaciones.**

| Marca | Significado |
|---|---|
| `[LECTURA]` | Solo lee. No cambia nada. Seguro. |
| `[ADITIVO]` | Crea archivos nuevos. No borra ni sobrescribe nada existente. |
| `[SOBRESCRIBE]` | Sobrescribe un archivo que ya existe. Verificar antes. |
| `[DESTRUCTIVO]` | **Borra datos. Irreversible.** Pedir confirmación explícita al usuario. |
| `[RED]` | Descarga de internet. Aquí, ~14.3 GB. |
| `[SISTEMA]` | Cambia configuración del sistema o del entorno. |
| `[LENTO]` | Tarda minutos. Normal, no es un error. |

---

## 4. Fase 0 — Inspección previa (todo `[LECTURA]`)

Ejecutar esto primero. **Si el equipo no es el esperado, PARAR y preguntar.**

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

**Reglas de decisión tras la Fase 0:**

- **Python no instalado** → `[ADITIVO]` instalar desde python.org. **Preguntar al
  usuario primero.** No instalar sin permiso.
- **RAM < 8 GB** → 3 modelos no caben en RAM a la vez. Avisar; siguen cabiendo en
  disco porque solo se carga uno cada vez.
- **Sin GPU NVIDIA** → la inferencia va por CPU. Con 7B/8B esperar 5-10 tokens/s.
  Considerar proponer `qwen2.5-coder:3b` (≈1.9 GB) en lugar de 7B para que sea
  usable. **Preguntar, no decidir solo.**
- **Disco < 25 GB libres** → parar. No cabe la instalación.

---

## 5. Fase 1 — Decidir dónde va todo `[LECTURA]` → decisión del usuario

Por defecto todo cae en **C:** del equipo personal:

| Qué | Ruta por defecto |
|---|---|
| Modelos | `%USERPROFILE%\.ollama\models` (~14.3 GB) |
| Ollama | `%LOCALAPPDATA%\Programs\Ollama` |
| Venv | donde se haga `cd` antes de crearlo |

Si el usuario prefiere el disco externo (debe ser **NTFS**, no exFAT), definir
`OLLAMA_MODELS` **antes del primer `pull`**:

```powershell
$env:OLLAMA_MODELS = "E:\Ollama\models"   # solo esta terminal
# o persistente (requiere reiniciar la terminal y Ollama):
setx OLLAMA_MODELS "E:\Ollama\models"
```

> Si se cambia después de descargar modelos, Ollama no los ve. Hay que repetirlos.
> `setx` es `[SISTEMA]` persistente — preguntar antes de usarlo.

**Preguntar al usuario** qué prefiere antes de decidir. No asumir.

---

## 6. Fase 2 — Instalación

### 2.1 Crear el venv

```powershell
cd <DIR_ELEGIDA>          # p. ej. C:\AI_Agent
py -m venv .venv          # [ADITIVO]
```

**No usar `py -3.12`.** No usar el `.tgz` de `D:\`.

### 2.2 Instalar paquetes

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip        # [ADITIVO] [SISTEMA]
.\.venv\Scripts\python.exe -m pip install ollama       # [ADITIVO] [RED]
```

Usar siempre la ruta completa al intérprete del venv. No activar el venv con
`activate` — añade complejidad innecesaria.

### 2.3 Verificar el import antes de seguir

```powershell
.\.venv\Scripts\python.exe -c "import ollama; print(ollama.__version__)"
```

Si esto falla, **PARAR**. No continuar a los modelos.

### 2.4 Arrancar el motor

```powershell
ollama serve
```

Dejar esa terminal abierta. En otra terminal, continuar.

### 2.5 Descargar modelos

```powershell
ollama pull qwen2.5-coder:7b    # [RED] [LENTO]  4.7 GB
ollama pull qwen2.5:7b          # [RED] [LENTO]  4.7 GB
ollama pull llama3.1:8b         # [RED] [LENTO]  4.9 GB
```

Tamaño total verificado en la librería oficial de Ollama (cuantización Q4_K_M):
**~14.3 GB**. Si alguno falla por disco lleno, parar y preguntar.

---

## 7. Fase 3 — Verificación (obligatoria antes de decir "listo")

```powershell
ollama list                    # [LECTURA] deben aparecer los 3 modelos
```

Prueba real de generación, no solo de instalación:

```powershell
ollama run llama3.1:8b "Explica en dos frases qué es un vector de contexto"  # [RED]
```

Y desde Python, que es el objetivo real del venv:

```powershell
.\.venv\Scripts\python.exe -c "import ollama; print(ollama.chat(model='qwen2.5:7b', messages=[{'role':'user','content':'di hola'}]))"
```

**Criterio de éxito:** las tres verificaciones pasan y hay texto generado.
Un `ollama list` con 3 modelos pero sin generación real **no** es un éxito.

---

## 8. Rollback

Todo lo instalado es reversible, y es barato. En orden inverso:

```powershell
ollama rm qwen2.5-coder:7b     # [DESTRUCTIVO] borra 4.7 GB, hay que redescargar
ollama rm qwen2.5:7b           # [DESTRUCTIVO] borra 4.7 GB
ollama rm llama3.1:8b          # [DESTRUCTIVO] borra 4.9 GB
```

- Borrar el venv entero: `[DESTRUCTIVO]` `Remove-Item -Recurse -Force <DIR>\.venv`
  (solo recreateble, no hay datos).
- Quitar Ollama: `[SISTEMA]` desinstalador de Windows.
- Cambiar `OLLAMA_MODELS`: devolver a `%USERPROFILE%\.ollama\models`.

**Lo único irrecuperable es el tiempo de descarga.** No hay datos de usuario en
juego en ningún punto.

---

## 9. Notas para el agente

- Si un paso falla, **leer el error entero** antes de proponer nada. No repetir
  el patrón de instalar y fallar, arrancar variaciones a ciegas: el intento
  anterior falló precisamente por eso (5 versiones de `open-interpreter` probadas
  sin leer el error de fondo).
- `open-interpreter` no está en el alcance. Si el usuario lo pide, explicar por
  qué se descartó, no simplemente instalarlo.
- `qwen2.5-coder` y `qwen2.5:7b` comparten base (7.62B params, Q4_K_M). Se
  pueden quitar ambos si el usuario prefiere ahorrar 9.4 GB.
- Todos los pasos son locales. **Nada de esto necesita red más allá de la
  descarga de modelos.**
