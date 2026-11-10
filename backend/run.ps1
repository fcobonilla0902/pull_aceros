$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python 3.12.' }
}
& $python -c "import fastapi,sqlalchemy,alembic,simpy,openpyxl,multipart,tzdata,psycopg,dotenv; assert tuple(map(int,fastapi.__version__.split('.')[:2])) >= (0,121)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Instalando las dependencias necesarias del backend...'
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
}
& $python local_postgres.py autostart
if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar PostgreSQL local.' }
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron aplicar las migraciones.' }
$needsAdmin = & $python -c "from database import Session, User; from sqlalchemy import select; s=Session(); print('yes' if s.scalar(select(User.id)) is None else 'no'); s.close()"
if ($LASTEXITCODE -ne 0) { throw 'No se pudo verificar la base de datos.' }
if ($needsAdmin -eq 'no') {
    & $python manage.py backup
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo guardar el respaldo previo al arranque.' }
}
if ($needsAdmin -eq 'yes' -and -not $env:METARIDE_ADMIN_PASSWORD) {
    $secret = Read-Host 'Define la contraseña inicial de admin (mínimo 12 caracteres)' -AsSecureString
    $env:METARIDE_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
    if ($env:METARIDE_ADMIN_PASSWORD.Length -lt 12) { throw 'Se requieren al menos 12 caracteres.' }
}
try { & $python -m uvicorn main:app --host 127.0.0.1 --port 8000 }
finally { Remove-Item Env:METARIDE_ADMIN_PASSWORD -ErrorAction SilentlyContinue }
