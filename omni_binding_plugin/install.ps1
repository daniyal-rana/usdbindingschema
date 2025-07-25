# USD Binding Protocol Extension Installation Script for Windows
# Run this script in PowerShell to install the extension and dependencies

param(
    [string]$OmniversePath = "",
    [switch]$InstallDependencies = $true,
    [switch]$CreateSymlink = $false
)

Write-Host "=== USD Binding Protocol Extension Installer ===" -ForegroundColor Green

# Function to find Omniverse installation
function Find-OmniversePath {
    $possiblePaths = @(
        "$env:LOCALAPPDATA\ov\pkg",
        "$env:PROGRAMFILES\NVIDIA Corporation\Omniverse",
        "$env:PROGRAMDATA\NVIDIA Corporation\Omniverse"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $appPaths = Get-ChildItem -Path $path -Directory -Filter "*kit*" | Sort-Object LastWriteTime -Descending
            if ($appPaths.Count -gt 0) {
                $extensionsPath = Join-Path $appPaths[0].FullName "exts"
                if (Test-Path $extensionsPath) {
                    return $extensionsPath
                }
            }
        }
    }
    
    return $null
}

# Determine installation path
if (-not $OmniversePath) {
    Write-Host "Searching for Omniverse installation..." -ForegroundColor Yellow
    $OmniversePath = Find-OmniversePath
    
    if (-not $OmniversePath) {
        Write-Host "Could not find Omniverse installation automatically." -ForegroundColor Red
        Write-Host "Please specify the extensions directory path using -OmniversePath parameter" -ForegroundColor Red
        Write-Host "Example: .\install.ps1 -OmniversePath 'C:\Users\YourName\AppData\Local\ov\pkg\create-2023.2.1\exts'" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Using Omniverse extensions path: $OmniversePath" -ForegroundColor Green

# Validate path
if (-not (Test-Path $OmniversePath)) {
    Write-Host "Extensions directory does not exist: $OmniversePath" -ForegroundColor Red
    exit 1
}

# Extension installation
$sourcePath = Join-Path $PSScriptRoot "omni_binding_plugin"
$targetPath = Join-Path $OmniversePath "omni.binding.protocol"

Write-Host "Installing extension..." -ForegroundColor Yellow

if (Test-Path $targetPath) {
    Write-Host "Existing extension found. Removing..." -ForegroundColor Yellow
    Remove-Item -Path $targetPath -Recurse -Force
}

if ($CreateSymlink) {
    # Create symbolic link (requires admin privileges)
    Write-Host "Creating symbolic link..." -ForegroundColor Yellow
    try {
        New-Item -ItemType SymbolicLink -Path $targetPath -Target $sourcePath -Force
        Write-Host "Symbolic link created successfully!" -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to create symbolic link (may require admin privileges). Copying files instead..." -ForegroundColor Yellow
        Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
    }
}
else {
    # Copy files
    Write-Host "Copying extension files..." -ForegroundColor Yellow
    Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
    Write-Host "Extension files copied successfully!" -ForegroundColor Green
}

# Install Python dependencies
if ($InstallDependencies) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    
    $requirementsPath = Join-Path $sourcePath "requirements.txt"
    
    if (Test-Path $requirementsPath) {
        # Try to find Omniverse Python
        $pythonPaths = @(
            (Get-Command python -ErrorAction SilentlyContinue).Source,
            (Get-Command python3 -ErrorAction SilentlyContinue).Source
        )
        
        $pythonExe = $null
        foreach ($pythonPath in $pythonPaths) {
            if ($pythonPath -and (Test-Path $pythonPath)) {
                $pythonExe = $pythonPath
                break
            }
        }
        
        if ($pythonExe) {
            Write-Host "Installing dependencies with: $pythonExe" -ForegroundColor Yellow
            
            # Install each dependency individually to handle optional ones
            $dependencies = @(
                "aiomqtt>=2.0.0",
                "aiohttp>=3.8.0", 
                "aioodbc>=0.4.0",
                "grpcio>=1.50.0",
                "websockets>=11.0.0"
            )
            
            foreach ($dep in $dependencies) {
                Write-Host "Installing $dep..." -ForegroundColor Gray
                try {
                    & $pythonExe -m pip install $dep --quiet
                    Write-Host "  ✓ $dep installed" -ForegroundColor Green
                }
                catch {
                    Write-Host "  ✗ Failed to install $dep (optional)" -ForegroundColor Yellow
                }
            }
        }
        else {
            Write-Host "Python not found in PATH. Please install dependencies manually:" -ForegroundColor Yellow
            Write-Host "pip install aiomqtt aiohttp aioodbc grpcio websockets" -ForegroundColor Gray
        }
    }
}

# Create test data
Write-Host "Creating test data files..." -ForegroundColor Yellow
$testConfigPath = Join-Path $sourcePath "test_config.py"
if (Test-Path $testConfigPath) {
    try {
        Set-Location $sourcePath
        & python test_config.py
        Write-Host "Test data files created!" -ForegroundColor Green
    }
    catch {
        Write-Host "Could not create test data files (optional)" -ForegroundColor Yellow
    }
    finally {
        Set-Location $PSScriptRoot
    }
}

# Final instructions
Write-Host ""
Write-Host "=== Installation Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Start NVIDIA Omniverse (Code, Create, or USD Composer)" -ForegroundColor White
Write-Host "2. Go to Window → Extensions → Extension Manager" -ForegroundColor White
Write-Host "3. Search for 'USD Binding Protocol' and enable it" -ForegroundColor White
Write-Host "4. Open the examples/SmartBuilding.usda file to test" -ForegroundColor White
Write-Host "5. Access the UI via Window → USD Binding Protocols" -ForegroundColor White
Write-Host ""
Write-Host "Extension installed to: $targetPath" -ForegroundColor Gray
Write-Host ""
Write-Host "For more information, see the README.md file." -ForegroundColor Gray
