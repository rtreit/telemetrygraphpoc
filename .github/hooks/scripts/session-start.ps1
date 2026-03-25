<#
.SYNOPSIS
    Session start hook — verifies development environment.
.DESCRIPTION
    Runs automatically at the start of every Copilot CLI session.
    Checks that Python and Node.js are available and that project
    dependencies are installed.
#>

$repoRoot = git rev-parse --show-toplevel 2>$null
if (-not $repoRoot) { $repoRoot = $PSScriptRoot -replace '[\\/]\.github[\\/]hooks[\\/]scripts$', '' }

# Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    Write-Host "Python: $(python --version 2>&1)" -ForegroundColor DarkGray
} else {
    Write-Host "WARNING: Python not found on PATH" -ForegroundColor Yellow
}

# Check Node
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "Node: $(node --version 2>&1)" -ForegroundColor DarkGray
} else {
    Write-Host "WARNING: Node.js not found on PATH" -ForegroundColor Yellow
}

# Check backend dependencies
$reqFile = Join-Path $repoRoot "api\requirements.txt"
if (Test-Path $reqFile) {
    python -c "import fastapi" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Backend deps not installed. Run: cd api && uv pip install -r requirements.txt" -ForegroundColor Yellow
    }
}

# Check frontend dependencies
$pkgJson = Join-Path $repoRoot "frontend\package.json"
if (Test-Path $pkgJson) {
    $nodeModules = Join-Path $repoRoot "frontend\node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Host "Frontend deps not installed. Run: cd frontend && npm install" -ForegroundColor Yellow
    }
}
