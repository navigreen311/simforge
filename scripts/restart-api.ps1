# Restart the SimForge API, preserving what the last launch recorded (ADR-0104 rulings 2 and 3).
#
# TWO DEFECTS THIS EXISTS TO PREVENT, both of them real:
#
#   1. On 21 September 2026 a restart was done with `Start-Process -RedirectStandardOutput`.
#      PowerShell TRUNCATES that file. The previous launch's entire record - its startup line, its
#      scheduler jobs, every sweep it had run - was destroyed by the act of replacing it, and the
#      forensic question being asked that evening lost its only remaining source.
#
#   2. The same restart captured PID and command line for the two processes it killed, and not
#      their CreationDate. Once they were gone there was no way to date them, and the process
#      identity had to be inferred from `started_commit` on an endpoint that was already dead.
#
# So: ROTATE, never truncate. And write down both processes - launcher and child - BEFORE killing
# anything, because after the kill there is nothing left to ask.
#
# A NOTE ON THE PAIR. `.venv\Scripts\python.exe` is a launcher that spawns the base interpreter,
# so one uvicorn launch is always two processes: the launcher, and a child holding the socket
# whose ExecutablePath is the SYSTEM Python. That pair is not two launches and not a stray
# process - reading it as one cost an investigation an hour. Both are recorded.

[CmdletBinding()]
param(
    [int]    $Port    = 8110,
    [string] $ApiDir  = "$PSScriptRoot\..\apps\api",
    [string] $LogDir  = "$PSScriptRoot\..\..",
    [switch] $NoStart
)

$ErrorActionPreference = 'Stop'
$ApiDir  = (Resolve-Path $ApiDir).Path
$LogDir  = (Resolve-Path $LogDir).Path
$stamp   = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$log     = Join-Path $LogDir "simforge-api-$Port.log"
$err     = Join-Path $LogDir "simforge-api-$Port.err"
$ledger  = Join-Path $LogDir "simforge-api-$Port.restarts.jsonl"

# --- 1 - Who is running, in full, before anything is killed -------------------------------------
# Matched by command line rather than by port: the launcher does not hold the socket, and killing
# the child alone leaves a launcher that owns nothing and answers nothing.
$running = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*--port $Port*" } |
    Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine)

$before = @($running | ForEach-Object {
    [ordered]@{
        pid             = $_.ProcessId
        parent_pid      = $_.ParentProcessId
        # THE FIELD THE 21 SEPTEMBER RESTART DID NOT CAPTURE.
        created_at      = if ($_.CreationDate) {
                              $_.CreationDate.ToUniversalTime().ToString('o')
                          } else { $null }
        executable_path = $_.ExecutablePath
        command_line    = $_.CommandLine
        role            = if ($_.ExecutablePath -like "*\.venv\*") { 'launcher' } else { 'child' }
    }
})

if ($before.Count -gt 0) {
    Write-Host "Stopping $($before.Count) process(es) on port ${Port}:"
    $before | ForEach-Object {
        Write-Host ("  {0,-8} pid {1,-7} parent {2,-7} created {3}" -f
                    $_.role, $_.pid, $_.parent_pid, $_.created_at)
    }
} else {
    Write-Host "Nothing running on port $Port."
}

# --- 2 - Rotate the logs. NEVER truncate --------------------------------------------------------
# A rename, not a copy: the old bytes are never rewritten, so a rotation that fails part way
# leaves the original whole rather than half of it.
foreach ($file in @($log, $err)) {
    if (Test-Path $file) {
        $rotated = [IO.Path]::ChangeExtension($file, $null).TrimEnd('.') + ".$stamp" +
                   [IO.Path]::GetExtension($file)
        Move-Item -LiteralPath $file -Destination $rotated
        Write-Host "Rotated $(Split-Path $file -Leaf) -> $(Split-Path $rotated -Leaf)"
    }
}

# --- 3 - Stop them, child first -----------------------------------------------------------------
foreach ($proc in ($before | Sort-Object { $_.role } -Descending)) {
    Stop-Process -Id $proc.pid -Force -ErrorAction SilentlyContinue
}
if ($before.Count -gt 0) { Start-Sleep -Seconds 2 }

# --- 4 - Start, and record BOTH halves of the new pair ------------------------------------------
$after = @()
if (-not $NoStart) {
    $python = Join-Path $ApiDir ".venv\Scripts\python.exe"
    Start-Process -FilePath $python `
        -ArgumentList "-m","uvicorn","src.main:app","--host","127.0.0.1","--port","$Port" `
        -WorkingDirectory $ApiDir `
        -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden
    Start-Sleep -Seconds 12

    $after = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
        Where-Object { $_.CommandLine -like "*uvicorn*" -and $_.CommandLine -like "*--port $Port*" } |
        ForEach-Object {
            [ordered]@{
                pid             = $_.ProcessId
                parent_pid      = $_.ParentProcessId
                created_at      = $_.CreationDate.ToUniversalTime().ToString('o')
                executable_path = $_.ExecutablePath
                role            = if ($_.ExecutablePath -like "*\.venv\*") { 'launcher' }
                                  else { 'child' }
            }
        })

    Write-Host "Started $($after.Count) process(es):"
    $after | ForEach-Object {
        Write-Host ("  {0,-8} pid {1,-7} parent {2,-7} created {3}" -f
                    $_.role, $_.pid, $_.parent_pid, $_.created_at)
    }
}

# --- 5 - Append the restart to a ledger that is never rotated -----------------------------------
# One line per restart, appended. This file is the thing that survives: it holds the pairs a later
# question will need, after the logs have rotated and the processes are gone.
$commit = (& git -C (Split-Path $ApiDir -Parent | Split-Path -Parent) rev-parse HEAD 2>$null)
$record = [ordered]@{
    restarted_at   = (Get-Date).ToUniversalTime().ToString('o')
    port           = $Port
    checkout_commit = if ($commit) { $commit.Trim() } else { $null }
    stopped        = $before
    started        = $after
    rotated_to     = $stamp
}
# UTF-8 with NO byte-order mark, appended. `Add-Content -Encoding UTF8` in Windows PowerShell
# writes a BOM, and a BOM in the middle of a JSONL file is a parse error for the next reader.
$line = ($record | ConvertTo-Json -Depth 6 -Compress) + [Environment]::NewLine
[IO.File]::AppendAllText($ledger, $line, (New-Object Text.UTF8Encoding $false))
Write-Host "Recorded in $(Split-Path $ledger -Leaf)"
