# Starts the portal at http://127.0.0.1:8000
$uv = Get-Command uv -ErrorAction SilentlyContinue
$exe = if ($uv) { $uv.Source } else { "$env:USERPROFILE\.local\bin\uv.exe" }
Set-Location $PSScriptRoot
& $exe run uvicorn main:app --host 127.0.0.1 --port 8000
