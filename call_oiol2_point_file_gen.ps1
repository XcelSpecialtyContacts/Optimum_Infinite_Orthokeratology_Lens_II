param(
    [string]$wo
)

$remotePC = "081LAB20"
$projectPath = "C:\Projects\Optimum_Infinite_Orthokeratology_Lens_II"

$username = "WALCO_DOM01\Hal2001"
$password = ConvertTo-SecureString "Dave616" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($username, $password)

$script = {
    param($wo, $projectPath)

    $ErrorActionPreference = "Stop"

    $conda = "conda.exe"   # or full path if needed
    $args  = @(
        "run", "-n", "pointfile",
        "python", "-m", "src.oiol2.main",
        "--wo", $wo
    )

    $p = Start-Process -FilePath $conda `
                       -ArgumentList $args `
                       -WorkingDirectory $projectPath `
                       -NoNewWindow `
                       -Wait `
                       -PassThru

    if ($p.ExitCode -ne 0) {
        Write-Host "Program failed with exit code $($p.ExitCode)"
        exit $p.ExitCode
    }

    Write-Host "Program succeeded"
    exit 0
}

Invoke-Command -ComputerName $remotePC -Credential $cred -ScriptBlock $script -ArgumentList $wo, $projectPath
exit $LASTEXITCODE