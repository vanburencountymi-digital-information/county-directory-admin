# Create the `directory` database on existing Cloud SQL instance db-dice.
# Do not create a separate instance. Do not run Django migrations against
# the `postgres` database (Sqitch / core.* live there).
$ErrorActionPreference = "Stop"
$Project = if ($env:PROJECT) { $env:PROJECT } else { "core-db-475718" }
$Instance = if ($env:INSTANCE) { $env:INSTANCE } else { "db-dice" }
$DbName = if ($env:DB_NAME) { $env:DB_NAME } else { "directory" }

Write-Host "Using project $Project, instance $Instance, database $DbName"
gcloud config set project $Project

try {
  gcloud sql instances describe $Instance --project $Project | Out-Null
} catch {
  Write-Error "Instance $Instance not found. Refusing to create a new instance."
  exit 1
}

$dbExists = $true
try {
  gcloud sql databases describe $DbName --instance $Instance --project $Project | Out-Null
} catch {
  $dbExists = $false
}
if (-not $dbExists) {
  gcloud sql databases create $DbName --instance $Instance --project $Project
} else {
  Write-Host "Database $DbName already exists on $Instance."
}

function Ensure-Secret([string]$Name) {
  try {
    gcloud secrets describe $Name --project $Project | Out-Null
    Write-Host "Secret $Name exists."
  } catch {
    Write-Host "Creating placeholder secret $Name (replace the value before serving traffic)."
    $bytes = New-Object byte[] 36
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $val = [Convert]::ToBase64String($bytes)
    $val | gcloud secrets create $Name --project $Project --data-file=-
  }
}

Ensure-Secret DIRECTORY_DJANGO_SECRET_KEY
Ensure-Secret DIRECTORY_SYNC_API_SECRET
Ensure-Secret DIRECTORY_DATABASE_URL

Write-Host ""
Write-Host "Next: set DIRECTORY_DATABASE_URL to db-dice / database directory (unix socket)."
Write-Host "ETL SOURCE_DATABASE_URL points at db-dice / postgres (core.*)."
Write-Host "See docs/STAGING.md"
