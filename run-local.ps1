param([ValidateSet('start','status','stop')][string]$Action='start')
$ErrorActionPreference='Stop'
$ProjectDir=$PSScriptRoot
$VenvDir=Join-Path $ProjectDir '.venv'
$Python=Join-Path $VenvDir 'Scripts\python.exe'
$Runtime=Join-Path $ProjectDir '.runtime'
$PidFile=Join-Path $Runtime 'services.json'
$FrontendPidFile=Join-Path $Runtime 'frontend.pid'
$Services=@(
    @{Name='user_service';Port=8001},
    @{Name='restaurant_service';Port=8002},
    @{Name='order_service';Port=8003},
    @{Name='payment_service';Port=8004},
    @{Name='delivery_service';Port=8005},
    @{Name='notification_service';Port=8006}
)

function Test-Healthy([int]$Port) {
    try { $r=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2; return $r.status -eq 'ok' }
    catch { return $false }
}
function Show-Status {
    foreach($s in $Services) {
        $state=if(Test-Healthy $s.Port){'RUNNING'}else{'STOPPED'}
        Write-Host ("{0,-22} {1,-8} http://127.0.0.1:{2}/docs" -f $s.Name,$state,$s.Port)
    }
    $web=try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8080' -TimeoutSec 2).StatusCode -eq 200 } catch { $false }
    $webState=if($web){'RUNNING'}else{'STOPPED'}
    Write-Host ("{0,-22} {1,-8} http://127.0.0.1:8080" -f 'frontend',$webState)
}
function Start-Project {
    if(-not (Test-Path -LiteralPath $Python)) {
        $cmd=Get-Command python -ErrorAction SilentlyContinue
        if(-not $cmd){throw 'Install Python 3 and add it to PATH.'}
        & $cmd.Source -m venv $VenvDir
        if($LASTEXITCODE -ne 0){throw 'Could not create the Python virtual environment.'}
        & $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectDir 'requirements.txt')
        if($LASTEXITCODE -ne 0){throw 'Could not install Python dependencies.'}
    }
    New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
    $env:USER_URL='http://127.0.0.1:8001'; $env:RESTAURANT_URL='http://127.0.0.1:8002'
    $env:PAYMENT_URL='http://127.0.0.1:8004'; $env:DELIVERY_URL='http://127.0.0.1:8005'; $env:NOTIFICATION_URL='http://127.0.0.1:8006'
    $started=@()
    foreach($s in $Services) {
        if(Test-Healthy $s.Port){continue}
        $work=Join-Path $Runtime $s.Name; New-Item -ItemType Directory -Force -Path $work | Out-Null
        $appDir = '"' + (Join-Path $ProjectDir $s.Name) + '"'
        $proc=Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app:app','--app-dir',$appDir,'--host','127.0.0.1','--port',[string]$s.Port) -WorkingDirectory $work -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime "$($s.Name).out.log") -RedirectStandardError (Join-Path $Runtime "$($s.Name).err.log") -PassThru
        $started+=@{Name=$s.Name;Port=$s.Port;Pid=$proc.Id}
    }
    if($started.Count -gt 0) { $started | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding utf8 }
    $ready=$false
    for($i=0;$i -lt 40;$i++) { if(@($Services | Where-Object { -not (Test-Healthy $_.Port) }).Count -eq 0){$ready=$true;break}; Start-Sleep -Milliseconds 500 }
    if(-not $ready){throw "Not all services became healthy. Check logs in $Runtime"}
    if(-not (Test-Path -LiteralPath $FrontendPidFile)) {
        $frontDir = '"' + (Join-Path $ProjectDir 'frontend') + '"'
        $webProcess=Start-Process -FilePath $Python -ArgumentList @('-m','http.server','8080','--bind','127.0.0.1','--directory',$frontDir) -WorkingDirectory $Runtime -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Runtime 'frontend.out.log') -RedirectStandardError (Join-Path $Runtime 'frontend.err.log') -PassThru
        Set-Content -LiteralPath $FrontendPidFile -Value $webProcess.Id -Encoding ascii
    }
    Show-Status
}
function Stop-Project {
    if(Test-Path -LiteralPath $PidFile) {
        $raw=Get-Content -LiteralPath $PidFile -Raw
        if(-not [string]::IsNullOrWhiteSpace($raw)) {
            $items=@($raw | ConvertFrom-Json)
            foreach($item in $items){ Stop-Process -Id $item.Pid -Force -ErrorAction SilentlyContinue }
        }
        Remove-Item -LiteralPath $PidFile -Force
    }
    if(Test-Path -LiteralPath $FrontendPidFile) {
        $webPid=Get-Content -LiteralPath $FrontendPidFile -Raw
        if($webPid){Stop-Process -Id ([int]$webPid) -Force -ErrorAction SilentlyContinue}
        Remove-Item -LiteralPath $FrontendPidFile -Force
    }
    Show-Status
}
switch($Action){'start'{Start-Project};'status'{Show-Status};'stop'{Stop-Project}}
