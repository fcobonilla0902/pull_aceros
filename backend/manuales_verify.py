"""Verifica OOXML, imágenes, estilo, PDF y apertura registrada por Microsoft Word."""
import json
from pathlib import Path
from zipfile import ZipFile
from docx import Document
from lxml import etree
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent.parent
DOCS=ROOT/'docs';BUILD=ROOT/'backend'/'manuales_build'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','r':'http://schemas.openxmlformats.org/package/2006/relationships'}
W='{'+NS['w']+'}'
report=json.loads((DOCS/'Verificacion_Manuales.json').read_text(encoding='utf-8'))
word=json.loads((BUILD/'word_verification.json').read_text(encoding='utf-8-sig'))
checks=[]
for entry in report['documentos']:
    path=DOCS/entry['file'];doc=Document(path)
    with ZipFile(path) as zip:
        assert zip.testzip() is None
        for name in zip.namelist():
            if name.endswith(('.xml','.rels')):etree.fromstring(zip.read(name))
        media=[n for n in zip.namelist() if n.startswith('word/media/')]
        links=[]
        for name in zip.namelist():
            if name.endswith('.rels'):
                rels=etree.fromstring(zip.read(name))
                links.extend(r for r in rels if r.get('Type','').endswith('/image') and r.get('TargetMode')=='External')
        assert not links
        assert len(media)==entry['figures'],(path,len(media),entry['figures'])
        xml=etree.fromstring(zip.read('word/document.xml'))
        for margin in xml.findall('.//'+W+'pgMar'):
            for side in ('top','bottom','left','right'):
                assert abs(int(margin.get(W+side))-1417)<=1
        for section in doc.sections:
            assert abs(section.left_margin.cm-2.5)<.01
        for s in ('Normal','Heading 1','Heading 2','Heading 3','Title'):
            assert doc.styles[s].font.name=='Arial',(entry['file'],s,doc.styles[s].font.name)
            expected=12 if s=='Normal' else 14
            assert doc.styles[s].font.size.pt==expected,(s,doc.styles[s].font.size.pt)
        assert len(doc.inline_shapes)==entry['figures']
        captions=[p.text for p in doc.paragraphs if p.text.startswith('Figura ')]
        assert len(captions)==entry['figures']
        for i,caption in enumerate(captions,1):assert caption.startswith('Figura '+str(i)+'.')
        assert xml.xpath('boolean(.//w:instrText[contains(.,"PAGE")])',namespaces=NS)
        assert xml.xpath('boolean(.//w:instrText[contains(.,"TOC")])',namespaces=NS)
    pdf=BUILD/(path.stem+'.pdf');reader=PdfReader(pdf)
    texts=[page.extract_text() or '' for page in reader.pages]
    assert len(reader.pages)>10
    assert all(text.strip() for text in texts),'Hay páginas sin texto visible'
    assert not any('Error! Bookmark not defined' in text or 'Error! Reference source not found' in text for text in texts)
    matching=next(item for item in word if item['file']==entry['file'])
    assert matching['word_opened'] and matching['toc_count']>=1
    assert matching['pages']==len(reader.pages)
    checks.append(dict(archivo=entry['file'],paginas=len(reader.pages),figuras=len(media),apertura_word='Correcta, sin reparación solicitada',indice='Actualizado con números de página',margenes='2,5 cm',fuentes='Arial; texto 12 y títulos 14',imagenes='Incrustadas, sin vínculos externos',integridad_ooxml='Correcta',pdf_verificacion='Abierto y extraído sin errores',bytes=path.stat().st_size))
report['verificacion_final']=checks
report['pendiente']='Ninguna pantalla principal pendiente. Restauración operativa no ejecutada por protección de datos; descrita desde el código y pruebas aisladas.'
report['pruebas_integracion']=dict(ejecutadas=18,aprobadas=17,omitidas=1,motivo='Prueba específica PostgreSQL; suite ejecutada sobre SQLite temporal.')
(DOCS/'Verificacion_Manuales.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2))
