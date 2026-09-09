# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------
$projectId = "gaming-45ba6"
$collection = "games"
$apiKey = "6c485c502f574fad8d8e96bc5cbf8774"
$limiteJuegos = 5000
$juegosPorPagina = 40

$apiHeaders = @{
Accept = "application/json"
}

# --------------------------------------------------
# AUTENTICACION CON GOOGLE CLOUD
# --------------------------------------------------

# Necesitas tener instalada la CLI de Google Cloud y haber ejecutado:
# gcloud auth application-default login
#
# O alternativamente:
# gcloud auth login

$accessToken = gcloud auth print-access-token

if ([string]::IsNullOrWhiteSpace($accessToken)) {
throw "No se ha podido obtener el token de Google Cloud."
}

# --------------------------------------------------
# OBTENER JUEGOS DESDE LA API
# --------------------------------------------------

# RAWG devuelve los juegos por paginas dentro de la propiedad "results".
$games = @()
$pagina = 1

while ($games.Count -lt $limiteJuegos) {
$apiUrl = "https://api.rawg.io/api/games?key=$apiKey&page=$pagina&page_size=$juegosPorPagina"

$response = Invoke-RestMethod `
-Uri $apiUrl `
-Method Get `
-Headers $apiHeaders

if ($null -ne $response.results) {
$pageGames = @($response.results)
}
else {
$pageGames = @($response)
}

if ($pageGames.Count -eq 0) {
break
}

$games += $pageGames
$pagina++
}

if ($games.Count -gt $limiteJuegos) {
$games = @($games | Select-Object -First $limiteJuegos)
}

Write-Host "Se han recibido $($games.Count) videojuegos."

# --------------------------------------------------
# INSERTAR O ACTUALIZAR EN FIRESTORE
# --------------------------------------------------

foreach ($game in $games) {
try {
# Convertir plataformas en valores compatibles con Firestore
$platformValues = @()

foreach ($platform in $game.platforms) {
# Si platforms ya contiene strings:
if ($platform -is [string]) {
$platformName = $platform
}
# RAWG normalmente devuelve platform.name:
elseif ($null -ne $platform.platform.name) {
$platformName = $platform.platform.name
}
# Posible formato alternativo:
elseif ($null -ne $platform.name) {
$platformName = $platform.name
}
else {
continue
}

$platformValues += @{
stringValue = [string]$platformName
}
}

# Construcción del documento Firestore
$firestoreFields = @{
id = @{
integerValue = [string]$game.id
}
name = @{
stringValue = [string]$game.name
}
rating = @{
doubleValue = [double]$game.rating
}
platforms = @{
arrayValue = @{
values = $platformValues
}
}
}

# Estos campos pueden llegar vacíos o nulos.
if ($null -ne $game.background_image) {
$firestoreFields["background_image"] = @{
stringValue = [string]$game.background_image
}
}
else {
$firestoreFields["background_image"] = @{
nullValue = $null
}
}

if ($null -ne $game.released) {
# Se guarda como texto porque la API devuelve solamente YYYY-MM-DD.
$firestoreFields["released"] = @{
stringValue = [string]$game.released
}
}
else {
$firestoreFields["released"] = @{
nullValue = $null
}
}

$body = @{
fields = $firestoreFields
} | ConvertTo-Json -Depth 20

# El ID del juego se utiliza como ID del documento
$documentId = [string]$game.id

$firestoreUrl = "https://firestore.googleapis.com/v1/projects/$projectId/databases/(default)/documents/$collection/$documentId"

# PATCH crea el documento si no existe y lo actualiza si ya existe.
Invoke-RestMethod `
-Uri $firestoreUrl `
-Method Patch `
-Headers @{
Authorization = "Bearer $accessToken"
} `
-ContentType "application/json; charset=utf-8" `
-Body $body | Out-Null

Write-Host "Importado correctamente: $($game.name) [$documentId]" `
-ForegroundColor Green
}
catch {
Write-Host "Error importando $($game.name): $($_.Exception.Message)" `
-ForegroundColor Red
}
}

Write-Host "Importacion terminada."