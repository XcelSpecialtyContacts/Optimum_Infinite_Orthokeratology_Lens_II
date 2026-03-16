<#
Simulate an ALM machine calling a remote PC to run the OIOL2 generator and return an exit code.

Usage examples:
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -WorkOrder 9312150
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -WorkOrder 9312150 -CondaEnv pointfile
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -WorkOrder 9312150 -PythonPath "C:\Users\you\miniconda3\envs\pointfile\python.exe"

Notes:
- Uses PowerShell Remoting (WinRM).
- Assumes repo exists at C:\Projects\Optimum_Infinite_Orthokeratology_Lens_II on the remote host (override with -RemoteRepoRoot).
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidateNotNullOrEmpty()]
  [string]$TargetComputer,

  [Parameter()]
  [ValidateNotNullOrEmpty()]
  [string]$WorkOrder = '9312150',

  # If you want to rely on Conda on the remote host (recommended)
  [Parameter()]
  [string]$CondaEnv = 'pointfile',

  # If you prefer to call a specific Python interpreter on the remote host, set this.
  # When set, this takes precedence over Conda.
  [Parameter()]
  [string]$PythonPath,

  # Root of the project on the remote host
  [Parameter()]
  [string]$RemoteRepoRoot = 'C:\Projects\Optimum_Infinite_Orthokeratology_Lens_II',

  # If you need to pass credentials explicitly, add -Credential (Get-Credential)
  [Parameter()]
  [System.Management.Automation.PSCredential]$Credential
)

Write-Host "=== simulate_alm.ps1 ===" -ForegroundColor Cyan
Write-Host "Target:    $TargetComputer"
Write-Host "WorkOrder: $WorkOrder"
Write-Host "Repo:      $RemoteRepoRoot"
if ($PythonPath) { Write-Host "Python:    $PythonPath" } else { Write-Host "Conda env: $CondaEnv" }

# ScriptBlock runs on the remote machine.
$remoteScript = {
  param($wo, $envName, $pyPath, $root)

  $ErrorActionPreference = 'Continue'
  $ProgressPreference    = 'SilentlyContinue'

  if (-not (Test-Path -LiteralPath $root)) {
    return [pscustomobject]@{
      ExitCode = 10
      Computer = $env:COMPUTERNAME
      Message  = "Input error: repo root missing at $root"
    }
  }

  Push-Location $root
  try {
    if ($pyPath) {
      $cmd = @(
        "`"$pyPath`""
        "-m src.oiol2.main"
        "--wo $wo"
      ) -join ' '
    } else {
      $cmd = @(
        "conda.exe run -n $envName python"
        "-m src.oiol2.main"
        "--wo $wo"
      ) -join ' '
    }

    Write-Host "[Remote:$env:COMPUTERNAME] CWD: $(Get-Location)"
    Write-Host "[Remote:$env:COMPUTERNAME] CMD: $cmd"

    # Run via cmd.exe so conda's non-zero exit doesn't throw a remoting error.
    $LASTEXITCODE = 0
    $output = & cmd.exe /c $cmd 2>&1
    if ($output) { $output | ForEach-Object { Write-Host $_ } }

    $code = $LASTEXITCODE
    Write-Host "[Remote:$env:COMPUTERNAME] exit code: $code"

    return [pscustomobject]@{
      ExitCode = $code
      Computer = $env:COMPUTERNAME
      Message  = if ($code -eq 0) { "OK" } else { "Non-zero exit propagated" }
    }
  }
  finally {
    Pop-Location
  }
}

$icmParams = @{
  ComputerName = $TargetComputer
  ScriptBlock  = $remoteScript
  ArgumentList = @($WorkOrder, $CondaEnv, $PythonPath, $RemoteRepoRoot)
  ErrorAction  = 'Stop'
}

if ($PSBoundParameters.ContainsKey('Credential')) {
  $icmParams['Credential'] = $Credential
}

try {
  $result = Invoke-Command @icmParams
} catch {
  Write-Error "Remote execution failed: $($_.Exception.Message)"
  exit 50
}

$exitCode = $result.ExitCode
$hostName = $result.Computer
$message  = $result.Message

Write-Host "=== Remote result from $hostName ===" -ForegroundColor Cyan
Write-Host "ExitCode: $exitCode"
if ($message) { Write-Host "Message : $message" }

exit [int]$exitCode
