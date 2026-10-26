# -----------------------------------------------------------------------------
# Comprueba el stack de extremo a extremo (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File .\scripts\verificar.ps1
# -----------------------------------------------------------------------------
$Api = "http://localhost:$(if ($env:API_PORT) { $env:API_PORT } else { 8000 })"
$Web = "http://localhost:$(if ($env:WEB_PORT) { $env:WEB_PORT } else { 8080 })"
$Fallos = 0
function Ok($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Ko($m) { Write-Host "  [FALLO] $m" -ForegroundColor Red; $script:Fallos++ }

Write-Host "1) Estado de los contenedores"
docker compose ps

Write-Host "`n2) La API está viva"
try { Invoke-RestMethod "$Api/health" | Out-Null; Ok "API responde en $Api" } catch { Ko "La API no responde en $Api" }

Write-Host "`n3) La API llega al backend Ollama"
try { $i = Invoke-RestMethod "$Api/health/backend"; Ok "$($i.modo) -> $($i.backend_url) | modelo: $($i.modelo) | $($i.status)" }
catch { Ko "La API no llega a Ollama (mira: docker compose logs api)" }

Write-Host "`n4) El frontend y su proxy hacia la API"
try { Invoke-WebRequest "$Web/" -UseBasicParsing | Out-Null; Ok "Frontend en $Web" } catch { Ko "El frontend no responde en $Web" }
try { Invoke-RestMethod "$Web/api/info" | Out-Null; Ok "Proxy nginx /api -> api:8000 funciona" } catch { Ko "El proxy del frontend no llega a la API" }

Write-Host "`n5) Pregunta de prueba al modelo (puede tardar en CPU)"
$body = '{"messages":[{"role":"user","content":"Responde solo con la palabra: funciona"}]}'
try {
  $r = Invoke-RestMethod "$Api/api/chat" -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 300
  Ok "[$($r.modo)] $($r.reply)"
} catch { Ko "El modelo no ha respondido" }

Write-Host ""
if ($Fallos -eq 0) { Write-Host "Todo correcto." } else { Write-Host "$Fallos comprobación(es) fallida(s)." }
exit $Fallos
