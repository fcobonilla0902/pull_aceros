$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $PSScriptRoot 'manuales_build'
$word = $null
$owned = $false
$results = @()
try {
    try { $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application') }
    catch { $word = New-Object -ComObject Word.Application; $word.Visible = $false; $owned = $true }
    foreach ($name in @('Manual_Tecnico_MetaRide', 'Manual_Usuario_MetaRide')) {
        $docPath = Join-Path $repoRoot ('docs\' + $name + '.docx')
        $pdfPath = Join-Path $buildRoot ($name + '.pdf')
        $document = $null
        $openedHere = $false
        for ($i = 1; $i -le $word.Documents.Count; $i++) {
            if ($word.Documents.Item($i).FullName -eq $docPath) { $document = $word.Documents.Item($i); break }
        }
        if ($null -eq $document) { $document = $word.Documents.Open($docPath, $false, $false); $openedHere = $true }
        Write-Output ('Abierto: ' + $name)
        if ($name -eq 'Manual_Usuario_MetaRide') {
            # Sustituye solo la figura de opciones por su captura completa.
            Add-Type -AssemblyName System.Drawing
            $imagePath = Join-Path $repoRoot 'docs\capturas\18_simulacion_opciones.png'
            $image = [System.Drawing.Image]::FromFile($imagePath)
            try { $widthCm = [Math]::Min(16.0, 19.0 * $image.Width / $image.Height) }
            finally { $image.Dispose() }
            $shape = $document.InlineShapes.Item(21)
            $anchor = $shape.Range.Duplicate
            $shape.Delete()
            $newShape = $document.InlineShapes.AddPicture($imagePath, $false, $true, $anchor)
            $newShape.LockAspectRatio = -1
            $newShape.Width = $widthCm * 72 / 2.54
        }
        $document.Content.LanguageID = 2058
        # Actualiza por índice sin invalidar un enumerador de la colección COM.
        if ($document.TablesOfContents.Count -gt 0) { $document.TablesOfContents.Item(1).Update() }
        Write-Output ('Indice actualizado: ' + $name)
        $document.Repaginate()
        if ($document.TablesOfContents.Count -gt 0) { $document.TablesOfContents.Item(1).UpdatePageNumbers() }
        for ($s = 1; $s -le $document.Sections.Count; $s++) {
            [void]$document.Sections.Item($s).Footers.Item(1).Range.Fields.Update()
        }
        $document.Save()
        $pages = $document.ComputeStatistics(2)
        Write-Output ('Guardado: ' + $pages + ' paginas')
        $document.ExportAsFixedFormat($pdfPath, 17)
        Write-Output ('PDF verificado: ' + $name)
        $results += [pscustomobject]@{file=$name+'.docx';word_opened=$true;pages=$pages;toc_count=$document.TablesOfContents.Count;inline_images=$document.InlineShapes.Count;pdf=$pdfPath}
        if ($openedHere) { $document.Close(0) }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    [System.IO.File]::WriteAllText((Join-Path $buildRoot 'word_verification.json'), (ConvertTo-Json -InputObject @($results) -Depth 5), [System.Text.UTF8Encoding]::new($false))
}
finally {
    if ($null -ne $word) {
        if ($owned -and $word.Documents.Count -eq 0) { $word.Quit() }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
}
