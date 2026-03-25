# Session Startup

At the start of every session, verify the development environment is ready:

```powershell
# Check Python is available
python --version

# Check Node.js is available
node --version

# Check if dependencies are installed
if (Test-Path "api\requirements.txt") { python -c "import fastapi" 2>$null || Write-Host "⚠️  Backend deps not installed. Run: cd api && uv pip install -r requirements.txt" }
if (Test-Path "frontend\package.json") { if (-not (Test-Path "frontend\node_modules")) { Write-Host "⚠️  Frontend deps not installed. Run: cd frontend && npm install" } }
```

Then proceed with whatever task the user requested.
