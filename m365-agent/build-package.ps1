# Copyright (c) 2026 jerry wolff

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ApiBaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$OAuthReferenceId,

    [Parameter(Mandatory = $true)]
    [string]$TenantIdOrDomain,

    [string]$ContactEmail = 'admin@wolffofficetenant.onmicrosoft.com',
    [string]$AppId = '6e80bd1e-8f43-4f93-bc5f-565aabde97b8',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot 'dist\finops-ccoe-agent.zip'
}
$source = Join-Path $PSScriptRoot 'appPackage'
$staging = Join-Path $PSScriptRoot 'dist\staging'
$outputDirectory = Split-Path -Parent $OutputPath
$apiUri = [Uri]$ApiBaseUrl.TrimEnd('/')

Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item $staging -ItemType Directory -Force | Out-Null
New-Item $outputDirectory -ItemType Directory -Force | Out-Null

function Expand-AgentTemplate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    $content = Get-Content $SourcePath -Raw
    $content = $content.Replace('{{APP_ID}}', $AppId)
    $content = $content.Replace('{{API_BASE_URL}}', $apiUri.AbsoluteUri.TrimEnd('/'))
    $content = $content.Replace('{{API_HOST}}', $apiUri.Host)
    $content = $content.Replace('{{OAUTH_REFERENCE_ID}}', $OAuthReferenceId)
    $content = $content.Replace('{{TENANT_ID_OR_DOMAIN}}', $TenantIdOrDomain)
    $content = $content.Replace('{{CONTACT_EMAIL}}', $ContactEmail)
    [System.IO.File]::WriteAllText(
        $DestinationPath,
        $content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

Expand-AgentTemplate (Join-Path $source 'manifest.template.json') (Join-Path $staging 'manifest.json')
Expand-AgentTemplate (Join-Path $source 'finops-api-plugin.template.json') (Join-Path $staging 'finops-api-plugin.json')
Expand-AgentTemplate (Join-Path $source 'finops-openapi.template.yaml') (Join-Path $staging 'finops-openapi.yaml')
Copy-Item (Join-Path $source 'declarativeAgent.json') $staging

Add-Type -AssemblyName System.Drawing

function New-AgentIcon {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [int]$Size,
        [Parameter(Mandatory = $true)]
        [bool]$Outline
    )

    $bitmap = [System.Drawing.Bitmap]::new($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)

    if ($Outline) {
        $pen = [System.Drawing.Pen]::new([System.Drawing.Color]::White, [Math]::Max(2, $Size / 10))
        $graphics.DrawEllipse($pen, $Size * 0.12, $Size * 0.12, $Size * 0.76, $Size * 0.76)
        $graphics.DrawLine($pen, $Size * 0.33, $Size * 0.52, $Size * 0.48, $Size * 0.67)
        $graphics.DrawLine($pen, $Size * 0.48, $Size * 0.67, $Size * 0.72, $Size * 0.35)
        $pen.Dispose()
    }
    else {
        $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(0, 120, 212))
        $graphics.FillEllipse($brush, 0, 0, $Size - 1, $Size - 1)
        $brush.Dispose()
        $font = [System.Drawing.Font]::new('Segoe UI', $Size * 0.32, [System.Drawing.FontStyle]::Bold)
        $textBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
        $format = [System.Drawing.StringFormat]::new()
        $format.Alignment = [System.Drawing.StringAlignment]::Center
        $format.LineAlignment = [System.Drawing.StringAlignment]::Center
        $graphics.DrawString('F', $font, $textBrush, [System.Drawing.RectangleF]::new(0, 0, $Size, $Size), $format)
        $format.Dispose()
        $textBrush.Dispose()
        $font.Dispose()
    }

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}

New-AgentIcon (Join-Path $staging 'color.png') 192 $false
New-AgentIcon (Join-Path $staging 'outline.png') 32 $true

Get-Content (Join-Path $staging 'manifest.json') -Raw | ConvertFrom-Json | Out-Null
Get-Content (Join-Path $staging 'declarativeAgent.json') -Raw | ConvertFrom-Json | Out-Null
Get-Content (Join-Path $staging 'finops-api-plugin.json') -Raw | ConvertFrom-Json | Out-Null

Remove-Item $OutputPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $OutputPath -Force
Write-Host "Created Microsoft 365 Copilot agent package: $OutputPath"