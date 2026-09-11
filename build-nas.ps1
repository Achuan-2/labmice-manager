[CmdletBinding()]
param(
    [switch]$ExcludeExcel
)

$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = [System.IO.Path]::GetFullPath($sourceRoot).TrimEnd('\', '/')
$buildRoot = [System.IO.Path]::GetFullPath((Join-Path $sourceRoot 'build')).TrimEnd('\', '/')

# build 是本脚本唯一允许清理的目录，先校验路径，避免误删项目中的其他内容。
$buildParent = Split-Path -Parent $buildRoot
$buildName = Split-Path -Leaf $buildRoot
if (
    -not [string]::Equals($buildParent, $sourceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    -not [string]::Equals($buildName, 'build', [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "构建目录校验失败：$buildRoot"
}

if (-not (Get-Command robocopy.exe -ErrorAction SilentlyContinue)) {
    throw '未找到 robocopy.exe，此脚本需要在 Windows PowerShell 中运行。'
}

Write-Host "项目目录：$sourceRoot"
Write-Host "构建目录：$buildRoot"

if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildRoot 'data') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildRoot 'excel') | Out-Null

function Copy-SourceTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $source = Join-Path $sourceRoot $Name
    $target = Join-Path $buildRoot $Name
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "缺少源目录：$source"
    }

    $robocopyArguments = @(
        $source,
        $target,
        '/E',
        '/R:2',
        '/W:1',
        '/COPY:DAT',
        '/DCOPY:DAT',
        '/NP',
        '/NFL',
        '/NDL',
        '/NJH',
        '/NJS',
        '/XD',
        'node_modules',
        '.venv',
        '__pycache__',
        '.pytest_cache',
        '.ruff_cache',
        '.mypy_cache',
        'dist',
        '/XF',
        '*.pyc',
        '*.pyo',
        '.env',
        '.env.*'
    )

    & robocopy.exe @robocopyArguments
    $robocopyExitCode = $LASTEXITCODE
    if ($robocopyExitCode -ge 8) {
        throw "复制 $Name 失败，Robocopy 退出码：$robocopyExitCode"
    }
}

Copy-SourceTree -Name 'backend'
Copy-SourceTree -Name 'frontend'

$deploymentFiles = @(
    'Dockerfile',
    'docker-compose.yml',
    '.dockerignore',
    '.env.example',
    'README.md'
)

foreach ($file in $deploymentFiles) {
    $source = Join-Path $sourceRoot $file
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "缺少部署文件：$source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $buildRoot $file) -Force
}

if (-not $ExcludeExcel) {
    $excelSource = Join-Path $sourceRoot 'excel'
    if (Test-Path -LiteralPath $excelSource -PathType Container) {
        $excelTarget = Join-Path $buildRoot 'excel'
        & robocopy.exe $excelSource $excelTarget /E /R:2 /W:1 /COPY:DAT /DCOPY:DAT /NP /NFL /NDL /NJH /NJS
        $robocopyExitCode = $LASTEXITCODE
        if ($robocopyExitCode -ge 8) {
            throw "复制 excel 失败，Robocopy 退出码：$robocopyExitCode"
        }
    }
}

# Robocopy 的 1-7 都表示成功，但会写入非零退出码；避免脚本调用方误判为失败。
$global:LASTEXITCODE = 0

Write-Host ''
Write-Host '群晖部署包创建完成。' -ForegroundColor Green
Write-Host "请把整个 build 文件夹中的内容复制到群晖部署目录：$buildRoot"
Write-Host 'data 和 excel 目录已创建，.env 请在群晖端根据 .env.example 配置。'
if ($ExcludeExcel) {
    Write-Host '已按 -ExcludeExcel 跳过本地 excel 文件。'
} else {
    Write-Host '已包含本地 excel 文件。'
}
