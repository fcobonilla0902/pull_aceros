"""Capturas para manuales; usa una PostgreSQL desechable y puertos independientes."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / 'backend'
OUT = ROOT / 'docs' / 'capturas'
API = 'http://127.0.0.1:8117'
WEB = 'http://127.0.0.1:5187'
CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def wait_http(url):
    for _ in range(150):
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.3)
    raise RuntimeError('No inició: ' + url)


def seed(password):
    with httpx.Client(base_url=API, timeout=45) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        def post(path, data):
            return call('POST', path, json=data)
        post('/api/auth/login', dict(username='admin', password=password))
        cats = call('GET', '/api/catalogs')
        users = {}
        for name, role in [('produccion.demo', 'Producción'), ('logistica.demo', 'Logística'), ('operador.demo', 'Operador'), ('operador.entrante', 'Operador')]:
            users[name] = post('/api/users', dict(username=name, password=password, role_id=next(r['id'] for r in cats['roles'] if r['name']==role)))
        part = post('/api/catalogs/parts', dict(name='DEMO-ACERO-01', specification='Acero de demostración; espesor 2 mm'))
        second = post('/api/catalogs/parts', dict(name='DEMO-ACERO-02', specification='Acero de demostración; espesor 3 mm'))
        loc = post('/api/catalogs/locations', dict(name='DEMO-A01'))
        loc2 = post('/api/catalogs/locations', dict(name='DEMO-B02'))
        lifts = [post('/api/catalogs/forklifts', dict(name='DEMO-MC0'+str(n))) for n in (1, 2)]
        for n in range(1, 13):
            post('/api/inventory', dict(code=f'DEMO-R{n:02d}', part_id=part['id'], location_id=loc['id'], kg=900+n*50))
        post('/api/inventory', dict(code='DEMO-NO-ELEGIBLE', part_id=second['id'], location_id=loc2['id'], kg=500))
        def req(press, qty=1, **kwargs):
            return post('/api/requests', dict(key=secrets.token_hex(16), press_id=press, process_id=cats['processes'][0]['id'], priority='Normal', risk='Sin riesgo', destination='Recepción ENN'+str(press), required_at=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(), notes='DEMONSTRACIÓN AISLADA PARA MANUALES', items=[dict(part_id=part['id'], quantity=qty)], **kwargs))
        def action(r, name, **kwargs):
            return post(f"/api/requests/{r['id']}/actions", dict(action=name, version=r['version'], **kwargs))
        def transit(r, op, lift=None):
            r=action(r,'validate')
            r=action(r,'assign',operator_id=op, forklift_id=lift)
            for name in ('prepare','ready','transport'):r=action(r,name)
            return r
        done=transit(req(1),users['operador.demo']['id'],lifts[0]['id'])
        done=action(done,'deliver',receiver='Supervisor de demostración')
        partial=transit(req(2,2),users['operador.demo']['id'],lifts[0]['id'])
        partial=action(partial,'deliver',receiver='Supervisor de demostración',roll_ids=[partial['rolls'][0]['id']])
        incident=action(req(3),'validate')
        incident=action(incident,'assign',operator_id=users['operador.entrante']['id'],forklift_id=lifts[1]['id'])
        incident=action(incident,'prepare')
        incident=action(incident,'incident',cause='Pasillo obstruido',notes='Demostración: acceso al rollo temporalmente bloqueado.',production_stopped=True)
        valid=action(req(4),'validate')
        urgent=post('/api/requests',dict(key=secrets.token_hex(16),press_id=5,process_id=cats['processes'][1]['id'],priority='Urgente',risk='Riesgo de paro',destination='Recepción ENN5',required_at=(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(),notes='DEMO: atender antes del siguiente cambio de turno',items=[dict(part_id=part['id'],quantity=1)]))
        pending=req(6)
        canceled=action(action(req(1),'validate'),'cancel',notes='Demostración: cambio de programa de producción.')
        ready=action(req(4),'validate')
        ready=action(ready,'assign',operator_id=1)
        ready=action(action(ready,'prepare'),'ready')
        handover=post('/api/handovers', dict(incoming_shift='T2',receiving_user_id=users['operador.entrante']['id'],notes='Revisar pasillo obstruido y completar entrega parcial de ENN2.'))
        return dict(users=users,part=part,location=loc,partial=partial,incident=incident,valid=valid,pending=pending,done=done,handover=handover)


async def capture(password, demo, temp):
    OUT.mkdir(parents=True, exist_ok=True)
    shots=[]
    errors=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(channel='chrome',headless=True)
        context=await browser.new_context(viewport=dict(width=1280,height=900),device_scale_factor=1.5,locale='es-MX',timezone_id='America/Monterrey',reduced_motion='reduce')
        page=await context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        async def snap(name, description, locator=None):
            await page.evaluate('document.fonts.ready')
            await page.wait_for_timeout(400)
            target=locator or page
            await target.screenshot(path=str(OUT/(name+'.png')), animations='disabled', **({} if locator else dict(full_page=False)))
            shots.append(dict(file=name+'.png',description=description))
            print('Captura:',name,flush=True)
        async def nav(name, wait):
            await page.locator('aside').get_by_role('button',name=name,exact=True).click()
            await page.get_by_text(wait,exact=False).first.wait_for()
            await page.evaluate('window.scrollTo(0,0)')
        async def login(username):
            await page.locator('input[autocomplete=username]').fill(username)
            await page.locator('input[type=password]').fill(password)
            await page.get_by_role('button',name='Entrar al sistema',exact=True).click()
            await page.locator('[data-testid=operational-dashboard]').wait_for()
        async def detail(r):
            await nav('Panel Kanban','Panel Kanban')
            await page.get_by_role('button').filter(has=page.get_by_text(r['folio'],exact=True)).click()
            await page.get_by_role('button',name='Cerrar detalle').wait_for()
        async def close():
            await page.get_by_role('button',name='Cerrar detalle').click()
        await page.goto(WEB,wait_until='networkidle')
        await page.locator('input[autocomplete=username]').wait_for()
        await snap('01_inicio_sesion','Inicio de sesión sin credenciales visibles.')
        await login('admin')
        await page.get_by_text('Movimientos por turno',exact=False).first.wait_for()
        await snap('02_resumen','Resumen con datos de la base de demostración aislada.')
        await nav('Panel Kanban','Panel Kanban')
        await snap('03_kanban','Kanban: primeras columnas y solicitudes de demostración.')
        board=page.locator('div.flex.snap-x')
        await board.evaluate('(element)=>element.scrollLeft=element.scrollWidth')
        await snap('04_kanban_entregas','Kanban: incidencias, entregas parciales y estados finales.')
        await nav('Nueva solicitud','Punto de entrega')
        await page.locator('select[name=press_id]').select_option('1')
        await page.locator('select[name=process_id]').select_option('1')
        await page.locator('input[name=destination]').fill('Recepción ENN1')
        await page.locator('input[name=required_at]').fill((datetime.now()+timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'))
        part_select=page.locator('select').filter(has=page.locator('option',has_text='Número de parte / especificación'))
        await part_select.select_option(str(demo['part']['id']))
        await page.get_by_role('spinbutton',name='Cantidad de rollos').fill('2')
        await snap('05_nueva_solicitud','Formulario de solicitud; asignación automática para pedir dos rollos.')
        await nav('Inventario','Registrar rollo')
        await snap('06_inventario','Inventario físico e importación Excel/CSV.')
        register=page.locator('form').filter(has=page.get_by_role('heading',name='Registrar rollo',exact=True))
        await register.scroll_into_view_if_needed()
        await snap('23_registro_rollo','Captura individual de un rollo: código, parte, ubicación y kg.',register)
        await page.evaluate('window.scrollTo(0,0)')
        csv=temp/'inventario_manual.csv'
        csv.write_text('codigo_rollo,numero_parte,ubicacion,kg,estado\nDEMO-IMPORTADO,DEMO-ACERO-01,DEMO-A01,1500,DISP\n',encoding='utf-8-sig')
        await page.locator('input[type=file]').set_input_files(str(csv))
        await page.get_by_role('button',name='Revisar archivo sin guardar',exact=True).click()
        await page.get_by_text('Archivo válido para confirmar',exact=False).wait_for()
        await snap('07_importacion','Vista previa real de un CSV; ninguna fila se guarda sin confirmación.')
        await page.get_by_role('button',name='Confirmar importación de 1 filas',exact=True).click()
        await page.get_by_text('Importación completada:',exact=False).wait_for()
        await detail(demo['valid'])
        modal=page.locator('div.max-h-\\[92vh\\]')
        await snap('08_detalle_asignacion','Detalle del folio, reserva de rollos y asignación de recursos.',modal)
        await page.locator('[data-testid=request-editor]').evaluate('(element)=>element.open=true')
        await page.locator('[data-testid=request-editor]').scroll_into_view_if_needed()
        await snap('09_edicion_solicitud','Edición de cantidades y campos con justificación obligatoria.',modal)
        await close()
        await detail(demo['partial'])
        await page.get_by_role('button',name='Completar entrega',exact=True).scroll_into_view_if_needed()
        await snap('10_entrega_parcial','Entrega parcial: cantidades, responsable y rollos pendientes.',modal)
        await close()
        await detail(demo['incident'])
        await page.get_by_role('button',name='Resolver incidencia',exact=True).scroll_into_view_if_needed()
        await snap('11_incidencia','Incidencia tipificada y formulario de resolución.',modal)
        await close()
        await nav('Cambio de turno','Entregar al siguiente turno')
        await page.get_by_role('button',name='Enviar pendientes para aceptación',exact=True).scroll_into_view_if_needed()
        await snap('12_cambio_turno','Pendientes activos y entrega al siguiente turno.')
        await nav('Historial','Descargar CSV')
        await snap('13_historial','Bitácora con usuario, folio, fecha y detalles de entrega.')
        await nav('Administración','Crear usuario')
        await snap('14_administracion_usuarios','Administración de usuarios y permisos.')
        await page.get_by_role('button',name='Catálogos',exact=True).click()
        await page.get_by_text('Números de parte',exact=True).wait_for()
        await snap('15_administracion_catalogos','Catálogos, especificaciones y estados de servicio.')
        await page.get_by_role('button',name='Respaldos',exact=True).click()
        await page.get_by_role('button',name='Crear respaldo ahora',exact=True).click()
        await page.get_by_text('Respaldo creado:',exact=False).wait_for()
        await snap('16_respaldos','Creación de un respaldo PostgreSQL de la base de demostración.')
        await nav('Simulación','Simulador de surtimiento de acero')
        await page.get_by_role('button',name='Ejecutar simulación',exact=True).click()
        await page.get_by_text('Tiempo promedio de entrega',exact=True).wait_for()
        await snap('17_simulacion','Simulación actual con sus tres indicadores básicos.')
        await page.get_by_text('Opciones avanzadas (opcional)',exact=True).click()
        options=page.locator('details').filter(has=page.get_by_text('Opciones avanzadas (opcional)',exact=True))
        await snap('18_simulacion_opciones','Opciones avanzadas: demanda, duración del turno y regla de atención.',options)
        await page.get_by_text('Opciones avanzadas (opcional)',exact=True).click()
        await page.get_by_role('button',name='Comparar 1 a 4 montacargas',exact=True).click()
        await page.get_by_text('Una barra más corta',exact=False).wait_for()
        await snap('19_simulacion_comparacion','Comparación real de uno a cuatro montacargas, manteniendo los demás parámetros.')
        await nav('Mi cuenta','Cambia tu contraseña sin cerrar esta sesión.')
        await snap('20_mi_cuenta','Cambio de contraseña desde la cuenta autenticada.')
        await page.locator('aside').get_by_role('button',name='Cerrar sesión',exact=True).click()
        await page.locator('input[autocomplete=username]').wait_for()
        await login('operador.entrante')
        await nav('Cambio de turno','Aceptar recepción de pendientes')
        await page.get_by_role('button',name='Aceptar recepción de pendientes',exact=True).scroll_into_view_if_needed()
        await snap('21_recepcion_turno','Recepción por el destinatario; cuenta distinta de quien entrega.')
        await page.get_by_role('textbox',name='Recepción de entrega 1').fill('Recibo pendientes y revisaré el acceso al material.')
        await page.get_by_role('button',name='Aceptar recepción de pendientes',exact=True).click()
        await page.get_by_text('Aceptó operador.entrante',exact=False).wait_for()
        await page.get_by_text('Aceptó operador.entrante',exact=False).scroll_into_view_if_needed()
        await snap('22_turno_aceptado','Evidencia de aceptación con usuario y fecha.')
        await browser.close()
    (OUT/'manifest.json').write_text(json.dumps(dict(capturas=shots,errores_navegador=errors,motor_demo='postgresql',aislamiento='Base PostgreSQL temporal; eliminada al terminar. Sin datos operativos.',fecha=datetime.now().isoformat()),ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:raise RuntimeError('Excepciones de JavaScript: '+repr(errors))


def main():
    # No se reutilizan puertos de los servidores operativos.
    for port in (8117,5187):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))
    from local_postgres import start
    from check_postgres import temporary_database
    start()
    processes=[]
    logs=[]
    with temporary_database() as target, tempfile.TemporaryDirectory(prefix='metaride-manuales-') as work:
        temp=Path(work)
        password=secrets.token_urlsafe(24)
        environment=os.environ.copy()
        environment.update(DATABASE_URL=target.render_as_string(hide_password=False),PG_LOCAL_AUTOSTART='false',BACKUP_DIR=str(temp/'backups'),METARIDE_ADMIN_PASSWORD=password)
        try:
            subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=BACKEND,env=environment,check=True,creationflags=CREATE_FLAGS)
            log=(temp/'backend.log').open('w+b');logs.append(log)
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8117'],cwd=BACKEND,env=environment,stdout=log,stderr=log,creationflags=CREATE_FLAGS))
            wait_http(API+'/salud')
            demo=seed(password)
            config=temp/'vite.manual.mjs'
            config.write_text('import {mergeConfig} from '+json.dumps((ROOT/'node_modules/vite/dist/node/index.js').as_uri())+';\nimport base from '+json.dumps((ROOT/'vite.config.js').as_uri())+';\nexport default mergeConfig(base,{server:{host:"127.0.0.1",port:5187,strictPort:true,proxy:{"/api":"'+API+'","/simular":"'+API+'","/salud":"'+API+'"}}});',encoding='utf-8')
            log=(temp/'frontend.log').open('w+b');logs.append(log)
            processes.append(subprocess.Popen(['node',str(ROOT/'node_modules/vite/bin/vite.js'),'--config',str(config)],cwd=ROOT,env=environment,stdout=log,stderr=log,creationflags=CREATE_FLAGS))
            wait_http(WEB)
            asyncio.run(capture(password,demo,temp))
        except Exception:
            for log in logs:
                log.flush();log.seek(0)
                print(log.read().decode('utf-8',errors='replace')[-4000:])
            raise
        finally:
            for process in reversed(processes):
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=CREATE_FLAGS)
                process.wait(timeout=15)
            for log in logs:log.close()


if __name__=='__main__':main()
