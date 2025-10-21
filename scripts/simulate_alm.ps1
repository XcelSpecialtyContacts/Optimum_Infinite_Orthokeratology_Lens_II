<#
Simulate an ALM machine calling a remote PC to run a Python program and return an exit code.

Usage examples:
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -Mode both
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -Mode cer -CondaEnv pointfile
  .\scripts\simulate_alm.ps1 -TargetComputer 081LAB20 -Mode front -PythonPath "C:\Users\you\miniconda3\envs\pointfile\python.exe"

Notes:
- This uses PowerShell Remoting (WinRM). If not enabled, see the “If remoting isn’t enabled” note below.
- Remote path assumes dummy.py is at C:\Projects\Optimum_Infinite_Orthokeratology_Lens_II\tests\dummy.py on the target.
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidateNotNullOrEmpty()]
  [string]$TargetComputer,

  [Parameter(Mandatory)]
  [ValidateSet('both','base','front','ier','cer','oer','toer','uer')]
  [string]$Mode,

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
Write-Host "Target: $TargetComputer"
Write-Host "Mode:   $Mode"
Write-Host "Repo:   $RemoteRepoRoot"
if ($PythonPath) { Write-Host "Python: $PythonPath" } else { Write-Host "Conda env: $CondaEnv" }

# ScriptBlock runs on the remote machine.
$remoteScript = {
  param($mode, $envName, $pyPath, $root)

  # Do NOT escalate native command stderr into terminating errors
  $ErrorActionPreference = 'Continue'
  $ProgressPreference    = 'SilentlyContinue'

  $dummy = Join-Path $root 'tests\dummy.py'
  if (-not (Test-Path -LiteralPath $dummy)) {
    # 10 = input error (your convention)
    return [pscustomobject]@{
      ExitCode = 10
      Computer = $env:COMPUTERNAME
      Message  = "Input error: dummy.py missing at $dummy"
    }
  }

  # Build the native command string
  if ($pyPath) {
    $cmd = @(
      "`"$pyPath`""
      "`"$dummy`""
      "--mode $mode"
    ) -join ' '
  } else {
    $cmd = @(
      "conda.exe run -n $envName python"
      "`"$dummy`""
      "--mode $mode"
    ) -join ' '
  }

  Write-Host "[Remote:$env:COMPUTERNAME] CMD: $cmd"

  # Run via cmd.exe so conda's non-zero exit doesn't throw a remoting error.
  # Redirect stderr -> stdout to keep output visible but non-terminating.
  $LASTEXITCODE = 0
  $output = & cmd.exe /c $cmd 2>&1
  if ($output) { $output | ForEach-Object { Write-Host $_ } }

  $code = $LASTEXITCODE
  Write-Host "[Remote:$env:COMPUTERNAME] dummy.py exit code: $code"

  # Always return an object; never throw here.
  return [pscustomobject]@{
    ExitCode = $code
    Computer = $env:COMPUTERNAME
    Message  = if ($code -eq 0) { "OK" } else { "Non-zero exit propagated" }
  }
}

# Build Invoke-Command parameters
$icmParams = @{
  ComputerName = $TargetComputer
  ScriptBlock  = $remoteScript
  ArgumentList = @($Mode, $CondaEnv, $PythonPath, $RemoteRepoRoot)
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

# $result is a PSCustomObject from the remote block
$exitCode = $result.ExitCode
$hostName = $result.Computer
$message  = $result.Message

Write-Host "=== Remote result from $hostName ===" -ForegroundColor Cyan
Write-Host "ExitCode: $exitCode"
if ($message) { Write-Host "Message : $message" }

# Mirror the remote exit code on the local process so callers can check $LASTEXITCODE
exit [int]$exitCode
