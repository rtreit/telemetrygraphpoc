<#
.SYNOPSIS
    Build the complete web application (React frontend + .NET backend)
.DESCRIPTION
    1. Builds the React frontend
    2. Copies built assets to webapp/wwwroot
    3. Builds and publishes the .NET web app
#>
param(
    [string]$Configuration = "Release",
    [string]$OutputDir = "publish"
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

Write-Host "=== Building React frontend ===" -ForegroundColor Cyan
Push-Location "$repoRoot\frontend"
npm run build
Pop-Location

Write-Host "=== Copying frontend to wwwroot ===" -ForegroundColor Cyan
$wwwroot = "$repoRoot\webapp\wwwroot"
if (Test-Path $wwwroot) { Remove-Item -Recurse -Force $wwwroot }
Copy-Item -Recurse "$repoRoot\frontend\dist" $wwwroot

Write-Host "=== Building .NET web app ===" -ForegroundColor Cyan
dotnet publish "$repoRoot\webapp\webapp.csproj" -c $Configuration -o "$repoRoot\$OutputDir"

Write-Host "=== Build complete ===" -ForegroundColor Green
Write-Host "Output: $repoRoot\$OutputDir"
