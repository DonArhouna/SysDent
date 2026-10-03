# Recrée l'environnement de test isolé (conteneur jetable sur un port libre).
# Usage depuis Backend/ :  .\_setup_test_db.ps1
$ErrorActionPreference = 'Stop'

$container = 'sysdent_s0b'
$port      = 55435
$password  = 'postgres_password'

$running = docker ps --filter "name=^/$container$" -q
if (-not $running) {
    $existing = docker ps -a --filter "name=^/$container$" -q
    if ($existing) { docker start $container | Out-Null }
    else {
        docker run -d --name $container `
            -e POSTGRES_PASSWORD=$password `
            -e POSTGRES_USER=postgres `
            -e POSTGRES_DB=sysdent_master `
            -p "${port}:5432" postgres:16-alpine | Out-Null
    }
}

# Attendre que PostgreSQL accepte les connexions.
for ($i = 0; $i -lt 30; $i++) {
    docker exec $container pg_isready -U postgres 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
}

$env:MASTER_DB_HOST     = '127.0.0.1'
$env:MASTER_DB_PORT     = "$port"
$env:MASTER_DB_NAME     = 'sysdent_master'
$env:TENANT_DB_HOST     = '127.0.0.1'
$env:TENANT_DB_PORT     = "$port"
$env:ALEMBIC_TENANT_DB_URL = "postgresql+psycopg2://postgres:$password@127.0.0.1:$port/sysdent_tenant_ref"
$env:ALEMBIC_MASTER_DB_URL = "postgresql+psycopg2://postgres:$password@127.0.0.1:$port/sysdent_master"
$env:PYTHONUTF8        = '1'

Write-Host "Environnement de test prêt sur le port $port."
