$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Se necesita Python 3.12.' }
}
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
$runtime=Join-Path $PSScriptRoot '.postgres'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$archive=Join-Path $runtime 'postgresql-17.11-5-windows-x64-binaries.zip'
$expected='80379B2C04D51C30225532E0AE04509899141E9957ED096FE749D7FD9DF8F82F'
if (-not (Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    curl.exe -L --fail --retry 5 --retry-all-errors --connect-timeout 20 --continue-at - --output $archive 'https://get.enterprisedb.com/postgresql/postgresql-17.11-5-windows-x64-binaries.zip'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar PostgreSQL.' }
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) { throw 'El archivo no coincide con el SHA-256 publicado por EDB; no se ejecutará.' }
# Extract the server and tools only; pgAdmin and documentation are not needed to run Meta-Ride.
$extract=@'
import sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]).resolve()
with zipfile.ZipFile(root/'postgresql-17.11-5-windows-x64-binaries.zip') as archive:
    for member in archive.infolist():
        if member.filename.startswith(('pgsql/bin/','pgsql/lib/','pgsql/share/')):
            target=(root/member.filename).resolve()
            if not target.is_relative_to(root):raise ValueError('Ruta de archivo inválida')
            archive.extract(member,root)
'@
& $python -c $extract $runtime
if ($LASTEXITCODE -ne 0) { throw 'No se pudo extraer PostgreSQL.' }
& $python local_postgres.py setup
if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar PostgreSQL.' }
Write-Host 'PostgreSQL local está listo. La base activa todavía no ha cambiado.'
Write-Host 'Detén el backend y ejecuta: .\.venv\Scripts\python.exe migrate_postgres.py --activate'
