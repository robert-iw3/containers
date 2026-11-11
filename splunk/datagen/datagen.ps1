<#
.SYNOPSIS
  Template-driven Splunk event generator. Windows PowerShell 5.1 and
  PowerShell 7+, .NET built-ins only.

.DESCRIPTION
  The PowerShell port of datagen.py. Reads the same JSON templates and
  implements the same generators and transforms, so a Windows host with no
  Python can produce the same data as a Linux host.

  Templates are JSON because ConvertFrom-Json and Python's json module are
  both built in, which keeps this dependency-free on either platform.

  Nothing here uses a PowerShell 7-only construct: no ternary operator, no
  null-coalescing, no ConvertFrom-Json -AsHashtable, no [datetime]::UnixEpoch.

  Output is not byte-identical to datagen.py: the two runtimes have
  different RNGs. Record shapes, source types and volumes match.

  Volume matters on a metered licence: a download-trial or Free licence
  indexes 500 MB/day. Every run measures bytes first and -BudgetMB refuses
  to go past a ceiling.

.EXAMPLE
  .\datagen.ps1 -Tier medium -Out .\out -Index linux_lab

.EXAMPLE
  .\datagen.ps1 -Tier large -EstimateOnly
#>
[CmdletBinding()]
param(
    [string]   $Templates    = (Join-Path $PSScriptRoot 'templates'),
    [string]   $Out          = '.\datagen-out',
    [ValidateSet('tiny', 'small', 'medium', 'large')]
    [string]   $Tier         = 'small',
    [int]      $Records      = 0,
    [string[]] $Only         = @(),
    [double]   $WindowHours  = 2.0,
    [double]   $BudgetMB     = 150.0,
    [int]      $Seed         = 0,
    [double]   $NowEpoch     = 0,
    [string]   $Index        = 'main',
    [switch]   $EstimateOnly,
    [switch]   $List
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$TIERS = @{ tiny = 200; small = 2000; medium = 150000; large = 600000 }
$EPOCH = [datetime]::SpecifyKind((Get-Date '1970-01-01T00:00:00'), 'Utc')

if ($Seed -ne 0) { $script:RNG = New-Object System.Random -ArgumentList $Seed }
else { $script:RNG = New-Object System.Random }
$script:SeqState = @{}

# ------------------------------------------------------------------ helpers

function Test-Prop {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    return ($Object.PSObject.Properties.Name -contains $Name)
}

function Get-Prop {
    param($Object, [string]$Name, $Default = $null)
    if (Test-Prop $Object $Name) {
        $v = $Object.$Name
        if ($null -ne $v) { return $v }
    }
    return $Default
}

function Get-RandomInt {
    param([int]$Min, [int]$Max)   # inclusive, matching Python randint
    return $script:RNG.Next($Min, $Max + 1)
}

function Write-Preserved {
    # "return $x" enumerates an array. The comma operator stops that, so an
    # array-valued template variable such as argv arrives intact.
    param($Value)
    if ($Value -is [System.Array]) { return ,$Value }
    return $Value
}

function Select-Weighted {
    param($Values, $Weights)
    $items = @($Values)
    if ($null -eq $Weights) {
        return (Write-Preserved $items[(Get-RandomInt 0 ($items.Count - 1))])
    }
    $total = 0
    foreach ($w in $Weights) { $total += [int]$w }
    $pick = $script:RNG.NextDouble() * $total
    $acc = 0
    for ($i = 0; $i -lt $items.Count; $i++) {
        $acc += [int]$Weights[$i]
        if ($pick -le $acc) { return (Write-Preserved $items[$i]) }
    }
    return (Write-Preserved $items[$items.Count - 1])
}

function ConvertTo-HexString {
    param([string]$Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    return ([System.BitConverter]::ToString($bytes)).Replace('-', '')
}

function Get-Sha256Hex {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text))
        return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLower()
    } finally { $sha.Dispose() }
}

# --------------------------------------------------------------- transforms

function Invoke-Transform {
    param($Value, [string]$Name)
    switch ($Name) {
        'hexify' {
            $t = [string]$Value
            if ($t -match '[\s"]') { return (ConvertTo-HexString $t) }
            return '"' + $t + '"'
        }
        'audit_args' {
            $items = @($Value)
            $parts = @()
            for ($i = 0; $i -lt $items.Count; $i++) {
                $parts += ('a{0}="{1}"' -f $i, $items[$i])
            }
            return ($parts -join ' ')
        }
        'argc'       { return ([string](@($Value)).Count) }
        'join'       { return ((@($Value)) -join ' ') }
        'join_comma' { return ((@($Value)) -join ',') }
        'first'      { $a = @($Value); return [string]$a[0] }
        'basename'   {
            $t = ([string]$Value).Replace('\', '/').TrimEnd('/')
            $parts = $t -split '/'
            return $parts[$parts.Count - 1]
        }
        'dirname'    {
            $t = ([string]$Value).Replace('\', '/')
            $parts = @($t -split '/')
            if ($parts.Count -le 1) { return '/' }
            $head = $parts[0..($parts.Count - 2)] -join '/'
            if ([string]::IsNullOrEmpty($head)) { return '/' }
            return $head
        }
        'upper'      { return ([string]$Value).ToUpper() }
        'lower'      { return ([string]$Value).ToLower() }
        'xml'        {
            $t = [string]$Value
            $t = $t.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
            return $t.Replace('"', '&quot;')
        }
        'abspath'    {
            $t = [string]$Value
            if ($t.StartsWith('/') -or $t.StartsWith('C:') -or $t.StartsWith('\')) { return $t }
            return '/usr/bin/' + $t
        }
        default { throw "unknown transform: $Name" }
    }
}

# A MatchEvaluator scriptblock is PowerShell 6+, so matches are walked by hand.
$script:Placeholder = [regex]'\{([A-Za-z_][A-Za-z0-9_]*)((?:\|[a-z_0-9]+)*)\}'

function Expand-Line {
    param([string]$Line, [hashtable]$Ctx)
    $mc = $script:Placeholder.Matches($Line)
    if ($mc.Count -eq 0) { return $Line }
    $sb = New-Object System.Text.StringBuilder
    $pos = 0
    foreach ($m in $mc) {
        [void]$sb.Append($Line.Substring($pos, $m.Index - $pos))
        $name = $m.Groups[1].Value
        if (-not $Ctx.ContainsKey($name)) {
            throw "template references undefined variable: $name"
        }
        $value = $Ctx[$name]
        $chain = $m.Groups[2].Value
        if ($chain.Length -gt 0) {
            foreach ($step in ($chain -split '\|')) {
                if ($step.Length -gt 0) { $value = Invoke-Transform $value $step }
            }
        }
        [void]$sb.Append([string]$value)
        $pos = $m.Index + $m.Length
    }
    [void]$sb.Append($Line.Substring($pos))
    return $sb.ToString()
}

# --------------------------------------------------------------- generators

function Get-TimestampValue {
    param($Spec, [datetime]$Base)
    $fmt = [string](Get-Prop $Spec 'format' 'iso8601')
    switch ($fmt) {
        'epoch'    { return ([string][int64]($Base - $EPOCH).TotalSeconds) }
        'epoch_ms3' {
            $secs = ($Base - $EPOCH).TotalSeconds
            return $secs.ToString('F3', [System.Globalization.CultureInfo]::InvariantCulture)
        }
        'iso8601'   { return $Base.ToString('yyyy-MM-ddTHH:mm:ss.ffffff') + '+00:00' }
        'iso8601_z' { return $Base.ToString('yyyy-MM-ddTHH:mm:ss.ffffff') + 'Z' }
        'win_xml'   { return $Base.ToString('yyyy-MM-ddTHH:mm:ss.ffffff') + 'Z' }
        'syslog_rfc3164' { return $Base.ToString('MMM d HH:mm:ss') }
        'strftime'  {
            $pattern = [string](Get-Prop $Spec 'pattern' 'yyyy-MM-dd HH:mm:ss')
            return $Base.ToString($pattern)
        }
        default { throw "unknown timestamp format: $fmt" }
    }
}

function Resolve-Variable {
    param($Spec, [string]$QualifiedName, [hashtable]$Ctx, [datetime]$Now, [double]$OffsetSeconds)
    $kind = [string](Get-Prop $Spec 'gen' 'const')
    switch ($kind) {
        'const'  { return (Get-Prop $Spec 'value' '') }
        'choice' {
            $values = @(Get-Prop $Spec 'values' @())
            $weights = $null
            if (Test-Prop $Spec 'weights') { $weights = @($Spec.weights) }
            $picked = Select-Weighted $values $weights
            return (Write-Preserved $picked)
        }
        'int'    { return (Get-RandomInt ([int](Get-Prop $Spec 'min' 0)) ([int](Get-Prop $Spec 'max' 100))) }
        'float'  {
            $lo = [double](Get-Prop $Spec 'min' 0.0)
            $hi = [double](Get-Prop $Spec 'max' 1.0)
            $places = [int](Get-Prop $Spec 'places' 2)
            return [math]::Round($lo + ($script:RNG.NextDouble() * ($hi - $lo)), $places)
        }
        'hex'    {
            $width = [int](Get-Prop $Spec 'width' 12)
            $chars = '0123456789abcdef'
            $sb = New-Object System.Text.StringBuilder
            for ($i = 0; $i -lt $width; $i++) {
                [void]$sb.Append($chars[(Get-RandomInt 0 15)])
            }
            return $sb.ToString()
        }
        'ipv4'   {
            $prefix = [string](Get-Prop $Spec 'prefix' '10')
            $octets = @($prefix -split '\.' | Where-Object { $_ -ne '' })
            while ($octets.Count -lt 4) { $octets += [string](Get-RandomInt 1 254) }
            return (($octets[0..3]) -join '.')
        }
        'uuid'        { return ([guid]::NewGuid()).ToString() }
        'guid_braced' { return '{' + ([guid]::NewGuid()).ToString() + '}' }
        'sequence' {
            $step = [int](Get-Prop $Spec 'step' 1)
            $jitter = [int](Get-Prop $Spec 'jitter' 0)
            if (-not $script:SeqState.ContainsKey($QualifiedName)) {
                $script:SeqState[$QualifiedName] = [int64](Get-Prop $Spec 'start' 1)
            }
            $cur = $script:SeqState[$QualifiedName]
            $next = $cur + $step
            if ($jitter -gt 0) { $next += (Get-RandomInt 0 $jitter) }
            $script:SeqState[$QualifiedName] = $next
            return $cur
        }
        'timestamp' { return (Get-TimestampValue $Spec $Now.AddSeconds(-1 * $OffsetSeconds)) }
        'sha256_of' {
            $of = [string](Get-Prop $Spec 'of' '')
            $src = ''
            if ($Ctx.ContainsKey($of)) { $src = [string]$Ctx[$of] }
            $len = [int](Get-Prop $Spec 'length' 64)
            $digest = Get-Sha256Hex $src
            if ($len -ge $digest.Length) { return $digest }
            return $digest.Substring(0, $len)
        }
        'compose' { return (Expand-Line ([string](Get-Prop $Spec 'value' '')) $Ctx) }
        default   { throw "unknown generator: $kind" }
    }
}

# ---------------------------------------------------------------- templates

function Import-Templates {
    param([string]$Path)
    if (Test-Path -Path $Path -PathType Container) {
        $files = @(Get-ChildItem -Path $Path -Filter '*.json' | Sort-Object Name)
    } else {
        $files = @(Get-Item -Path $Path)
    }
    $result = @()
    foreach ($f in $files) {
        if ($f.Name -eq 'manifest.json') { continue }
        try {
            $t = Get-Content -Path $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            throw ("{0}: invalid JSON: {1}" -f $f.FullName, $_.Exception.Message)
        }
        foreach ($k in @('name', 'sourcetype', 'records')) {
            if (-not (Test-Prop $t $k)) {
                throw ("{0}: template missing required key: {1}" -f $f.FullName, $k)
            }
        }
        if (@($t.records).Count -eq 0) {
            throw ("{0}: 'records' must be a non-empty list" -f $f.FullName)
        }
        $outFile = Get-Prop $t 'output_file' $null
        if ($null -eq $outFile) {
            $outFile = ([regex]'[^A-Za-z0-9_.-]').Replace([string]$t.sourcetype, '_') + '.log'
        }
        $result += [pscustomobject]@{
            Name       = [string]$t.name
            Sourcetype = [string]$t.sourcetype
            Origin     = [string](Get-Prop $t 'origin' '-')
            OutputFile = [string]$outFile
            Weight     = [int](Get-Prop $t 'weight' 10)
            Variables  = (Get-Prop $t 'variables' $null)
            Records    = @($t.records)
            File       = $f.FullName
        }
    }
    if ($result.Count -eq 0) { throw "no templates found in $Path" }
    return $result
}

function New-RecordGroup {
    param($Template, [datetime]$Now, [double]$WindowSeconds)
    $records = $Template.Records
    $weights = @()
    foreach ($r in $records) { $weights += [int](Get-Prop $r 'weight' 10) }
    $rec = Select-Weighted $records $weights

    $ctx = @{}
    $offset = $script:RNG.NextDouble() * $WindowSeconds

    $varSets = @()
    if ($null -ne $Template.Variables) { $varSets += $Template.Variables }
    $recVars = Get-Prop $rec 'variables' $null
    if ($null -ne $recVars) { $varSets += $recVars }

    foreach ($set in $varSets) {
        foreach ($prop in $set.PSObject.Properties) {
            $qualified = $Template.Name + '.' + $prop.Name
            $ctx[$prop.Name] = Resolve-Variable $prop.Value $qualified $ctx $Now $offset
        }
    }

    # Returned unwrapped: the caller collects with @(), which handles both a
    # multi-line group and a single-line record. Adding a comma here as well
    # nests the array and the whole group collapses into one string.
    $lines = @()
    foreach ($line in @($rec.lines)) { $lines += (Expand-Line ([string]$line) $ctx) }
    return $lines
}

# --------------------------------------------------------------------- main

$templateList = Import-Templates -Path $Templates

if ($Only.Count -gt 0) {
    $templateList = @($templateList | Where-Object { $Only -contains $_.Name })
    if ($templateList.Count -eq 0) { throw "no template matched -Only $($Only -join ', ')" }
}

if ($List) {
    '{0,-24} {1,-52} {2,3}  {3}' -f 'name', 'sourcetype', 'wt', 'origin'
    foreach ($t in $templateList) {
        '{0,-24} {1,-52} {2,3}  {3}' -f $t.Name, $t.Sourcetype, $t.Weight, $t.Origin
    }
    exit 0
}

$target = $TIERS[$Tier]
if ($Records -gt 0) { $target = $Records }

if ($NowEpoch -gt 0) { $now = $EPOCH.AddSeconds($NowEpoch) }
else { $now = [datetime]::UtcNow }
$windowSeconds = $WindowHours * 3600

$pool = @()
foreach ($t in $templateList) {
    $w = [math]::Max(1, $t.Weight)
    for ($i = 0; $i -lt $w; $i++) { $pool += $t }
}

$buffers = @{}
foreach ($t in $templateList) { $buffers[$t.Name] = New-Object System.Collections.ArrayList }

$emitted = 0
$guard = 0
$guardMax = ($target * 20) + 1000
while ($emitted -lt $target -and $guard -lt $guardMax) {
    $guard++
    $t = $pool[(Get-RandomInt 0 ($pool.Count - 1))]
    $lines = @(New-RecordGroup $t $now $windowSeconds)
    foreach ($l in $lines) { [void]$buffers[$t.Name].Add($l) }
    $emitted += $lines.Count
}

$byName = @{}
foreach ($t in $templateList) { $byName[$t.Name] = $t }

$sizes = @{}
$totalBytes = 0
$totalRecords = 0
foreach ($name in $buffers.Keys) {
    $b = 0
    foreach ($l in $buffers[$name]) { $b += [System.Text.Encoding]::UTF8.GetByteCount($l) + 1 }
    $sizes[$name] = $b
    $totalBytes += $b
    $totalRecords += $buffers[$name].Count
}

'{0,-24} {1,-52} {2,9} {3,8}' -f 'template', 'sourcetype', 'records', 'MB'
foreach ($name in ($buffers.Keys | Sort-Object)) {
    if ($buffers[$name].Count -eq 0) { continue }
    '{0,-24} {1,-52} {2,9:N0} {3,8:N2}' -f `
        $name, $byName[$name].Sourcetype, $buffers[$name].Count, ($sizes[$name] / 1MB)
}
'{0,-24} {1,-52} {2,9:N0} {3,8:N2}' -f 'TOTAL', '', $totalRecords, ($totalBytes / 1MB)

$usedMB = $totalBytes / 1MB
$pct = 0
if ($BudgetMB -gt 0) { $pct = ($usedMB / $BudgetMB) * 100 }
''
'budget {0:N0} MB, {1:N1}% used. 500 MB/day is the download-trial and Free licence cap.' -f $BudgetMB, $pct

if ($BudgetMB -gt 0 -and $usedMB -gt $BudgetMB) {
    throw ("REFUSED: {0:N1} MB exceeds -BudgetMB {1:N0}. Lower -Tier or raise the budget deliberately." -f $usedMB, $BudgetMB)
}

if ($EstimateOnly) {
    ''
    '-EstimateOnly: nothing written'
    exit 0
}

if (-not (Test-Path -Path $Out)) { [void](New-Item -ItemType Directory -Path $Out -Force) }
$outRoot = (Resolve-Path -Path $Out).Path
$utf8 = New-Object System.Text.UTF8Encoding $false

$outputs = @{}
foreach ($name in ($buffers.Keys | Sort-Object)) {
    if ($buffers[$name].Count -eq 0) { continue }
    $path = Join-Path $outRoot $byName[$name].OutputFile
    $text = ($buffers[$name] -join "`n") + "`n"
    [System.IO.File]::WriteAllText($path, $text, $utf8)
    $outputs[$name] = [ordered]@{
        path       = $path
        file       = $byName[$name].OutputFile
        sourcetype = $byName[$name].Sourcetype
        records    = $buffers[$name].Count
        bytes      = $sizes[$name]
        sha256     = (Get-FileHash -Path $path -Algorithm SHA256).Hash.ToLower()
    }
}

$manifest = [ordered]@{
    generated_at  = $now.ToString('yyyy-MM-ddTHH:mm:ss.ffffffZ')
    generator     = 'datagen.ps1'
    seed          = $Seed
    tier          = $(if ($Records -gt 0) { "custom:$Records" } else { $Tier })
    window_hours  = $WindowHours
    total_records = $totalRecords
    total_bytes   = $totalBytes
    index         = $Index
    outputs       = $outputs
}
$manifestPath = Join-Path $outRoot 'manifest.json'
[System.IO.File]::WriteAllText($manifestPath,
    ($manifest | ConvertTo-Json -Depth 6), $utf8)

$stanzas = New-Object System.Collections.ArrayList
[void]$stanzas.Add('# Generated by datagen.ps1. Point a forwarder at these files.')
[void]$stanzas.Add('# Paths are where the data was written; adjust if you move it.')
foreach ($name in ($outputs.Keys | Sort-Object)) {
    [void]$stanzas.Add('')
    [void]$stanzas.Add('[monitor://' + $outputs[$name].path + ']')
    [void]$stanzas.Add('sourcetype = ' + $outputs[$name].sourcetype)
    [void]$stanzas.Add('index = ' + $Index)
    [void]$stanzas.Add('disabled = 0')
    [void]$stanzas.Add('crcSalt = <SOURCE>')
}
[System.IO.File]::WriteAllText((Join-Path $outRoot 'inputs.conf'),
    (($stanzas -join "`n") + "`n"), $utf8)

''
'wrote {0} log files, manifest.json and inputs.conf to {1}' -f $outputs.Count, $outRoot
exit 0
