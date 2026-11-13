"""Genera los manuales Word a partir del código inspeccionado y capturas reales."""
from datetime import datetime
import json
from pathlib import Path
import re
import textwrap
from zipfile import ZipFile

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
DOCS=ROOT/'docs'
CAP=DOCS/'capturas'
DIAGRAMS=DOCS/'diagramas'
BUILD=ROOT/'backend'/'manuales_build'
META=json.loads((BUILD/'metadata.json').read_text(encoding='utf-8'))
MANIFEST=json.loads((CAP/'manifest.json').read_text(encoding='utf-8'))
DATE=datetime.now().strftime('%d/%m/%Y')
BLACK=RGBColor(0,0,0)


def font(size=28,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)


def diagram(name,title,boxes,arrows,size=(1600,1050)):
    image=Image.new('RGB',size,'white');draw=ImageDraw.Draw(image)
    draw.text((size[0]//2,45),title,font=font(36,True),fill='black',anchor='mt')
    for start,end,label in arrows:
        draw.line([start,end],fill='#334155',width=4)
        import math
        angle=math.atan2(end[1]-start[1],end[0]-start[0])
        points=[end,(end[0]-18*math.cos(angle-.45),end[1]-18*math.sin(angle-.45)),(end[0]-18*math.cos(angle+.45),end[1]-18*math.sin(angle+.45))]
        draw.polygon(points,fill='#334155')
        if label:
            x,y=(start[0]+end[0])/2,(start[1]+end[1])/2
            draw.text((x+12,y-28),label,font=font(24),fill='black')
    for rect,heading,body in boxes:
        draw.rounded_rectangle(rect,radius=16,fill='#f1f5f9',outline='#334155',width=3)
        x1,y1,x2,y2=rect
        draw.text(((x1+x2)//2,y1+20),heading,font=font(29,True),fill='black',anchor='mt')
        lines=[]
        for line in body.split('\n'):lines.extend(textwrap.wrap(line,width=max(18,int((x2-x1)/16))))
        draw.multiline_text((x1+22,y1+72),'\n'.join(lines),font=font(26),spacing=8,fill='black')
    DIAGRAMS.mkdir(exist_ok=True)
    image.save(DIAGRAMS/(name+'.png'))


def make_diagrams():
    diagram('arquitectura','Arquitectura y flujo de una operación',[
        ((80,150,700,355),'Navegador: React + Vite','Formularios, Kanban, reportes y simulación.\nSesión mediante cookie HttpOnly.'),
        ((900,150,1520,355),'FastAPI + Pydantic','Valida datos y permisos.\nRutas /api y /simular.'),
        ((900,520,1520,750),'SQLAlchemy + PostgreSQL','Transacciones, reservas y versiones.\nPersistencia de solicitudes y eventos.'),
        ((80,520,700,750),'SimPy','Solicitudes, operadores y montacargas.\nEjecuta escenarios, no movimientos reales.'),
        ((440,870,1160,1010),'Herramientas locales','Alembic: esquema. pg_dump / pg_restore: respaldos.')
    ],[((700,240),(900,240),'HTTP / JSON'),((1200,355),(1200,520),'SQL'),((900,430),(400,430),'POST /simular'),((400,430),(400,520),''),((1200,750),(1000,870),''),((1520,650),(1520,650),'')])
    diagram('relaciones','Relaciones principales del modelo de datos',[
        ((40,145,480,365),'Identidad','roles → users → sessions\nroles ↔ permissions\nTabla puente: role_permissions'),
        ((580,145,1030,400),'requests','Solicitante y operador → users\nEstampadora → presses\nProceso → processes\nMontacargas → forklifts'),
        ((1130,145,1560,400),'request_items','Solicitud → requests\nParte → parts\nRollo preferido → rolls\nCantidad solicitada'),
        ((580,550,1030,805),'rolls','Parte → parts\nUbicación → locations\nReserva / entrega → requests\nEstado y peso del rollo'),
        ((40,550,480,805),'Trazabilidad','incidents → requests\naudit → users y requests\nsimulation_runs → users\ninventory_imports → users'),
        ((1130,550,1560,805),'Cambio de turno','handovers → users\nhandover_items → handovers\nhandover_items → requests\nCopia del estado en JSON')
    ],[((480,250),(580,250),''),((1030,250),(1130,250),'1:N'),((800,400),(800,550),'1:N'),((580,670),(480,670),''),((1130,680),(1030,680),'')],size=(1600,900))
    diagram('flujo_simulacion','Flujo de una solicitud en SimPy',[
        ((60,170,480,360),'1. Llegada','Momento aleatorio dentro del turno.'),
        ((590,170,1010,360),'2. Espera de operador','Cola por llegada o prioridad.'),
        ((1120,170,1540,360),'3. Preparación','Operador ocupado; localización y preparación.'),
        ((1120,560,1540,790),'4. Espera de equipo','Conserva al operador mientras espera un montacargas.'),
        ((590,560,1010,790),'5. Traslado','Operador y montacargas ocupados hasta terminar.'),
        ((60,560,480,790),'6. Entrega','Libera recursos. Calcula espera, duración y fin dentro del turno.')
    ],[((480,265),(590,265),''),((1010,265),(1120,265),''),((1330,360),(1330,560),''),((1120,670),(1010,670),''),((590,670),(480,670),'')],size=(1600,900))


def field(paragraph,instruction,placeholder=''):
    begin=OxmlElement('w:fldChar');begin.set(qn('w:fldCharType'),'begin')
    code=OxmlElement('w:instrText');code.set(qn('xml:space'),'preserve');code.text=instruction
    separate=OxmlElement('w:fldChar');separate.set(qn('w:fldCharType'),'separate')
    end=OxmlElement('w:fldChar');end.set(qn('w:fldCharType'),'end')
    for node in (begin,code,separate):paragraph.add_run()._r.append(node)
    if placeholder:paragraph.add_run(placeholder)
    paragraph.add_run()._r.append(end)


class Manual:
    def __init__(self,title,filename):
        self.doc=Document();self.title=title;self.filename=filename;self.figures=[]
        section=self.doc.sections[0]
        section.page_width=Cm(21);section.page_height=Cm(29.7)
        section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Cm(2.5)
        section.header_distance=section.footer_distance=Cm(1.2)
        for style in self.doc.styles:
            if style.type in (1,2):
                style.font.name='Arial';style.font.size=Pt(12);style.font.color.rgb=BLACK
                props=style.element.get_or_add_rPr()
                fonts=props.find(qn('w:rFonts'))
                if fonts is None:fonts=OxmlElement('w:rFonts');props.append(fonts)
                for slot in ('ascii','hAnsi','eastAsia','cs'):fonts.set(qn('w:'+slot),'Arial')
        normal=self.doc.styles['Normal']
        normal.paragraph_format.line_spacing=1.15
        normal.paragraph_format.space_after=Pt(7)
        for name in ('Title','Subtitle','Heading 1','Heading 2','Heading 3'):
            style=self.doc.styles[name];style.font.size=Pt(14);style.font.bold=True;style.font.color.rgb=BLACK
        for name in ('Heading 1','Heading 2','Heading 3'):
            self.doc.styles[name].paragraph_format.keep_with_next=True
        header=section.header.paragraphs[0]
        header.text='META-RIDE / PULL ACEROS';header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
        footer.add_run('Página ');field(footer,'PAGE','1');footer.add_run(' de ');field(footer,'NUMPAGES','1')
        self.doc.core_properties.title=title
        self.doc.core_properties.subject='Meta-Ride / Pull Aceros — documentación del repositorio inspeccionado'
        self.doc.core_properties.author='Proyecto Meta-Ride'
        self.doc.core_properties.keywords='Meta-Ride, Pull Aceros, FastAPI, React, SimPy, PostgreSQL'
        settings=self.doc.settings.element
        update=OxmlElement('w:updateFields');update.set(qn('w:val'),'true');settings.append(update)
        self.cover()

    def cover(self):
        for _ in range(3):self.doc.add_paragraph()
        for text in ['META-RIDE / PULL ACEROS',self.title,'Documentación académica del sistema']:
            p=self.doc.add_paragraph(text,'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        self.doc.add_paragraph()
        for text in ['Institución: __________________________________','Programa académico: __________________________','Asignatura: Modelado y Simulación de Sistemas','Autor(es): ___________________________________','Profesor(a): __________________________________','Grupo y semestre: _____________________________','Edición documental: 1.0','Fecha de elaboración: '+DATE]:
            p=self.doc.add_paragraph(text);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        self.p('Documento elaborado a partir del código y de capturas reales en un entorno de demostración aislado. Los campos académicos no proporcionados se dejan para completar.')
        self.doc.add_page_break()
        p=self.doc.add_paragraph('Índice','Title')
        field(self.doc.add_paragraph(),'TOC \\o "1-2" \\h \\z \\u','El índice se actualiza al abrir el documento en Microsoft Word.')
        self.doc.add_page_break()

    def h(self,text,level=1):
        p=self.doc.add_heading(text,level)
        if level==1 and len(self.doc.paragraphs)>20:p.paragraph_format.page_break_before=True
        return p

    def p(self,text,bold=False):
        p=self.doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
        r=p.add_run(text);r.bold=bold
        return p

    def steps(self,items):
        for i,item in enumerate(items,1):
            p=self.doc.add_paragraph(f'{i}. {item}');p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY

    def table(self,headers,rows,widths=None):
        table=self.doc.add_table(rows=1,cols=len(headers));table.alignment=WD_TABLE_ALIGNMENT.CENTER
        table.style='Table Grid';table.autofit=False
        if widths:
            for col,width in zip(table.columns,widths):col.width=Cm(width)
        for cell,text in zip(table.rows[0].cells,headers):
            cell.text=str(text)
            shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7E6E6');cell._tc.get_or_add_tcPr().append(shade)
            for r in cell.paragraphs[0].runs:r.bold=True
        repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            cells=table.add_row().cells
            for cell,text in zip(cells,row):
                cell.text=str(text);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
                    p.paragraph_format.line_spacing=1
        for row in table.rows:
            no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
            if widths:
                for cell,width in zip(row.cells,widths):cell.width=Cm(width)
        self.doc.add_paragraph()
        return table

    def code(self,text):
        for line in text.strip().splitlines():
            p=self.doc.add_paragraph(line);p.alignment=WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after=Pt(3);p.paragraph_format.left_indent=Cm(.3)
            p.paragraph_format.keep_with_next=True
        self.doc.add_paragraph()

    def fig(self,name,description,diagram=False):
        path=(DIAGRAMS if diagram else CAP)/(name+'.png')
        if not path.is_file():raise FileNotFoundError(path)
        with Image.open(path) as im:w,h=im.size
        width=min(16,19*w/h)
        p=self.doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True
        p.add_run().add_picture(str(path),width=Cm(width))
        self.figures.append(path.name)
        caption=self.doc.add_paragraph(f'Figura {len(self.figures)}. {description}')
        caption.alignment=WD_ALIGN_PARAGRAPH.CENTER
        caption.paragraph_format.space_after=Pt(12)

    def save(self):
        path=DOCS/self.filename;self.doc.save(path)
        Document(path)
        with ZipFile(path) as archive:
            assert archive.testzip() is None
            assert len([n for n in archive.namelist() if n.startswith('word/media/')])>0
            for name in archive.namelist():
                if name.endswith('.rels'):
                    assert not re.search(rb'Type="[^"]*/image"[^>]*TargetMode="External"',archive.read(name))
        return dict(file=self.filename,figures=len(self.figures),images=self.figures)


ROLES=[
    ('Administrador','Todas las operaciones; usuarios, catálogos y respaldos.'),
    ('Producción','Crea solicitudes y consulta operación, inventario, historial y turnos; no coordina reservas ni ejecuta simulación.'),
    ('Logística','Crea y coordina solicitudes; inventario, cambio de turno y simulación; sin administración de usuarios/catálogos/respaldos.'),
    ('Operador','Avanza sus movimientos asignados y entrega/recibe turno; consulta las pantallas comunes. No valida, asigna, edita ni cancela solicitudes.')
]
STATES=[
    ('Solicitado','Crear solicitud','Se registra el folio; aún no reserva material.'),
    ('Validado','Validar existencia y especificación','Reserva material elegible en una transacción.'),
    ('Tomado','Asignar operador','Asigna operador y montacargas opcional disponibles.'),
    ('En preparación','Iniciar preparación','Registra el inicio de la atención física.'),
    ('Listo para traslado','Confirmar material localizado','Confirma que el material está listo.'),
    ('En traslado','Iniciar traslado','Registra la salida hacia el punto de entrega.'),
    ('Entrega parcial','Confirmar entrega de algunos rollos','Conserva los rollos pendientes y los recursos asignados.'),
    ('Entregado','Confirmar entrega de todos los pendientes','Registra receptor, cierra el folio y libera el montacargas.'),
    ('Con incidencia','Registrar incidencia','Conserva la etapa anterior hasta resolver la incidencia.'),
    ('Cancelado','Cancelar solicitud y liberar recursos','Libera reservas pendientes y conserva entregas e historial.')
]
TROUBLES=[
    ('No conecta con el servidor','Iniciar backend con .\\run.ps1 y frontend con npm run dev; comprobar /salud y la consola.'),
    ('No se encuentra pg_ctl / PG_BIN','Comprobar .postgres/pgsql/bin/pg_ctl.exe y corregir PG_BIN en .env al mover la carpeta. No crear otra base para resolver una ruta incorrecta.'),
    ('Usuario o contraseña rechazados','Verificar usuario, cuenta activa y contraseña. Pedir al administrador restablecerla; no existe recuperación por correo.'),
    ('Demasiados intentos de acceso','El límite usa una ventana de 15 minutos. Esperar y verificar las credenciales antes de reintentar.'),
    ('El valor de cantidad debe ser 1','Se seleccionó un rollo específico. Elegir asignación automática o Permitir asignación automática para pedir varios rollos de una parte.'),
    ('Inventario insuficiente','Comprobar parte, ubicación activa, estado DISP, ausencia de reserva y peso mayor de 500 kg. La captura de 500 kg no es elegible.'),
    ('Operador o montacargas ocupado','Cerrar o cancelar el movimiento anterior, o seleccionar otro recurso; no desactivar un catálogo para liberar una maniobra.'),
    ('La solicitud cambió / error 409','Otro usuario modificó la versión o el recurso. Actualizar, revisar el estado y repetir solo la acción pendiente.'),
    ('Fecha requerida rechazada','Elegir una fecha/hora futura y comprobar el reloj y zona horaria del equipo. El navegador convierte la hora local a UTC.'),
    ('No aparece una opción del menú','El rol puede no tener permiso. Administración y Simulación, por ejemplo, no están disponibles para todos.'),
    ('El archivo no se importa','Usar CSV o XLSX, primera hoja, encabezados únicos, partes/ubicaciones existentes y pesos válidos; quitar fórmulas y revisar el mapeo.'),
    ('La revisión de importación venció','Generar otra vista previa y confirmarla antes de 30 minutos. Cada revisión solo puede confirmarse una vez.'),
    ('No se ven datos en Resumen','Quitar filtros con Ver todo o aplicar fechas de creación correctas. Un guion en una métrica puede indicar ausencia de entregas completas.'),
    ('La entrega parcial se completó totalmente','Sin rollos marcados, Confirmar entrega incluye todos los pendientes. Para una entrega parcial deben marcarse solo los rollos recibidos.'),
    ('No permite aceptar mi cambio de turno','Debe aceptarlo otra cuenta autorizada y, si se eligió destinatario, exactamente esa persona.'),
    ('Simulación muestra entregas con decimales','Es el promedio de 10 ejecuciones, no una cantidad física fraccionada de una única ejecución.'),
    ('No permite restaurar un respaldo','Detener el backend y usar un archivo del motor y esquema actuales. No restaurar una copia SQLite sobre PostgreSQL.')
]


def technical():
    m=Manual('Manual Técnico y de Desarrollo','Manual_Tecnico_MetaRide.docx')
    m.h('1. Propósito, alcance y fuentes')
    m.p('Meta-Ride / Pull Aceros centraliza requerimientos internos de rollos de acero, su surtimiento, entregas, incidencias y continuidad entre turnos. Este manual describe el código presente en la copia del repositorio inspeccionada, no una arquitectura propuesta.')
    m.table(['Control documental','Contenido'],[('Fecha',DATE),('Versión de API declarada','2.0.0 en main.py'),('Destinatarios','Desarrolladores, responsables técnicos y evaluadores académicos'),('Evidencia','Código fuente, OpenAPI generado, 19 tablas ORM y capturas con Playwright'),('Seguridad del recorrido','PostgreSQL temporal independiente; ningún dato operativo creado, modificado o eliminado')],[4.5,11.5])
    m.p('Se leyeron README.md, docs/AUDITORIA.md, docs/MANTENIMIENTO_LOCAL.md, docs/POSTGRESQL.md y docs/REQUISITOS_DOCUMENTO.md, además de los módulos de frontend, backend, migraciones y pruebas. Los conteos históricos publicados en esos archivos no representan el contenido actual de la base.')
    m.p('Prevalece el código actual cuando difiere de documentación anterior: la simulación ya no ofrece calibración histórica en la pantalla y muestra solamente tres indicadores. El endpoint de calibración sigue implementado en la API. La plantilla Excel de validación existente es un recurso de captura de datos, no una conexión de la aplicación.')
    m.h('2. Arquitectura y flujo de datos')
    m.fig('arquitectura','Componentes implementados y sus conexiones. Las flechas muestran dependencias principales.',True)
    m.table(['Capa','Responsabilidad'],[('Presentación','React, formularios, navegación mediante estado local, reportes Recharts y tarjetas Kanban.'),('Transporte','fetch con credenciales; Vite redirige /api, /simular y /salud al servidor local.'),('Aplicación','FastAPI recibe solicitudes; Pydantic valida datos y security.py exige los permisos.'),('Persistencia','SQLAlchemy y psycopg consultan PostgreSQL; Alembic mantiene el esquema.'),('Simulación','SimPy ejecuta procesos y colas virtuales; el resultado se guarda en simulation_runs.'),('Mantenimiento','PowerShell inicia el entorno; pg_dump/pg_restore respaldan y recuperan PostgreSQL.')],[4,12])
    m.h('2.1. Recorrido de una operación',2)
    m.steps(['El usuario inicia sesión y recibe una cookie opaca. El navegador no guarda tokens de autenticación en localStorage.','React consulta catálogos y operación. Los datos comunes se renuevan cada 30 segundos; no hay streaming ni WebSockets de aplicación.','El formulario transforma identificadores y cantidades a números y la hora local a ISO UTC.','FastAPI verifica sesión, permiso, esquema y reglas de negocio. SQLAlchemy reserva o modifica registros dentro de una transacción.','La versión evita avances obsoletos. El evento de auditoría y la modificación se confirman antes de enviar la respuesta, mediante dependencias con scope=function.','El frontend vuelve a consultar datos y muestra el estado actualizado o el error recibido.'])
    m.h('2.2. Navegación y límites de integración',2)
    m.p('App.jsx selecciona la pantalla mediante estado React; no hay router de URLs para cada módulo. La importación recibe archivos exportados por QAD, sin conexión directa al ERP. No se implementan notificaciones por correo, geolocalización de montacargas ni rutas geométricas de planta.')
    m.h('3. Tecnologías y versiones inspeccionadas')
    m.table(['Componente backend','Versión instalada'],list(META['backend_versions'].items()),[9,7])
    m.table(['Componente frontend','Versión instalada'],list(META['frontend_versions'].items()),[9,7])
    m.p('Las versiones de estas tablas se obtuvieron del entorno local, mientras que requirements.txt y package.json declaran rangos. package-lock.json fija la resolución npm. Python 3.12 y Node.js 22.13.0 están presentes en el entorno utilizado. La distribución PostgreSQL incluida corresponde a la rama 17; setup-postgres.ps1 referencia los binarios 17.11.')
    m.p('python-docx, Playwright, Pillow y pypdf se usaron como herramientas de documentación. Su instalación no modificó requirements.txt ni el manifiesto npm de la aplicación.')
    m.h('4. Estructura del repositorio')
    m.table(['Carpeta o archivo','Uso real'],[
        ('src/','Código React y estilos de la aplicación.'),('src/components/ui/','Componentes de botón, tarjeta, entrada, insignia y progreso.'),('src/lib/','Utilidades de clases y formato de plazos en días, horas y minutos.'),('src/assets/ y public/','Recursos estáticos; también permanecen imágenes del arranque Vite.'),('backend/','API, reglas de negocio, modelos, simulación, pruebas y scripts.'),('backend/migrations/','Configuración Alembic, instantánea inicial y revisiones 0001–0006.'),('backend/.postgres/','Binarios, datos y configuración privada del clúster local. No editar manualmente.'),('backend/backups/','Copias operativas .dump y copias SQLite anteriores, fuera de control de versiones.'),('backend/migration-reports/','Reportes de verificación de la migración; no son métricas del negocio.'),('backend/.venv/ y __pycache__/','Entorno Python y caché; no forman parte del código fuente.'),('docs/','Documentación, plantilla de validación y manuales generados.'),('docs/capturas/ y docs/diagramas/','Capturas reales y diagramas incluidos en los manuales.'),('artifacts/','Evidencias de verificaciones del navegador preexistentes.'),('dist/','Compilación de producción generada por Vite; no editar a mano.'),('node_modules/','.Dependencias instaladas de npm; se regeneran desde el manifiesto y lock.'),('Microsoft/','Carpeta auxiliar existente; no es importada como módulo de la aplicación.'),('.git/ y .gitignore','Historial del repositorio y exclusiones de archivos privados.'),('index.html y src/main.jsx','Entrada HTML y montaje React en StrictMode.'),('vite.config.js','Plugins React/Tailwind, alias @, proxy local y restricciones de archivos.'),('eslint.config.js, jsconfig.json y components.json','Análisis estático, alias y configuración de componentes.'),('package.json y package-lock.json','Dependencias y comandos dev/build/lint/preview.'),('README.md','Guía general de instalación y operación; contrastar con la versión actual.')],[6,10])
    m.h('4.1. Módulos de la interfaz',2)
    m.table(['Archivo','Responsabilidad'],[
        ('App.jsx','Sesión, carga común, menú, alertas, Kanban y detalle modal.'),('Operations.jsx','Nueva solicitud, inventario, historial y acciones sobre el folio.'),('RequestEditor.jsx','Edición justificada de campos y partidas con ajuste de reservas.'),('Reports.jsx y DashboardCharts.jsx','Indicadores por periodo y gráficos por estado, turno y causa.'),('ShiftPage.jsx','Entrega y aceptación de pendientes entre personas autorizadas.'),('AdminPage.jsx','Usuarios, catálogos y respaldos.'),('InventoryImport.jsx','Archivo, mapeo de columnas, vista previa y confirmación.'),('AccountPage.jsx','Cambio de contraseña propia.'),('SimulationPage.jsx','Escenario, opciones simplificadas, resultados y comparaciones.'),('api.js','fetch, cookies, mensajes del servidor y cierre por sesión no autorizada.'),('lib/time.js','Formato legible para vencimientos y retrasos.'),('index.css y App.css','Estilos globales; App.css conserva estilos iniciales y no es la base del tablero.')],[6,10])
    m.h('4.2. Módulos del servidor',2)
    m.table(['Archivo','Responsabilidad'],[
        ('main.py','Crea FastAPI, registra routers, CORS, ciclo de vida, /salud y /simular.'),('database.py','Motor, sesión ORM, entidades, relaciones y restricciones.'),('schemas.py','Entradas estrictas Pydantic; límites, literales y fechas.'),('security.py','Hash de contraseñas, sesión, permisos, bootstrap y transacciones.'),('api.py','Autenticación, catálogos, usuarios, inventario, solicitudes, acciones, métricas, historial, turnos y simulaciones.'),('reservations.py','Elegibilidad, selección y reserva atómica de rollos.'),('request_revisions.py','Edición de solicitudes y conservación del material entregado.'),('maintenance.py','Cambios de usuarios, contraseñas y catálogos.'),('inventory_import.py','Lectura XLSX/CSV, revisión, token temporal y confirmación transaccional.'),('operations.py','Zona de planta, fechas inclusivas, estados cerrados y horarios de turno.'),('simulation.py','Validación del escenario, ejecución SimPy y agregación de réplicas.'),('backups.py y manage.py','Copias, bloqueo de mantenimiento, descarga y recuperación fuera de línea.'),('settings.py y local_postgres.py','Carga de .env y gestión del clúster PostgreSQL local.'),('migrate_postgres.py','Copia verificable SQLite → PostgreSQL y activación explícita.'),('run.ps1 y setup-postgres.ps1','Arranque habitual e instalación de binarios locales.'),('test_integration.py','Pruebas de API sobre bases aisladas.'),('test_postgres_concurrency.py','Competencia real por rollos, operadores, equipos y versiones.'),('check_postgres.py y check_browser.py','Bases PostgreSQL desechables y recorrido con Chrome.'),('alembic.ini y requirements.txt','Configuración de migraciones y dependencias Python.')],[6,10])
    m.h('5. Instalación, configuración y ejecución')
    m.h('5.1. Requisitos y copia ya configurada',2)
    m.p('Utilizar Windows con PowerShell, Python 3.12, Node.js/npm y las utilidades PostgreSQL. Los puertos habituales son 5173 para Vite, 8000 para FastAPI y 5432 para PostgreSQL. El instalador local puede elegir 55432 cuando inicializa un clúster nuevo y 5432 ya está ocupado.')
    m.steps(['Abrir una terminal en la raíz, donde se encuentra package.json.','Instalar dependencias frontend y arrancar Vite.','Abrir otra terminal en backend y ejecutar run.ps1. Si PowerShell bloquea scripts, permitirlos solo para ese proceso.','En la primera base sin usuarios, definir la contraseña solicitada para admin: al menos 12 caracteres. En una base existente usar las credenciales que ya tenga.','Abrir la URL que imprime Vite y verificar el backend en /salud.'])
    m.code('npm install\nnpm run dev')
    m.code('cd backend\nSet-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned\n.\\run.ps1')
    m.p('run.ps1 crea el entorno virtual si falta, comprueba dependencias, inicia el PostgreSQL local configurado, aplica Alembic y crea un respaldo si ya existen usuarios. Finalmente ejecuta Uvicorn en 127.0.0.1:8000. Cada terminal debe permanecer abierta.')
    m.h('5.2. Preparación de una instalación nueva',2)
    m.code('cd backend\npy -3.12 -m venv .venv\n.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt\n.\\setup-postgres.ps1')
    m.p('setup-postgres.ps1 descarga y verifica el archivo de binarios que tiene fijado; extrae servidor, bibliotecas y herramientas, inicializa el clúster local y crea una cuenta de aplicación sin privilegios administrativos. No activa por sí solo la migración de datos.')
    m.p('Si se dispone de la SQLite de origen, detener su backend y activar únicamente tras verificar que el destino está vacío:')
    m.code('.\\.venv\\Scripts\\python.exe migrate_postgres.py --activate\n.\\run.ps1')
    m.p('Si la instalación no tiene SQLite que migrar, configurar backend/.env con la conexión PostgreSQL creada o con un servidor PostgreSQL previamente preparado; después aplicar Alembic y arrancar con run.ps1. .env.example es una plantilla para un servidor existente, no crea bases ni usuarios. Mantener en privado las credenciales generadas en .postgres/credentials.json; no copiarlas a documentación ni Git.')
    m.h('5.3. Variables y comprobaciones',2)
    m.table(['Variable','Uso'],[
        ('DATABASE_URL','Conexión SQLAlchemy; para PostgreSQL usa postgresql+psycopg. Una variable del proceso prevalece sobre .env.'),('PG_BIN','Carpeta de pg_ctl, pg_dump, pg_restore e initdb; corregirla si cambia la ubicación del proyecto.'),('PG_LOCAL_AUTOSTART','true activa el arranque del clúster local desde run.ps1.'),('METARIDE_ADMIN_PASSWORD','Solo crea la primera cuenta admin; no restablece una contraseña existente.'),('BACKUP_DIR','Ubicación de los respaldos; por defecto backend/backups para PostgreSQL.'),('PG_ADMIN_URL','Conexión administrativa de mantenimiento, cuando se usa un servidor externo.'),('COOKIE_SECURE','true para servir por HTTPS; el desarrollo local HTTP utiliza false.'),('CORS_ORIGINS','Orígenes admitidos, separados por comas; revisar al separar frontend y backend.'),('PLANT_TIMEZONE','Zona IANA de reportes; valor predeterminado America/Monterrey.'),('VITE_API_URL / VITE_SIM_API','Origen de la API en la interfaz. Con proxy local no hace falta definirlo.')],[5.5,10.5])
    m.code('.\\.venv\\Scripts\\python.exe manage.py info\n.\\.venv\\Scripts\\python.exe local_postgres.py status')
    m.p('Servicios de referencia: interfaz http://localhost:5173; salud http://127.0.0.1:8000/salud; Swagger http://127.0.0.1:8000/docs; contrato http://127.0.0.1:8000/openapi.json. Si falta .env tras activar PostgreSQL, settings.py evita recurrir silenciosamente a la SQLite antigua.')
    m.h('6. Modelo de datos PostgreSQL')
    m.p('SQLAlchemy declara 19 tablas de aplicación; Alembic agrega alembic_version para registrar la revisión. Se utilizan claves enteras, claves foráneas y restricciones únicas. Los campos de fecha operativa se almacenan en UTC sin zona adjunta y se interpretan como UTC al presentarlos.')
    m.fig('relaciones','Relaciones principales. Las referencias nombradas corresponden a claves foráneas; las copias de turno se conservan como JSON.',True)
    m.h('6.1. Tablas y finalidad',2)
    purposes={'roles':'Cuatro roles efectivos del servidor.','permissions':'Acciones autorizables.','role_permissions':'Relación muchos a muchos entre rol y permiso.','users':'Cuenta, hash de contraseña, rol, estado y versión.','sessions':'Hash del token opaco, usuario y vencimiento.','processes':'Tipos de proceso.','presses':'Estampadoras.','parts':'Código de material y especificación técnica.','locations':'Ubicaciones de inventario.','forklifts':'Equipo activo y disponibilidad de asignación.','requests':'Cabecera del requerimiento, responsables, prioridad, destino y estado.','request_items':'Parte, cantidad y rollo preferido opcional por solicitud.','rolls':'Unidad física con código, peso, ubicación, estado y solicitud asociada.','incidents':'Causa, descripción, paro, etapa anterior y resolución.','audit':'Evento, usuario, detalle, solicitud opcional y fecha.','handovers':'Entrega, destinatario, turno y aceptación.','handover_items':'Copia JSON del estado de cada folio al entregar turno.','simulation_runs':'Parámetros y resultado JSON de una simulación.','inventory_imports':'Token hasheado, revisión, caducidad y confirmación de importaciones.'}
    m.table(['Tabla','Finalidad'],[(t['name'],purposes[t['name']]) for t in META['tables']],[5,11])
    m.h('6.2. Restricciones e integridad',2)
    m.p('Los códigos de rollo, parte, ubicación y montacargas y el nombre de usuario son únicos. Una solicitud no admite repetir el mismo número de parte en distintas partidas. Las cantidades son positivas y el peso es mayor de cero. Un rollo solo admite DISP, RESERVADO, ENTREGADO o BLOQUEADO.')
    m.p('La elegibilidad de surtimiento exige DISP, ausencia de otra reserva, peso mayor de 500 kg, parte y ubicación activas. La reserva automática elige identificadores de rollo ascendentes. Un rollo específico exige cantidad 1 y debe pertenecer a la parte seleccionada. La aplicación no deduce una compatibilidad industrial entre parte, estampadora y proceso.')
    m.p('Las versiones de registros evitan sobrescribir cambios concurrentes. En PostgreSQL se usan bloqueos de fila y FOR UPDATE SKIP LOCKED para reservas. Los índices parciales uq_requests_active_operator_id y uq_requests_active_forklift_id impiden que el mismo recurso figure en dos solicitudes abiertas. Los errores transaccionales esperados se transforman en HTTP 409.')
    m.h('6.3. Migraciones',2)
    m.table(['Revisión','Cambio'],[('0001','Esquema operativo inicial normalizado.'),('0002','Rollo físico preferido en una partida.'),('0003','Conservación de la restricción de cantidad al recrear tablas SQLite.'),('0004','Recepción digital de turno e incidencias estructuradas.'),('0005','Mantenimiento de usuarios/catálogos, versiones e importaciones.'),('0006','Unicidad de recursos en movimientos abiertos.')],[3,13])
    m.h('7. API FastAPI y contratos')
    m.p('El inventario siguiente procede del OpenAPI generado por el código actual: 34 operaciones HTTP. /docs y /redoc son interfaces de documentación del framework; no son módulos del negocio. Las lecturas comunes requieren sesión salvo /salud. Las operaciones de escritura exigen además un permiso.')
    descriptions={
        ('POST','/api/auth/login'):('Público','Usuario y contraseña; crea cookie y evento.'),('GET','/api/auth/me'):('Sesión','Identidad, rol y permisos.'),('POST','/api/auth/logout'):('Sesión/cookie','Revoca el token recibido y borra la cookie.'),('POST','/api/auth/password'):('Sesión','Contraseña actual y nueva; revoca otras sesiones.'),
        ('GET','/api/catalogs'):('Sesión','Catálogos y cuentas elegibles para asignación/turno.'),('POST','/api/catalogs/{kind}'):('admin','Crea parte, ubicación, equipo, estampadora o proceso.'),('PATCH','/api/catalogs/{kind}/{id}'):('admin','Edita nombre, estado y especificación con versión.'),
        ('GET','/api/users'):('admin','Lista usuarios sin hashes.'),('POST','/api/users'):('admin','Crea usuario con rol.'),('PATCH','/api/users/{id}'):('admin','Edita cuenta con versión.'),('POST','/api/users/{id}/password'):('admin','Restablece otra cuenta y revoca sus sesiones.'),
        ('GET','/api/inventory'):('Sesión','Lista rollos y elegibilidad.'),('POST','/api/inventory'):('inventory','Registra código, parte, ubicación y kg.'),('GET','/api/inventory/import/template'):('inventory','Plantilla; query format=xlsx o csv.'),('POST','/api/inventory/import/preview'):('inventory','multipart: file, mapping y update_existing.'),('POST','/api/inventory/import/commit'):('inventory','Token de revisión; confirma de forma atómica.'),
        ('GET','/api/requests'):('Sesión','Solicitudes con partidas, rollos, eventos e incidencias.'),('POST','/api/requests'):('request','Crea cabecera y partidas; clave idempotente.'),('PATCH','/api/requests/{id}'):('coordinate','Revisión con versión y justificación.'),('POST','/api/requests/{id}/actions'):('operate y reglas','Avance con versión; ciertas acciones exigen coordinate.'),
        ('GET','/api/history'):('Sesión','Últimos 2000 eventos.'),('GET','/api/history/export'):('Sesión','Exporta toda la bitácora CSV.'),('GET','/api/metrics'):('Sesión','Indicadores; start/end como fechas locales.'),('GET','/api/metrics/export'):('Sesión','CSV del periodo aplicado.'),
        ('GET','/api/handovers'):('Sesión','Últimas 100 entregas de turno.'),('POST','/api/handovers'):('handover','Turno, destinatario y notas; copia de pendientes.'),('POST','/api/handovers/{id}/accept'):('handover','Aceptación por otra persona autorizada.'),
        ('GET','/api/simulations'):('simulate','Últimas 50 ejecuciones guardadas.'),('GET','/api/simulations/calibration'):('simulate','Rangos observados; endpoint vigente, retirado de la UI.'),('POST','/simular'):('simulate','Recibe Params y persiste el resultado SimPy.'),('GET','/salud'):('Público','Estado y nombre del motor de datos.'),
        ('GET','/api/backups'):('admin','Lista archivos de respaldo y compatibilidad.'),('POST','/api/backups'):('admin','Crea copia consistente.'),('GET','/api/backups/{name}'):('admin','Descarga validando el nombre del archivo.')}
    for group,prefixes in [('7.1. Identidad y catálogos',('/api/auth','/api/users','/api/catalogs')),('7.2. Inventario y solicitudes',('/api/inventory','/api/requests')),('7.3. Reportes, turno, simulación y respaldo',('/api/history','/api/metrics','/api/handovers','/api/simulations','/api/backups','/simular','/salud'))]:
        m.h(group,2)
        rows=[]
        for route in META['routes']:
            if route['path'].startswith(prefixes):
                method=route['methods'][0];permission,description=descriptions[(method,route['path'])]
                rows.append((method+' '+route['path'],permission,description+' Éxito: '+str(route['status'])+'.'))
        m.table(['Método y ruta','Acceso','Comportamiento'],rows,[6.8,3,6.2])
    m.h('7.4. Contratos y errores',2)
    m.table(['Entrada','Campos y reglas esenciales'],[('RequestInput','key de 16–80 caracteres; press_id, process_id, priority, risk, destination, required_at con zona, notes e items (1–50). Cada partida tiene part_id, quantity (1–100) y preferred_roll_id opcional.'),('ActionInput','version ≥1, action y campos según acción: operator_id, forklift_id, roll_ids, receiver, notes, cause y production_stopped.'),('RequestRevision','Los campos de solicitud, version y justification de al menos 3 caracteres.'),('RollInput','code, part_id, location_id y kg positivo hasta 1 000 000.'),('UserInput','Usuario 3–80 caracteres [a-zA-Z0-9_.-], contraseña 12–200 y role_id.'),('HandoverInput','incoming_shift T1/T2/T3, notes 3–4000 y receiving_user_id; la UI obliga seleccionar destinatario.'),('Params','Solicitudes 1–1000, montacargas y operadores 1–30, turno 60–1440 min; otros campos del modelo mantienen sus validaciones.')],[4.5,11.5])
    m.table(['Código','Interpretación'],[('401','Sesión ausente, vencida o cuenta inactiva; verificar detalle.'),('403','Permiso insuficiente o responsable no autorizado.'),('404','Registro o respaldo inexistente.'),('409','Conflicto de estado, versión, existencias o recurso ocupado.'),('422','Entrada inválida o regla que exige completar/corregir un campo.'),('429','Demasiados intentos de inicio de sesión.')],[3,13])
    m.p('Los modelos Strict rechazan campos adicionales. required_at exige zona horaria y se normaliza a UTC. Una clave de creación repetida permite recuperar la misma solicitud; otra solicitud abierta idéntica por estampadora, proceso, hora y partidas se rechaza como probable duplicado.')
    m.h('8. Autenticación, permisos y trazabilidad')
    m.table(['Rol','Alcance implementado'],ROLES,[4,12])
    m.p('Las contraseñas se almacenan con scrypt, sal aleatoria y comparación de tiempo constante. El token de sesión es aleatorio; en sessions solo se conserva su SHA-256 y vencimiento. La cookie metaride_session es HttpOnly, SameSite=Strict, con duración de ocho horas y Secure configurable.')
    m.p('El acceso fallido se registra y se limita por cuenta y origen en una ventana de 15 minutos; el umbral es diez eventos aplicables. Cambiar rol, desactivar o restablecer otra cuenta revoca sesiones. Cambiar la propia contraseña conserva la sesión actual y cierra las demás. Debe quedar al menos un administrador activo.')
    m.p('La auditoría registra usuario, acción, detalle y fecha, con folio cuando corresponde. Los códigos internos como deliver no son cantidades: la presentación actual de una entrega incluye receptor, cantidad y códigos de rollo. No existe un endpoint para borrar rollos ni una opción general de eliminación en la interfaz; no documentar borrados manuales como función del usuario.')
    m.h('9. Reglas operativas y transiciones')
    m.table(['Estado','Botón o acción','Efecto'],STATES,[3.8,5,7.2])
    m.p('Logística/administrador valida, asigna, edita y cancela. Un operador solo registra avances sobre sus movimientos asignados. Las solicitudes Entregado y Cancelado no aceptan avances. Resolver incidencia exige texto y retorna a la etapa anterior; la cancelación cierra incidencias abiertas y solo libera material aún reservado.')
    m.p('Al cambiar material de una solicitud validada se reajustan todas las reservas o se revierte el cambio completo. Si hay operador asignado vuelve a Tomado para repetir preparación. Se conservan rollos ya entregados. Durante el traslado no se cambian material ni destino. No se puede disminuir una cantidad por debajo de lo entregado ni cerrar una entrega parcial editando cantidades.')
    m.h('10. Simulación con SimPy')
    m.fig('flujo_simulacion','Secuencia de atención y ocupación de recursos en el modelo implementado.',True)
    m.h('10.1. Entradas visibles y supuestos',2)
    m.table(['Entrada visible','Valor inicial y significado'],[('Solicitudes','50; entidades que llegan durante el turno. No es lectura automática del inventario real.'),('Montacargas','2; capacidad de la cola de traslado.'),('Operadores','3; capacidad de atención y preparación.'),('Duración del turno','480 minutos; editable entre 60 y 1440.'),('Tipo de demanda','Normal, o con urgencias: probabilidad 25% por entidad.'),('Regla de atención','Según tipo de demanda, orden de llegada o urgentes primero.')],[5,11])
    m.p('En la interfaz se mantienen preparación uniforme entre 5 y 12 min, traslado uniforme entre 8 y 20 min, localización e incidencias adicionales en cero, semilla base 42 y diez réplicas. La API conserva la distribución triangular y otros parámetros avanzados, pero no se presentan como controles disponibles al usuario.')
    m.h('10.2. Ejecución y recursos',2)
    m.p('una_corrida crea un generador random.Random independiente y un Environment SimPy. Genera llegadas uniformes entre 0 y la duración del turno, y sortea previamente tareas y urgencias. PriorityResource limita operadores y montacargas; prioridad 0 atiende urgentes antes que prioridad 1 cuando la regla lo dispone, sin interrumpir servicios iniciados.')
    m.p('La solicitud espera operador, consume localización/preparación y conserva al operador mientras espera montacargas. Después ambos quedan ocupados hasta terminar el traslado. Al final se liberan por los bloques de contexto. env.run() termina todas las entidades, incluidas las que salen del turno; esa continuidad no las convierte en entregas dentro del turno.')
    m.h('10.3. Cálculo de los tres resultados visibles',2)
    m.table(['Resultado','Cálculo'],[('Tiempo promedio de entrega','Para cada entidad: fin − llegada. Promedio sobre todas las solicitudes, incluyendo las entregadas después del turno.'),('Tiempo promedio de espera','Para cada entidad: (inicio de operador − llegada) + (inicio de traslado − material listo). Promedio sobre todas las entidades.'),('Entregas dentro del turno','Conteo de entidades con fin ≤ turno_minutos. Se cuentan solicitudes, no rollos físicos ni movimientos operativos.')],[5.5,10.5])
    m.p('simulate ejecuta diez corridas con semillas base+i. El resumen promedia cada indicador de las corridas y redondea a dos decimales. Por ello las entregas pueden mostrarse como 45,6: es un promedio de conteos enteros. Los tiempos individuales guardados en registros también se redondean a dos decimales antes de promediar.')
    m.p('Ejemplo didáctico: si tres entidades tardan 20, 30 y 40 min, el tiempo de entrega de esa corrida es 30 min. Si esperan 0, 5 y 10 min por recursos, la espera media es 5 min. Si solo dos terminan antes del cierre, esa corrida registra dos entregas en turno. La pantalla vuelve a promediar estos resultados entre las réplicas.')
    m.fig('17_simulacion','Pantalla actual: solo tres indicadores básicos y valores de demostración.')
    m.h('10.4. Comparaciones y límites',2)
    m.p('Comparar 1 a 4 montacargas ejecuta cuatro escenarios con la misma carga y operadores. Comparar reglas ejecuta llegada y urgentes primero y se habilita cuando hay demanda con urgencias. La misma semilla mantiene llegadas y tareas comparables. Cada respuesta se conserva en simulation_runs; la UI muestra hasta diez antecedentes y el endpoint consulta hasta cincuenta.')
    m.p('El modelo no reproduce geometría de rutas, consumo parcial de kg, compatibilidades por estampadora ni fallas individuales de equipo. Los tiempos no están calibrados industrialmente. /api/simulations/calibration calcula rangos desde cinco muestras válidas por etapa, pero ya no se consulta desde la pantalla simplificada; no afirmar que sus rangos se aplican automáticamente.')
    m.h('11. Indicadores operativos, fechas y turnos')
    m.p('Los indicadores de Resumen provienen de la base operativa y no de SimPy. Las solicitudes se seleccionan por fecha de creación; movimientos e incidencias por fecha de evento. start y end son días locales inclusivos convertidos a un intervalo UTC con límite final excluido. La aceptación de turno pendiente se cuenta globalmente, sin aplicar el filtro de fechas de solicitudes.')
    m.table(['Indicador','Definición'],[('Activas y vencidas','Solicitudes no cerradas; vencidas si required_at ya pasó. Próximas a vencer: hasta 30 min.'),('Entregas a tiempo','Porcentaje de solicitudes con entrega final ≤ required_at entre las que tienen entrega final.'),('Promedio de surtimiento','Media de delivered_at − created_at de las solicitudes completadas.'),('Movimientos por turno','Cada evento deliver cuenta una vez, aunque incluya varios rollos o sea parcial.'),('Causas de retraso','Conteo de incidencias reportadas por causa.'),('Tiempo con paro','Suma de intervalos de incidencias marcadas con paro; puede solaparse y no equivale a inactividad única de una máquina.')],[5,11])
    m.p('T1 comprende 06:00–14:00, T2 14:00–21:30 y T3 21:30–06:00 en la zona configurada. La madrugada se atribuye al día de inicio del turno nocturno. El periodo aplicado es una consulta estática; debe volver a consultarse. Ver todo restablece el acumulado que se renueva cada 30 segundos.')
    m.h('12. Importación de inventario y cambio de turno')
    m.p('La importación recibe CSV UTF-8/Windows-1252 o primera hoja XLSX; límites de 5 MB, 5000 filas y 50 columnas. Admite mapeo a codigo_rollo, numero_parte, ubicacion, kg y estado. Rechaza fórmulas y formatos distintos; solo DISP/BLOQUEADO se importan. La revisión no guarda rollos: persiste un payload temporal y un hash de token, con vigencia de 30 minutos.')
    m.p('La confirmación vuelve a revisar versiones y disponibilidad, se exige el mismo usuario y el token solo se consume una vez. Se aplica todo el archivo o nada. Rollos reservados y entregados nunca se sobrescriben. La importación de QAD es por archivo exportado, no por conexión directa.')
    m.p('handovers guarda quién entrega, a quién, turno y notas. handover_items conserva la copia JSON de cada pendiente. La aceptación exige otra cuenta autorizada y el destinatario correcto cuando está seleccionado; no reasigna operadores ni libera reservas. La UI permite consultar la copia histórica junto al estado actual.')
    m.h('13. Pruebas, mantenimiento y recuperación')
    m.h('13.1. Comandos de verificación',2)
    m.code('npm run lint\nnpm run build\ncd backend\n.\\.venv\\Scripts\\python.exe -m unittest test_integration\n.\\.venv\\Scripts\\python.exe check_postgres.py --skip-migration')
    m.p('La suite de integración usa SQLite temporal salvo que METARIDE_TEST_DATABASE_URL seleccione otra base aislada. check_postgres crea y elimina bases desechables para comprobar transacciones y concurrencia. Nunca definir esas variables con una conexión operativa. check_browser.py también usa una base/perfil temporal; su implementación actual utiliza CDP y Chrome, no Playwright.')
    m.p('Para estos manuales se utilizó Playwright con Chrome y otra PostgreSQL desechable. Se verificaron acceso, consulta, importación, respaldo, simulación, comparación y aceptación de turno. La suite de integración de esta elaboración terminó con 18 pruebas: 17 aprobadas y una restauración específica de PostgreSQL omitida por ejecutarse sobre SQLite. No se probó restauración sobre la base operativa ni se modificó el código de negocio.')
    m.h('13.2. Respaldo y restauración',2)
    m.code('.\\.venv\\Scripts\\python.exe manage.py backup')
    m.p('Crear desde Administración o terminal produce un .dump consistente con pg_dump mientras la aplicación está activa. Para restaurar, primero detener FastAPI con Ctrl+C. La recuperación reemplaza la base seleccionada; usar solamente una copia del motor y revisión actuales.')
    m.code('.\\.venv\\Scripts\\python.exe manage.py restore "metaride-FECHA-CODIGO.dump" --confirm RESTAURAR\n.\\run.ps1')
    m.p('El bloqueo de mantenimiento rechaza restaurar si otra API mantiene uso compartido. La herramienta valida primero el archivo en una base temporal, comprueba esquema y administrador activo, crea una copia antes-restauracion y restaura con pg_restore en una transacción. Después revoca sesiones e importaciones pendientes y registra el evento. La cuenta administrativa solo se usa en mantenimiento; la API opera con la cuenta de servicio.')
    m.fig('16_respaldos','Respaldo real de la base PostgreSQL de demostración. No contiene datos operativos.')
    m.h('13.3. Migración y conservación',2)
    m.p('migrate_postgres.py obtiene una copia consistente SQLite, la actualiza con Alembic, rechaza un destino con datos y compara huellas normalizadas por tabla. Ajusta secuencias y activa .env únicamente tras verificar. metaride.db representa el estado anterior al cambio; no sustituye a la PostgreSQL con operaciones nuevas.')
    m.p('Mantener privados .env, credentials.json, carpetas de datos y respaldos. Vite excluye backend y archivos .env del servicio de archivos. El arranque es local; un despliegue remoto necesita HTTPS, cookies Secure y proxy/CORS apropiados. No existe un procedimiento de publicación remota ya implementado en el repositorio.')
    m.h('14. Diagnóstico y límites documentados')
    m.table(['Situación','Acción recomendada'],TROUBLES,[5,11])
    m.p('La evidencia no acredita integración directa con QAD, ajuste estadístico industrial, compatibilidad automática de materiales, correo de recuperación, impresión de etiquetas ni eliminación de inventario desde la UI. No se describen como funciones disponibles. No se hicieron commits ni push durante la elaboración.')
    m.h('Anexo A. Diccionario de datos')
    m.p('Diccionario generado de Base.metadata. PK identifica clave primaria; FK referencia tabla y columna; NULL indica que el campo admite ausencia. Los contenidos JSON se almacenan en columnas de texto. Las restricciones compuestas se explican en la sección 6.')
    for t in META['tables']:
        m.h(t['name'],2)
        rows=[]
        for c in t['columns']:
            attrs=[]
            if c['pk']:attrs.append('PK')
            if c['unique']:attrs.append('Único')
            attrs.append('NULL' if c['nullable'] else 'No NULL')
            if c['fk']:attrs.append('FK: '+', '.join(c['fk']))
            rows.append((c['name'],c['type'],'; '.join(attrs)))
        m.table(['Campo','Tipo ORM','Restricción / relación'],rows,[5.2,4.5,6.3])
    m.h('Anexo B. Trazabilidad documental')
    m.p('Fuentes del repositorio: README.md; docs/AUDITORIA.md; docs/MANTENIMIENTO_LOCAL.md; docs/POSTGRESQL.md; docs/REQUISITOS_DOCUMENTO.md; código listado en el inventario de módulos. Las rutas de API y el diccionario se obtuvieron del OpenAPI y ORM actuales, sin consultar credenciales ni extraer registros operativos.')
    m.p('Las capturas originales se conservan en docs/capturas. manifest.json identifica cada pantalla y el aislamiento del entorno. Los diagramas fueron elaborados a partir del código y se conservan en docs/diagramas. El archivo Verificacion_Manuales.json reúne comprobaciones de estructura, imágenes y apertura.')
    return m.save()


def user():
    m=Manual('Manual de Usuario','Manual_Usuario_MetaRide.docx')
    m.h('1. Presentación y acceso según rol')
    m.p('Meta-Ride / Pull Aceros permite solicitar rollos, coordinar su surtimiento, registrar entregas e incidencias y dar continuidad a los pendientes entre turnos. Este manual sigue los nombres de botones y campos de la interfaz actual.')
    m.p('Las imágenes muestran cuentas y datos de demostración en una PostgreSQL temporal. No son órdenes reales ni cifras de planta. Los números de folio son ejemplos y en otra instalación pueden cambiar. No hay contraseña predeterminada: utiliza la que asignó el administrador.')
    m.table(['Rol','Qué puede hacer'],ROLES,[4,12])
    m.p('Requisitos de uso: navegador actualizado, acceso al frontend y backend iniciados, cuenta activa y catálogos preparados. Al capturar fechas, el formulario usa la hora local del equipo. Mantén correctos el reloj y la zona horaria.')
    m.h('2. Iniciar y cerrar sesión')
    m.steps(['Abrir la dirección de la interfaz; en desarrollo suele ser http://localhost:5173.','Escribir el usuario y la contraseña asignados.','Pulsar Entrar al sistema o presionar Enter desde la contraseña.','Esperar el Resumen operativo. El menú disponible depende de los permisos.','Al terminar, pulsar Cerrar sesión en el menú lateral.'])
    m.fig('01_inicio_sesion','Inicio de sesión: usuario y contraseña autorizados.')
    m.p('Resultado esperado: acceso a la cuenta y a sus funciones. Si faltan credenciales o la cuenta está inactiva, aparece un error. Las sesiones duran ocho horas y también pueden cerrarse si el administrador cambia el acceso. Tras varios intentos fallidos puede aplicarse una espera por límite de acceso.')
    m.h('3. Consultar Resumen y alertas')
    m.steps(['Seleccionar Resumen.','Revisar solicitudes activas, vencidas, entregas a tiempo y promedio de surtimiento.','Para un periodo, completar Desde/Hasta y pulsar Consultar periodo; cambiar solo las fechas no aplica la consulta.','Seleccionar una etapa de Estado de solicitudes para ver sus folios y abrir uno.','Consultar Movimientos por turno, elegir Todos/T1/T2/T3 y desplegar Ver detalle de movimientos.','Revisar causas de retraso, paros reportados y su tiempo acumulado.','Pulsar Exportar indicadores CSV para descargar los datos del periodo aplicado; Ver todo regresa al acumulado.'])
    m.fig('02_resumen','Resumen operativo con solicitudes e incidencias de demostración.')
    m.table(['Elemento','Interpretación'],[('Entregas a tiempo','Porcentaje de solicitudes completadas antes de su hora requerida.'),('Promedio de surtimiento','Tiempo de creación a entrega final; las parciales aún abiertas no lo completan.'),('Movimientos','Cada confirmación de entrega cuenta una vez, incluso si es parcial o incluye varios rollos.'),('Próximas a vencer','Solicitudes con hasta 30 minutos antes de su hora requerida.'),('Tiempo con paro','Suma de incidencias marcadas con paro; pueden existir intervalos solapados.'),('Campana superior','Muestra urgentes, próximas a vencer, retrasadas, incidencias y turnos por aceptar.')],[5,11])
    m.p('La vista acumulada se actualiza cada 30 segundos. Un periodo aplicado es una consulta de ese momento y debe volver a consultarse para actualizarla. Las solicitudes se agrupan por creación y los movimientos/incidencias por fecha del evento. La recepción pendiente de turno se cuenta globalmente.')
    m.h('4. Consultar el Panel Kanban')
    m.steps(['Abrir Panel Kanban.','Buscar por folio, ENN o número de parte y filtrar por estampadora si hace falta.','Desplazarse horizontalmente para ver todas las columnas.','Seleccionar una tarjeta para consultar materiales, responsables, incidencias y trazabilidad.','Cerrar el detalle con el botón de cierre y volver al tablero.'])
    m.fig('03_kanban','Primeras columnas del Kanban: solicitudes y etapas de preparación.')
    m.fig('04_kanban_entregas','Desplazamiento horizontal hacia incidencias, entregas y cancelaciones.')
    m.p('Cada tarjeta muestra folio, estampadora, prioridad, partes, rollos entregados/solicitados, responsable y fecha requerida. El plazo se expresa en días, horas y minutos; si pasó, indica retraso. Los folios cerrados muestran su estado final. Las tarjetas se abren para registrar acciones; no se arrastran entre columnas.')
    m.table(['Estado','Cómo se alcanza','Qué significa'],STATES,[3.8,5,7.2])
    m.h('5. Crear una solicitud')
    m.p('Disponible para Producción, Logística y Administrador. Antes de empezar debe existir el número de parte activo con su especificación. La disponibilidad se confirma al validar, no al llenar el formulario.')
    m.steps(['Seleccionar Nueva solicitud.','Elegir Estampadora y Tipo de proceso.','Seleccionar prioridad Normal, Alta o Urgente y la Fecha y hora requerida futura.','Capturar el Punto de entrega y el Riesgo para Producción.','Agregar especificaciones y observaciones en el campo de comentarios.','Elegir el número de parte; revisar especificación y disponibles.','Dejar Rollo: asignación automática para pedir varios rollos, o elegir un rollo físico específico para cantidad 1.','Indicar Cantidad de rollos. Usar Agregar partida para otra parte o Quitar para retirar una partida; no repetir la misma parte.','Pulsar Crear solicitud y comprobar el folio en Solicitado dentro del Kanban.'])
    m.fig('05_nueva_solicitud','Nueva solicitud con dos rollos y asignación automática.')
    m.table(['Campo','Regla de uso'],[('Prioridad','Normal, Alta o Urgente; expresa necesidad operativa.'),('Riesgo','Sin riesgo, Riesgo de paro o Línea detenida; no sustituye registrar una incidencia.'),('Fecha requerida','Hora local futura; se convierte automáticamente a UTC.'),('Cantidad','Número de rollos físicos, entre 1 y 100 por parte; no son kg.'),('Rollo específico','Identifica una sola unidad y limita la cantidad a 1.'),('Partidas','De 1 a 50; combinar la cantidad de una misma parte en una sola partida.'),('Comentarios','Observaciones hasta 2000 caracteres; el punto de entrega admite hasta 200.')],[5,11])
    m.p('Resultado esperado: un folio único en Solicitado. Si falta un dato obligatorio, el navegador o el servidor pide corregirlo. Una solicitud abierta idéntica puede rechazarse para evitar duplicados. Si se necesita una entrega parcial futura, crear una solicitud de dos o más rollos mediante asignación automática.')
    m.h('6. Validar y asignar recursos')
    m.p('Disponible para Logística y Administrador. El permiso del Operador no permite validar ni asignar.')
    m.steps(['Abrir la tarjeta en Solicitado.','Verificar parte, especificación, cantidades y destino. Pulsar Validar existencia y especificación.','Confirmar el estado Validado y los códigos reservados. Si no alcanza el material, corregir inventario o cantidades; no quedan reservas parciales del intento fallido.','Seleccionar un Operador activo disponible.','Elegir Montacargas (opcional) si se va a asignar equipo.','Pulsar Asignar operador y verificar el estado Tomado y el responsable.'])
    m.fig('08_detalle_asignacion','Detalle de una solicitud validada con selección de operador y montacargas.')
    m.p('Solo se reservan rollos DISP, sin reserva previa, de la parte solicitada, en ubicación activa y con peso mayor de 500 kg. Un rollo de exactamente 500 kg se registra, pero no se puede reservar. No se comparte operador o montacargas entre dos solicitudes abiertas.')
    m.h('7. Registrar preparación, localización y traslado')
    m.steps(['Ingresar como operador asignado o como coordinador autorizado.','Abrir la solicitud en estado Tomado.','Pulsar Iniciar preparación cuando empiece el trabajo. El estado cambia a En preparación.','Localizar y verificar físicamente el rollo; registrar observaciones de la etapa si corresponde.','Pulsar Confirmar material localizado. El estado será Listo para traslado.','Al salir hacia el punto de entrega, pulsar Iniciar traslado. El estado será En traslado.'])
    m.p('Resultado esperado: cada avance queda en Trazabilidad del folio con usuario y fecha/hora. El operador solo puede avanzar solicitudes asignadas a su cuenta. No pulsar etapas por anticipado: sus horas alimentan los indicadores de operación. La aplicación no verifica físicamente el acero ni rastrea rutas.')
    m.h('8. Confirmar entregas completas o parciales')
    m.h('8.1. Entrega completa',2)
    m.steps(['Abrir el folio En traslado.','Comprobar los rollos realmente recibidos.','Escribir el Responsable que recibe.','Para entregar todos los pendientes, dejar sin selección los rollos o seleccionar todos.','Pulsar Confirmar entrega. Comprobar Entregado y las cantidades entregadas.'])
    m.p('La última entrega registra la hora final y libera el montacargas. El responsable receptor es un nombre capturado, no una firma electrónica ni una nueva sesión de usuario.')
    m.h('8.2. Entrega parcial y conclusión',2)
    m.steps(['En un folio con varios rollos pendientes, marcar únicamente los que se reciben en esa entrega.','Capturar el responsable receptor y pulsar Confirmar entrega.','Verificar Entrega parcial y la cantidad efectivamente entregada.','Cuando llegue el resto, abrir de nuevo el folio y pulsar Completar entrega, con responsable y selección de pendientes.','Comprobar Entregado al finalizar todos.'])
    m.fig('10_entrega_parcial','Folio parcial: rollos recibidos, pendientes y responsable de la siguiente entrega.')
    m.p('Importante: sin selección se entregan todos los rollos pendientes. No se debe dejar todo desmarcado cuando se pretende registrar solo algunos. La parcial conserva los recursos y reservas del remanente.')
    m.p('En el historial, deliver es el código de la acción de entrega. El detalle indica Recibe, Cantidad y códigos de Rollos. Un código o ID de rollo no debe interpretarse como cantidad. Ejemplo: Cantidad: 1 | Rollos: DEMO-R01 significa una unidad.')
    m.h('9. Registrar y resolver incidencias')
    m.steps(['Abrir una solicitud no cerrada.','Seleccionar Causa de retraso: Material no disponible, Rollo no localizado, Especificación incorrecta, Falta de personal, Equipo no disponible, Pasillo obstruido u Otro.','Marcar La estampadora está detenida por falta de material solo si corresponde al hecho observado.','Escribir una descripción de al menos tres caracteres y pulsar Registrar incidencia.','Comprobar Con incidencia y la causa/descripción.','Al resolver el problema, escribir Resolución obligatoria y pulsar Resolver incidencia.','Comprobar que el folio vuelve a la etapa anterior y continuar la maniobra.'])
    m.fig('11_incidencia','Incidencia abierta y resolución obligatoria antes de retomar el flujo.')
    m.p('Una incidencia cambia el estado para que el pendiente sea visible; no reasigna recursos ni libera el material. El registro de paro alimenta el conteo y tiempo de incidencias del Resumen. Evitar registrar paros simulados en operación real.')
    m.h('10. Editar o cancelar una solicitud')
    m.h('10.1. Editar solicitud y cantidades',2)
    m.steps(['Como Logística o Administrador, abrir un folio no cerrado.','Desplegar Editar solicitud y cantidades.','Modificar únicamente los campos necesarios. Si un rollo específico limita la cantidad, pulsar Permitir asignación automática antes de aumentar los rollos.','Escribir la Justificación obligatoria.','Pulsar Guardar solicitud y ajustar reservas.','Revisar los nuevos materiales, cantidades, reservas y estado; repetir preparación cuando el cambio lo requiera.'])
    m.fig('09_edicion_solicitud','Edición justificada de la solicitud y sus cantidades.')
    m.p('La edición es completa o no se aplica. No permite quitar material ya entregado, disminuir cantidades por debajo de lo recibido ni cambiar material/destino durante traslado. Si cambia el material con un operador asignado, vuelve a Tomado. Una solicitud cerrada no se edita.')
    m.h('10.2. Cancelar',2)
    m.steps(['Abrir el folio aún activo.','Escribir la Justificación para cancelar.','Pulsar Cancelar solicitud y liberar recursos.','Comprobar Cancelado y que los rollos pendientes vuelven a estar disponibles.'])
    m.p('La cancelación conserva el historial y cualquier rollo ya entregado. Solo libera reservas pendientes y equipo; no borra el folio ni restaura material recibido. Si había una incidencia abierta, queda cerrada con la justificación de cancelación.')
    m.h('11. Consultar y registrar inventario')
    m.steps(['Abrir Inventario.','Buscar por rollo, parte o ubicación.','Revisar código, parte, ubicación, kg, estado y solicitud asociada.','Para registrar, bajar al formulario Registrar rollo.','Capturar Código único, Número de parte y especificación, Ubicación y Peso en kg.','Pulsar Guardar rollo y comprobar la nueva fila.'])
    m.fig('06_inventario','Inventario e ingreso a la importación de archivos.')
    m.fig('23_registro_rollo','Formulario de registro individual de rollos.')
    m.table(['Estado del rollo','Significado'],[('DISP','Libre; elegible solo si además cumple peso y catálogos activos.'),('RESERVADO','Comprometido con una solicitud.'),('ENTREGADO','Ya confirmado como recibido.'),('BLOQUEADO','No disponible para reservar; puede establecerse por importación.')],[4,12])
    m.p('Captura individual e importación están disponibles para Logística y Administrador. Los demás roles pueden consultar. El peso debe ser positivo y no exceder 1 000 000 kg; el código debe ser único. La interfaz no incluye un botón para eliminar rollos.')
    m.h('12. Importar Excel o CSV')
    m.steps(['En Inventario, descargar la plantilla Excel o CSV.','Registrar antes partes y ubicaciones activas.','Sustituir las filas de ejemplo por datos propios; mantener códigos como texto para conservar ceros iniciales.','Seleccionar Archivo de inventario. Si se actualizarán rollos libres existentes, marcar la opción correspondiente.','Pulsar Revisar archivo sin guardar.','Si no reconoce encabezados, relacionar las columnas con código de rollo, parte, ubicación, kg y estado; volver a revisar.','Examinar errores, filas nuevas, actualizadas y sin cambios. Una vista válida muestra la confirmación.','Pulsar Confirmar importación de N filas.','Verificar el mensaje de importación completada y el listado de rollos.'])
    m.fig('07_importacion','Revisión de un archivo CSV antes de confirmar los cambios.')
    m.table(['Columna estándar','Contenido'],[('codigo_rollo','Código físico único del rollo.'),('numero_parte','Código exacto de una parte activa existente.'),('ubicacion','Código exacto de una ubicación activa existente.'),('kg','Peso positivo, sin separadores de miles.'),('estado','DISP o BLOQUEADO; sin columna se usa DISP.')],[5,11])
    m.p('Límites: CSV o XLSX, primera hoja, hasta 5000 filas, 50 columnas y 5 MB. No se admiten fórmulas ni macros. Para QAD, exportar primero a un archivo admitido; no se conecta al ERP. Los errores rechazan el archivo completo. Rollos reservados/entregados no se sobrescriben. La revisión dura 30 minutos y solo puede confirmarla una vez el usuario que la creó.')
    m.h('13. Entregar y recibir el turno')
    m.h('13.1. Entregar pendientes',2)
    m.steps(['Abrir Cambio de turno con permiso de entrega/recepción.','Revisar los pendientes que continúan activos, sus rollos, ubicaciones e incidencias.','Seleccionar Turno entrante: T1, T2 o T3.','Elegir un Responsable entrante distinto de la cuenta actual.','Escribir pendientes críticos y contexto, al menos tres caracteres.','Pulsar Enviar pendientes para aceptación.','Verificar la entrega registrada como Pendiente de aceptación.'])
    m.fig('12_cambio_turno','Formulario de entrega y registro de pendientes entre turnos.')
    m.h('13.2. Aceptar recepción',2)
    m.steps(['Cerrar la sesión saliente e ingresar con la cuenta del destinatario; puede hacerlo en otro equipo.','Abrir Cambio de turno y localizar la entrega.','Desplegar Pendientes al entregar para revisar la copia histórica y contrastarla con el estado actual.','Escribir la nota de recepción.','Pulsar Aceptar recepción de pendientes.','Comprobar Aceptada, el nombre de quien recibió y la fecha/hora.'])
    m.fig('21_recepcion_turno','Destinatario autorizado con el botón de aceptación disponible.')
    m.fig('22_turno_aceptado','Entrega aceptada con evidencia de usuario, fecha y nota.')
    m.p('Aceptar transfiere la coordinación de los pendientes; conserva asignaciones de operador y reservas. No puede aceptarse la entrega propia. Horarios de referencia de planta: T1 06:00–14:00, T2 14:00–21:30, T3 21:30–06:00. Se elige el turno entrante explícitamente.')
    m.h('14. Consultar historial y exportar')
    m.steps(['Abrir Historial.','Escribir en Filtrar historial por folio, usuario o acción. La búsqueda local consulta los eventos cargados.','Revisar acción, usuario, folio, detalle y fecha/hora.','Pulsar Descargar CSV para obtener la bitácora completa.','Para revisar un folio concreto, abrirlo desde Kanban y leer Trazabilidad del folio.'])
    m.fig('13_historial','Bitácora operativa; el detalle de entrega separa cantidad y códigos.')
    m.p('La pantalla carga los últimos 2000 eventos; el CSV incluye todos. El filtro de texto de la pantalla no restringe la descarga completa. Los códigos de acciones pueden aparecer en inglés: validate = validación, assign = asignación, prepare = preparación, ready = material listo, transport = traslado, deliver = entrega, incident = incidencia, resolve = resolución y cancel = cancelación.')
    m.h('15. Administrar usuarios y catálogos')
    m.p('Estas funciones están disponibles exclusivamente para Administrador.')
    m.h('15.1. Crear y modificar usuarios',2)
    m.steps(['Abrir Administración y seleccionar Usuarios.','Capturar nombre de usuario, contraseña inicial y rol.','Pulsar Crear cuenta y comprobar el registro.','Para modificar, desplegar la cuenta en Usuarios y permisos.','Cambiar nombre, rol o Cuenta activa y pulsar Guardar usuario.','Para restablecer otra cuenta, capturar Nueva contraseña y pulsar Restablecer contraseña.'])
    m.fig('14_administracion_usuarios','Creación y mantenimiento de cuentas y roles.')
    m.p('Usuario: 3–80 caracteres, letras sin acentos, números, punto, guion o guion bajo. Contraseña: mínimo 12 caracteres. Cambiar rol/desactivar cierra sus sesiones. No se elimina la cuenta ni puede quedar la instalación sin administrador activo. Las cuentas con movimientos abiertos o recepciones pendientes requieren resolver esa actividad antes de retirar su acceso.')
    m.h('15.2. Crear y mantener catálogos',2)
    m.steps(['En Administración, seleccionar Catálogos.','Localizar Números de parte, Ubicaciones, Montacargas, Estampadoras o Tipos de proceso.','Capturar código/nombre; para una parte, agregar su especificación técnica. Pulsar Agregar.','Para modificar, desplegar el registro y ajustar nombre/código o estado.','Pulsar Guardar catálogo y verificar el resultado.'])
    m.fig('15_administracion_catalogos','Catálogos y controles de estado activo o en servicio.')
    m.p('Los catálogos inactivos no se ofrecen para operaciones nuevas. No se permite desactivar un registro comprometido en movimientos abiertos. En equipo, En servicio indica mantenimiento/retiro y Asignado indica ocupación; activar una casilla no libera una maniobra. Una especificación distinta para una parte que ya tiene rollos requiere crear otra parte.')
    m.h('16. Crear y descargar respaldos')
    m.steps(['Ingresar como Administrador y abrir Administración → Respaldos.','Pulsar Crear respaldo ahora.','Esperar Respaldo creado y localizar el archivo.','Pulsar Descargar y conservar la copia en una ubicación privada.','Si se requiere recuperar, desplegar Recuperar un respaldo y coordinar el procedimiento con el responsable técnico; no se ejecuta una restauración desde un botón web.'])
    m.fig('16_respaldos','Respaldo PostgreSQL generado y disponible para descarga.')
    m.p('En PostgreSQL el archivo es .dump. Las copias del motor anterior se identifican como tales. La recuperación reemplaza datos, exige detener el backend y usar el comando indicado por la pantalla. Crea una copia de recuperación y cierra sesiones. Para el procedimiento completo consultar el manual técnico. No restaurar una copia antigua solo para corregir una captura equivocada.')
    m.h('17. Ejecutar y explicar la simulación')
    m.p('Disponible para Logística y Administrador. La simulación crea solicitudes virtuales; no consume rollos del inventario, no mueve folios operativos y sus resultados no sustituyen las mediciones del Resumen.')
    m.steps(['Abrir Simulación.','Indicar Solicitudes durante el turno, Montacargas disponibles y Operadores disponibles.','Para una primera demostración usar 50 solicitudes, 2 montacargas y 3 operadores.','Pulsar Ejecutar simulación.','Leer los tres resultados y revisar que se refieren al escenario configurado.'])
    m.fig('17_simulacion','Tres resultados básicos de un escenario ejecutado.')
    m.table(['Resultado','Qué mide y cómo se calcula'],[('Tiempo promedio de entrega','Promedio de hora de entrega menos hora de llegada; incluye esperas, preparación y traslado.'),('Tiempo promedio de espera','Promedio de la espera por operador más la espera por montacargas; excluye el trabajo de preparación y traslado.'),('Entregas dentro del turno','Solicitudes que terminan a más tardar al cierre; se muestra el promedio de diez ejecuciones.')],[5.5,10.5])
    m.p('Una entrega posterior al cierre no cuenta dentro del turno, pero sí se simula hasta finalizar para calcular su tiempo total y espera. Se repite diez veces; por eso pueden aparecer entregas con decimales. No significa una fracción de rollo.')
    m.h('17.1. Opciones avanzadas simplificadas',2)
    m.steps(['Desplegar Opciones avanzadas (opcional).','Elegir demanda Normal o Con urgencias. Esta última da a cada solicitud una probabilidad del 25% de ser urgente.','Indicar Duración del turno en minutos, entre 60 y 1440; 480 equivale a ocho horas.','Elegir Regla de atención: Según tipo de demanda, Orden de llegada o Urgentes primero.','Volver a ejecutar para aplicar los cambios.'])
    m.fig('18_simulacion_opciones','Solo tres opciones avanzadas: demanda, duración del turno y regla de atención.')
    m.p('Según tipo de demanda usa orden de llegada para demanda normal y prioridad a urgentes cuando existen urgencias. Preparación de 5–12 minutos y traslado de 8–20 minutos son supuestos fijos de esta pantalla. La simulación no aprende automáticamente del historial operativo.')
    m.h('17.2. Comparar escenarios',2)
    m.steps(['Mantener las mismas solicitudes, operadores y turno.','Pulsar Comparar 1 a 4 montacargas.','Leer las barras: menor longitud significa menor espera promedio. Debajo aparecen tiempo de entrega y entregas dentro del turno.','Para comparar reglas, seleccionar demanda Con urgencias y pulsar Comparar orden de llegada y urgentes primero.','Desplegar Ver simulaciones anteriores para consultar las últimas diez guardadas.'])
    m.fig('19_simulacion_comparacion','Comparación de recursos usando las mismas llegadas y duraciones simuladas.')
    m.p('Frase sugerida para exposición: «Mantengo la misma demanda y cambio los recursos para observar cuánto esperan las solicitudes y cuántas se completan dentro del turno». Los resultados no garantizan desempeño industrial sin validar los tiempos con datos de planta.')
    m.h('18. Cambiar la contraseña propia')
    m.steps(['Abrir Mi cuenta desde el menú o desde el usuario de la barra superior.','Capturar Contraseña actual.','Escribir Nueva contraseña, diferente de la actual y de al menos 12 caracteres.','Repetirla en Confirmar nueva contraseña.','Pulsar Cambiar contraseña y comprobar el mensaje de actualización.'])
    m.fig('20_mi_cuenta','Cambio de contraseña con verificación de la actual y confirmación de la nueva.')
    m.p('La sesión actual permanece abierta y se cierran las de otros dispositivos. Si la confirmación no coincide, corregirla. Si se olvidó la contraseña, un administrador debe restablecer la cuenta; no hay enlace de recuperación por correo.')
    m.h('19. Problemas frecuentes')
    m.table(['Problema','Qué hacer'],TROUBLES,[5,11])
    m.h('20. Lista de comprobación para una demostración')
    m.steps(['Preparar partes, ubicaciones, montacargas, cuentas y rollos elegibles de demostración en una base autorizada.','Crear un folio de una unidad y completar validar → asignar → preparar → localizar → trasladar → entregar.','Crear otro de dos unidades y confirmar solo una para mostrar Entrega parcial.','Registrar y resolver una incidencia en un folio abierto.','Editar una cantidad con justificación y comprobar las reservas.','Enviar turno y aceptarlo con otra cuenta autorizada.','Consultar indicadores, filtrar fechas y descargar CSV.','Ejecutar la simulación y comparar montacargas manteniendo las demás entradas.','Crear un respaldo, verificar persistencia tras recargar y cerrar sesión.'])
    m.p('No utilizar estas pruebas para generar incidentes o entregas ficticias en una base operativa. Las capturas de este manual se generaron en un entorno aislado y se conservan en docs/capturas. Todas las pantallas principales solicitadas pudieron documentarse; los procedimientos destructivos de restauración se explican sin ejecutarlos sobre operación.')
    return m.save()


def main():
    DOCS.mkdir(exist_ok=True)
    assert len(MANIFEST['capturas'])>=23
    assert not MANIFEST['errores_navegador']
    make_diagrams()
    results=[technical(),user()]
    report=dict(fecha=DATE,documentos=results,capturas_reales=len(MANIFEST['capturas']),diagramas=3,tablas_aplicacion=len(META['tables']),operaciones_api=len(META['routes']),verificacion_inicial='ZIP íntegro; apertura con python-docx; imágenes internas; sin enlaces externos de imágenes.',pendiente='Apertura y paginación con Microsoft Word.')
    (DOCS/'Verificacion_Manuales.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
