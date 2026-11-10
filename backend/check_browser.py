"""Headless Chrome smoke test; temporary database, isolated browser profile, no npm additions.

Run from the repo root: backend/.venv/Scripts/python.exe backend/check_browser.py
Uses websockets already supplied by uvicorn[standard]. Requires Chrome on Windows.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import http.cookiejar
import websockets

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'
API='http://127.0.0.1:8107'
WEB='http://127.0.0.1:5179'
CHROME=Path(os.getenv('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe'

def wait_http(url,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(url,timeout=1) as response:return json.load(response) if 'json' in response.headers.get('content-type','') else response.read()
        except (OSError,ValueError):time.sleep(.2)
    raise RuntimeError('Service did not start: '+url)

class CDP:
    def __init__(self,ws):self.ws=ws;self.seq=0;self.errors=[];self.http_errors=[];self.network_failures=[]
    async def call(self,method,params=None):
        self.seq+=1;identity=self.seq
        await self.ws.send(json.dumps({'id':identity,'method':method,'params':params or {}}))
        while True:
            message=json.loads(await asyncio.wait_for(self.ws.recv(),timeout=20))
            if message.get('method')=='Runtime.exceptionThrown':self.errors.append(message['params'])
            if message.get('method')=='Network.loadingFailed':self.network_failures.append(message['params'].get('errorText'))
            if message.get('method')=='Network.responseReceived':
                response=message['params']['response']
                if response['status']>=400:self.http_errors.append((response['url'],response['status']))
            if message.get('id')==identity:
                if 'error' in message:raise RuntimeError(message['error'])
                return message.get('result',{})
    async def evaluate(self,expression):
        result=await self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    async def until(self,expression,timeout=20):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if await self.evaluate(expression):return
            await asyncio.sleep(.1)
        raise AssertionError(f'Timeout: {expression}\nHTTP: {self.http_errors}\nJS: {self.errors}\nNetwork: {self.network_failures}\n'+str(await self.evaluate('document.body.textContent')))
    async def click(self,label):
        expression=f"[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==={json.dumps(label)})"
        await self.until(f'Boolean({expression})')
        await self.evaluate(f'{expression}.click()')
    async def type(self,selector,value):
        await self.evaluate(f'document.querySelector({json.dumps(selector)}).focus()')
        await self.evaluate(f'document.querySelector({json.dumps(selector)}).select()')
        await self.call('Input.insertText',{'text':value})

async def scenario(password,recipient,inventory_file):
    tabs=wait_http('http://127.0.0.1:9337/json')
    page=next(p for p in tabs if p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl']) as ws:
        cdp=CDP(ws)
        await cdp.call('Runtime.enable');await cdp.call('Page.enable');await cdp.call('Network.enable')
        await cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await cdp.call('Page.navigate',{'url':WEB})
        await cdp.until("Boolean(document.querySelector('input[autocomplete=username]'))",timeout=45)
        await cdp.type('input[autocomplete=username]','admin');await cdp.type('input[type=password]',password)
        await cdp.click('Entrar al sistema')
        await cdp.until("document.body.textContent.includes('Resumen operativo') && document.body.textContent.includes('Movimientos por turno')")
        print('Chrome: acceso correcto',flush=True)
        await cdp.click('Administración')
        await cdp.until("document.body.textContent.includes('Crear usuario')")
        await cdp.type('input[name=username]','ui_managed')
        await cdp.type('input[name=password]',password)
        await cdp.evaluate("(()=>{let s=document.querySelector('select[name=role_id]');s.value=[...s.options].find(o=>o.textContent==='Producción').value;})()")
        await cdp.click('Crear cuenta')
        await cdp.until("[...document.querySelectorAll('summary')].some(s=>s.textContent.includes('ui_managed'))")
        await cdp.evaluate("(()=>{let d=[...document.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent.includes('ui_managed'));d.open=true;d.querySelector('input[name=username]').value='ui_renamed';d.querySelector('form').requestSubmit();})()")
        await cdp.until("[...document.querySelectorAll('summary')].some(s=>s.textContent.includes('ui_renamed'))")
        await cdp.click('Inventario')
        await cdp.until("Boolean(document.querySelector('input[type=file]'))")
        root=(await cdp.call('DOM.getDocument'))['root']['nodeId']
        node=(await cdp.call('DOM.querySelector',{'nodeId':root,'selector':'input[type=file]'}))['nodeId']
        await cdp.call('DOM.setFileInputFiles',{'nodeId':node,'files':[str(inventory_file)]})
        await cdp.click('Revisar archivo sin guardar')
        await cdp.until("document.body.textContent.includes('Archivo válido para confirmar')")
        await cdp.click('Confirmar importación de 1 filas')
        await cdp.until("document.body.textContent.includes('Importación completada: 1 rollos nuevos')")
        print('Chrome: usuario editado e inventario importado',flush=True)
        await cdp.click('Nueva solicitud')
        await cdp.until("Boolean(document.querySelector('select[name=press_id]'))")
        # Trigger native change events for select and uncontrolled input fields.
        await cdp.evaluate("document.querySelector('select[name=press_id]').value='1';document.querySelector('select[name=process_id]').value='1';document.querySelector('input[name=destination]').value='DANLY - recepción';document.querySelector('input[name=required_at]').value='2099-01-01T12:00'")
        await cdp.evaluate("(()=>{let s=[...document.querySelectorAll('select')].find(s=>s.options[0].text.includes('Número de parte'));s.value='1';s.dispatchEvent(new Event('change',{bubbles:true}));})()")
        await cdp.click('Crear solicitud')
        await cdp.until("document.body.textContent.includes('REQ-000001')")
        await cdp.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('REQ-000001')).click()")
        for label in ['Validar existencia y especificación','Asignar operador','Iniciar preparación','Confirmar material localizado','Iniciar traslado','Confirmar entrega']:
            await cdp.until('document.body.textContent.includes('+json.dumps(label)+')')
            if label=='Asignar operador':
                await cdp.evaluate("document.querySelector('[data-testid=request-editor]').open=true")
                await cdp.type('[data-testid=request-editor] input[type=number]','2')
                await cdp.type('[data-testid=request-editor] textarea[name=justification]','Programa requiere un segundo rollo')
                await cdp.click('Guardar solicitud y ajustar reservas')
                await cdp.until("document.body.textContent.includes('2 solicitados')")
                await cdp.evaluate("document.querySelector('select[name=operator_id]').value='1'")
            if label=='Iniciar preparación':
                await cdp.type('textarea[placeholder="Describe la incidencia"]','Pasillo temporalmente obstruido durante la prueba')
                await cdp.click('Registrar incidencia')
                await cdp.until("document.body.textContent.includes('Resolver incidencia')")
                await cdp.type('textarea[placeholder="Resolución obligatoria"]','Pasillo liberado para continuar el movimiento')
                await cdp.click('Resolver incidencia')
                await cdp.until("document.body.textContent.includes('Iniciar preparación')")
            if label=='Confirmar entrega':await cdp.type('input[name=receiver]','Supervisor prueba navegador')
            await cdp.click(label)
        await cdp.until("document.body.textContent.includes('Último responsable receptor: Supervisor prueba navegador')")
        print('Chrome: solicitud editada y entregada',flush=True)
        await cdp.evaluate("document.querySelector('button[aria-label=\"Cerrar detalle\"]').click()")
        await cdp.click('Cambio de turno')
        await cdp.until("document.body.textContent.includes('Entregar al siguiente turno')")
        await cdp.evaluate(f"document.querySelector('select[name=receiving_user_id]').value='{recipient}'")
        await cdp.type('textarea[name=notes]','Revisados pendientes y continuidad de operación')
        await cdp.click('Enviar pendientes para aceptación')
        await cdp.until("document.body.textContent.includes('Entrega #1')")
        await cdp.click('Simulación')
        await cdp.click('Ejecutar simulación')
        await cdp.until("document.body.textContent.includes('Riesgo simulado de paro')")
        await cdp.click('Resumen')
        await cdp.until("Boolean(document.querySelector('[data-testid=operational-dashboard]')) && document.body.textContent.includes('Movimientos por turno')")
        await cdp.evaluate("[...document.querySelectorAll('[aria-pressed]')].find(b=>b.textContent.includes('Entregadas')).click()")
        await cdp.until("document.body.textContent.includes('Solicitudes · Entregadas')")
        await cdp.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('REQ-000001')).click()")
        await cdp.until("Boolean(document.querySelector('button[aria-label=\"Cerrar detalle\"]'))")
        await cdp.evaluate("document.querySelector('button[aria-label=\"Cerrar detalle\"]').click()")
        await cdp.evaluate("document.querySelector('input[name=start]').value='2099-01-01';document.querySelector('input[name=end]').value='2099-01-02'")
        await cdp.click('Consultar periodo')
        await cdp.until("document.body.textContent.includes('Sin solicitudes para este periodo')")
        assert 'start=2099-01-01' in await cdp.evaluate("document.querySelector('[data-testid=dashboard-export]').getAttribute('href')"), 'Export period does not match filters'
        await cdp.click('Ver todo')
        await cdp.until("document.body.textContent.includes('1 folio')")
        await cdp.until("Boolean(document.querySelector('[aria-label^=\"Distribución de\"] svg path'))")
        positions=await cdp.evaluate("(()=>{let a=document.querySelector('[data-testid=dashboard-filter]').getBoundingClientRect();let b=document.querySelector('[data-testid=dashboard-export]').getBoundingClientRect();return {a:a.bottom,b:b.bottom,ah:a.height,bh:b.height};})()")
        assert abs(positions['a']-positions['b'])<=1 and abs(positions['ah']-positions['bh'])<=1,positions
        await asyncio.sleep(.25)  # Allow the navigation color transition to finish before capture.
        artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
        screenshot=await cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
        (artifacts/'resumen-browser.png').write_bytes(base64.b64decode(screenshot['data']))
        await cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await asyncio.sleep(.3)
        assert await cdp.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Dashboard exceeds mobile viewport'
        mobile=await cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
        (artifacts/'resumen-mobile.png').write_bytes(base64.b64decode(mobile['data']))
        await cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await cdp.click('Administración');await cdp.click('Respaldos')
        await cdp.until("document.body.textContent.includes('Crear respaldo ahora')")
        await cdp.click('Crear respaldo ahora')
        await cdp.until("document.body.textContent.includes('Respaldo creado:')")
        await cdp.click('Mi cuenta')
        await cdp.until("Boolean(document.querySelector('input[name=current_password]'))")
        await cdp.type('input[name=current_password]',password)
        await cdp.type('input[name=new_password]',password+'X')
        await cdp.type('input[name=confirm_password]',password+'X')
        await cdp.click('Cambiar contraseña')
        await cdp.until("document.body.textContent.includes('Contraseña actualizada')")
        print('Chrome: respaldo y contraseña verificados',flush=True)
        await cdp.click('Cerrar sesión')
        await cdp.until("Boolean(document.querySelector('input[autocomplete=username]'))")
        await cdp.type('input[autocomplete=username]','incoming_browser');await cdp.type('input[type=password]',password)
        await cdp.click('Entrar al sistema');await cdp.until("document.body.textContent.includes('Resumen operativo')")
        await cdp.click('Cambio de turno')
        await cdp.until("document.body.textContent.includes('Aceptar recepción de pendientes')")
        await cdp.type('textarea[aria-label="Recepción de entrega 1"]','Confirmo recepción de pendientes')
        await cdp.click('Aceptar recepción de pendientes')
        await cdp.until("document.body.textContent.includes('Aceptó incoming_browser')")
        await cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        assert await cdp.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page exceeds mobile viewport'
        assert not cdp.errors,cdp.errors
        print('BROWSER OK: user creation/edit, CSV preview/commit, request revision/reservations, full workflow, handover/acceptance, simulation, backup, own password, mobile viewport; no JS exceptions.')

def main():
    if not CHROME.exists():raise RuntimeError('Chrome executable not found')
    processes=[];logs=[]
    with tempfile.TemporaryDirectory(prefix='metaride-browser-') as temp:
        env=os.environ.copy();password=secrets.token_urlsafe(24)
        env.update(DATABASE_URL=os.getenv('METARIDE_BROWSER_DATABASE_URL') or 'sqlite:///'+str(Path(temp)/'browser.db'),METARIDE_ADMIN_PASSWORD=password,CORS_ORIGINS=WEB,VITE_API_URL=API,BACKUP_DIR=str(Path(temp)/'backups'))
        try:
            subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=BACKEND,env=env,check=True,capture_output=True)
            for args,cwd in [([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8107'],BACKEND),([shutil.which('npm.cmd'),'run','dev','--','--host','127.0.0.1','--port','5179','--strictPort'],ROOT)]:
                log=tempfile.TemporaryFile();logs.append(log)
                processes.append(subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW))
            wait_http(API+'/salud');wait_http(WEB)
            jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            def post(path,payload):
                with client.open(urllib.request.Request(API+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})) as response:return json.load(response)
            post('/api/auth/login',{'username':'admin','password':password})
            part=post('/api/catalogs/parts',{'name':'BROWSER-PART','specification':'Acero de prueba'})
            location=post('/api/catalogs/locations',{'name':'ALM-01'})
            post('/api/inventory',{'code':'BROWSER-ROLL','part_id':part['id'],'location_id':location['id'],'kg':900})
            with client.open(API+'/api/catalogs') as response:catalogs=json.load(response)
            role=next(r for r in catalogs['roles'] if r['name']=='Operador')
            recipient=post('/api/users',{'username':'incoming_browser','password':password,'role_id':role['id']})
            processes.append(subprocess.Popen([str(CHROME),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9337','--user-data-dir='+str(Path(temp)/'profile'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW))
            wait_http('http://127.0.0.1:9337/json')
            inventory_file=Path(temp)/'browser-inventory.csv'
            inventory_file.write_text('codigo_rollo,numero_parte,ubicacion,kg,estado\nBROWSER-CSV,BROWSER-PART,ALM-01,1100,DISP\n',encoding='utf-8')
            asyncio.run(scenario(password,recipient['id'],inventory_file))
        except Exception:
            for log in logs:
                log.seek(0);print(log.read().decode('utf-8',errors='replace')[-5000:],flush=True)
            raise
        finally:
            for process in reversed(processes):
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                process.wait(timeout=10)
            for log in logs:log.close()

if __name__=='__main__':main()
