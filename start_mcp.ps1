# start_mcp.ps1 — temporary debug version
Get-Content ".\.env" | ForEach-Object {
    if ($_ -match "^\s*([^#=][^=]*)=(.+)$") {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        Write-Host "Set: $key"
    }
}

Write-Host "`n--- Verifying ---"
Write-Host "JIRA_URL            = $env:JIRA_URL"
Write-Host "JIRA_API_TOKEN = $env:JIRA_API_TOKEN"
Write-Host "-----------------`n"

if (-not $env:JIRA_URL -or -not $env:JIRA_API_TOKEN) {
    Write-Host "ERROR: One or both variables are empty. Check your .env file."
    exit 1
}

$env:PYTHONPATH = "src"
# py -m mcp_atlassian --transport streamable-http --host 0.0.0.0 --port 8080 --read-only -vv
py -m mcp_atlassian --port 8080 -vv