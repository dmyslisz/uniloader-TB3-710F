param(
    [Parameter(Mandatory = $true)][string]$OriginalBoot,
    [Parameter(Mandatory = $true)][string]$LoaderZImage,
    [Parameter(Mandatory = $true)][string]$OutputBoot
)

$ErrorActionPreference = 'Stop'

function Read-U32([byte[]]$Bytes, [int]$Offset) {
    return [BitConverter]::ToUInt32($Bytes, $Offset)
}

function Align-Up([long]$Value, [long]$Alignment) {
    return [long](($Value + $Alignment - 1) -band (-bnot ($Alignment - 1)))
}

function Copy-Range([byte[]]$Bytes, [long]$Offset, [long]$Length) {
    if ($Offset -lt 0 -or $Length -lt 0 -or ($Offset + $Length) -gt $Bytes.LongLength) {
        throw 'Boot image component lies outside the input image.'
    }
    $part = [byte[]]::new([int]$Length)
    [Array]::Copy($Bytes, [int]$Offset, $part, 0, [int]$Length)
    return ,$part
}

$original = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $OriginalBoot))
$kernel = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LoaderZImage))
if ($original.Length -lt 1632 -or [Text.Encoding]::ASCII.GetString($original, 0, 8) -ne 'ANDROID!') {
    throw 'Input is not a supported Android boot image.'
}
if ($kernel.Length -le 0x28 -or (Read-U32 $kernel 0x24) -ne 0x016F2818) {
    throw 'Loader file lacks the Linux zImage magic at offset 0x24.'
}

$page = Read-U32 $original 36
if ($page -lt 1632 -or ($page -band ($page - 1)) -ne 0) {
    throw "Unsupported Android boot page size: $page"
}
if ((Read-U32 $original 44) -ne 0) {
    throw 'Unknown nonzero legacy boot header field; refusing to repack.'
}

$kernelSize = Read-U32 $original 8
$ramdiskSize = Read-U32 $original 16
$secondSize = Read-U32 $original 24
$dtSize = Read-U32 $original 40
$ramdiskOffset = $page + (Align-Up $kernelSize $page)
$secondOffset = $ramdiskOffset + (Align-Up $ramdiskSize $page)
$dtOffset = $secondOffset + (Align-Up $secondSize $page)
$ramdisk = Copy-Range $original $ramdiskOffset $ramdiskSize
$second = Copy-Range $original $secondOffset $secondSize
$dt = Copy-Range $original $dtOffset $dtSize

$stream = [IO.MemoryStream]::new()
$writer = [IO.BinaryWriter]::new($stream)
$writer.Write((Copy-Range $original 0 $page))
$writer.BaseStream.Position = 8
$writer.Write([uint32]$kernel.Length)
$writer.BaseStream.Position = $page
$writer.Write($kernel)
$writer.Write([byte[]]::new([int]((Align-Up $kernel.Length $page) - $kernel.Length)))
$writer.Write($ramdisk)
$writer.Write([byte[]]::new([int]((Align-Up $ramdiskSize $page) - $ramdiskSize)))
$writer.Write($second)
$writer.Write([byte[]]::new([int]((Align-Up $secondSize $page) - $secondSize)))
$writer.Write($dt)
$writer.Write([byte[]]::new([int]((Align-Up $dtSize $page) - $dtSize)))

if ($stream.Length -gt $original.Length) {
    throw "New image exceeds original partition size ($($original.Length) bytes)."
}
$writer.Write([byte[]]::new([int]($original.Length - $stream.Length)))
$writer.Flush()
[IO.File]::WriteAllBytes($OutputBoot, $stream.ToArray())
$writer.Dispose()
$stream.Dispose()

Write-Host "Created $OutputBoot ($($original.Length) bytes). No device was flashed."

