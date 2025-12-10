# powershell -ExecutionPolicy Bypass -File package.ps1
$version = (Get-Content -Path "VERSION" -TotalCount 1).Trim()
$releaseDir = "TtimoTtabbong_$version"
if (Test-Path $releaseDir) { Remove-Item $releaseDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

Write-Host "Copying files..."
Copy-Item "dist/TtimoTtabbong_$version.exe" -Destination $releaseDir
Copy-Item "data" -Destination $releaseDir -Recurse
Copy-Item "ignored_champions.json" -Destination $releaseDir
Copy-Item "ui_settings.json" -Destination $releaseDir
Copy-Item "credits.json" -Destination $releaseDir
Copy-Item "champion_aliases.json" -Destination $releaseDir
Copy-Item "icon.ico" -Destination $releaseDir

Write-Host "Compressing..."
$zipFile = "$releaseDir.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
Compress-Archive -Path "$releaseDir\*" -DestinationPath $zipFile -Force

Write-Host "Done. Created $zipFile"
