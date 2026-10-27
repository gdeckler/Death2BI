$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& docker --context desktop-linux version
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running in Linux containers mode, and this terminal must have engine access.' }
& docker --context desktop-linux build --platform linux/amd64 --pull --tag death2bi:latest .
if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed.' }
$smokeName = 'death2bi-smoke-' + [guid]::NewGuid().ToString('N').Substring(0,12)
try {
    $portListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,0)
    try { $portListener.Start(); $port=$portListener.LocalEndpoint.Port } finally { $portListener.Stop() }
    $origin = 'http://127.0.0.1:' + $port
    & docker --context desktop-linux run --detach --name $smokeName --publish "127.0.0.1:${port}:8765" --env "D2PBI_BASE_URL=$origin" death2bi:latest | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the clean smoke-test container.' }
    $headers = @{ Origin=$origin }
    $ready = $false
    for ($attempt=0; $attempt -lt 45; $attempt++) {
        try { $health=Invoke-RestMethod -Uri ($origin+'/api/health') -Headers $headers; if ($health.ok) { $ready=$true; break } } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { & docker --context desktop-linux logs $smokeName; throw 'Container did not become ready.' }
    $providers=Invoke-RestMethod -Uri ($origin+'/api/auth/providers') -Headers $headers
    if (@($providers.providers).Count -ne 0) { throw 'Clean image unexpectedly has a configured identity provider.' }
    $session=New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $login=Invoke-RestMethod -Uri ($origin+'/api/auth/login') -Method Post -Headers $headers -ContentType application/json -Body '{"username":"admin","password":"Death2PowerBI!"}' -WebSession $session
    $accounts=Invoke-RestMethod -Uri ($origin+'/api/admin/accounts') -Headers $headers -WebSession $session
    if (@($accounts).Count -ne 1 -or $accounts[0].username -ne 'admin') { throw 'Clean image contains unexpected accounts.' }
    $reports=Invoke-RestMethod -Uri ($origin+'/api/models') -Headers $headers -WebSession $session
    if ($reports -and @($reports).Count -ne 0) { throw 'Clean image contains saved reports.' }
    Write-Host 'PASS: clean container starts, default admin signs in, no saved reports or federated providers.'
} finally {
    & docker --context desktop-linux rm --force --volumes $smokeName | Out-Null
}
& docker --context desktop-linux image inspect death2bi:latest --format 'Installed image: {{.Id}}'
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the built image.' }
Write-Host 'The image is now available in Docker Desktop > Images as death2bi:latest.'
Write-Host 'To run it: docker --context desktop-linux compose up -d'
Write-Host 'Then open http://127.0.0.1:8766'
