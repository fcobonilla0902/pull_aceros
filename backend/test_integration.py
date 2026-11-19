"""Las pruebas de integración utilizan un archivo temporal de SQLite, migraciones reales y sesiones reales."""
import os
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient

_temp = tempfile.TemporaryDirectory(prefix='metaride-tests-')
os.environ['DATABASE_URL'] = os.getenv('METARIDE_TEST_DATABASE_URL') or 'sqlite:///' + str(Path(_temp.name)/'test.db')
os.environ['BACKUP_DIR']=str(Path(_temp.name)/'backups')
os.environ['METARIDE_ADMIN_PASSWORD'] = 'Testing-only-Admin-1234'
from main import app, Params, una_corrida
from database import engine, Session, Request, Roll, SimulationRun, Handover
from operations import shift_at

class OperationalIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config=Config(str(Path(__file__).with_name('alembic.ini')))
        command.upgrade(config,'head')
        cls.context=TestClient(app); cls.client=cls.context.__enter__()
        response=cls.client.post('/api/auth/login',json={'username':'admin','password':os.environ['METARIDE_ADMIN_PASSWORD']})
        assert response.status_code==200,response.text
        cls.admin=response.json()
        cls.catalogs=cls.client.get('/api/catalogs').json()
        for kind,name in [('parts','TEST-STEEL'),('locations','A-01'),('forklifts','MC-01')]:
            response=cls.client.post('/api/catalogs/'+kind,json={'name':name,'specification':'Grade A / 2mm'})
            assert response.status_code==201,response.text
        cls.catalogs=cls.client.get('/api/catalogs').json()
        cls.part=cls.catalogs['parts'][0]['id'];cls.location=cls.catalogs['locations'][0]['id']
    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None);engine.dispose();_temp.cleanup()
    def create(self,qty=1):
        payload={'key':str(uuid.uuid4()),'press_id':self.catalogs['presses'][0]['id'],'process_id':self.catalogs['processes'][0]['id'],'required_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'items':[{'part_id':self.part,'quantity':qty}]}
        response=self.client.post('/api/requests',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        return response.json(),payload
    def action(self,r,action,status=200,**kwargs):
        response=self.client.post(f"/api/requests/{r['id']}/actions",json={'action':action,'version':r['version'],**kwargs})
        self.assertEqual(response.status_code,status,response.text)
        return response.json()
    def test_01_auth_and_roles(self):
        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get('/api/requests').status_code,401)
            self.assertEqual(anonymous.post('/simular',json={}).status_code,401)
            production=next(r for r in self.catalogs['roles'] if r['name']=='Producción')
            response=self.client.post('/api/users',json={'username':'production','password':'Production-test-123','role_id':production['id']})
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(anonymous.post('/api/auth/login',json={'username':'production','password':'Production-test-123'}).status_code,200)
            self.assertEqual(anonymous.post('/api/inventory',json={'code':'forbidden','part_id':self.part,'location_id':self.location,'kg':600}).status_code,403)
            anonymous.post('/api/auth/logout')
            self.assertEqual(anonymous.get('/api/auth/me').status_code,401)
    def test_02_full_workflow_and_atomicity(self):
        for code,kg in [('ROLL-A',1000),('ROLL-B',500),('ROLL-C',1200)]:
            self.assertEqual(self.client.post('/api/inventory',json={'code':code,'part_id':self.part,'location_id':self.location,'kg':kg}).status_code,201)
        r,payload=self.create()
        same=self.client.post('/api/requests',json=payload).json();self.assertEqual(r['id'],same['id'])
        self.action(r,'transport',409)
        r=self.action(r,'validate');self.assertEqual(r['state'],'Validado')
        self.action(r,'assign',422)
        r=self.action(r,'assign',operator_id=self.admin['id'],forklift_id=self.catalogs['forklifts'][0]['id'])
        old=r.copy();r=self.action(r,'prepare');self.action(old,'prepare',409)
        r=self.action(r,'incident',notes='Material bloqueado en pasillo');self.assertEqual(r['state'],'Con incidencia')
        r=self.action(r,'resolve',notes='Pasillo liberado');self.assertEqual(r['state'],'En preparación')
        r=self.action(r,'ready');r=self.action(r,'transport')
        self.action(r,'deliver',422)
        r=self.action(r,'deliver',receiver='Supervisor Producción');self.assertEqual(r['state'],'Entregado')
        self.assertEqual(r['items'][0]['delivered'],1)
        delivery_event=next(e for e in r['events'] if e['action']=='deliver')
        self.assertIn('Cantidad: 1 | Rollos: ROLL-A',delivery_event['detail'])
        self.assertFalse(delivery_event['detail'].startswith(' |'))
        self.action(r,'cancel',409,notes='No puede cancelar una entrega')
        with Session() as db:
            self.assertEqual(db.get(Request,r['id']).receiver,'Supervisor Producción')
            self.assertEqual(db.query(Roll).filter_by(code='ROLL-B').one().status,'DISP')
        too_many,_=self.create(qty=10);self.action(too_many,'validate',409)
        with Session() as db: self.assertEqual(db.query(Roll).filter_by(code='ROLL-C').one().status,'DISP')
        r2,_=self.create();r2=self.action(r2,'validate');r2=self.action(r2,'cancel',notes='Cambio de programa');self.assertEqual(r2['state'],'Cancelado')
        handover=self.client.post('/api/handovers',json={'incoming_shift':'T2','notes':'Continuar pendientes'});self.assertEqual(handover.status_code,201)
        self.assertIn(too_many['id'],__import__('json').loads(handover.json()['pending']))
        self.assertEqual(self.client.get('/api/metrics').json()['delivered'],1)
        export=self.client.get('/api/history/export');self.assertEqual(export.status_code,200);self.assertIn('text/csv',export.headers['content-type'])
    def test_03_partial_delivery(self):
        for code in ['PARTIAL-A','PARTIAL-B']:
            response=self.client.post('/api/inventory',json={'code':code,'part_id':self.part,'location_id':self.location,'kg':1100})
            self.assertEqual(response.status_code,201,response.text)
        r,_=self.create(qty=2)
        r=self.action(r,'validate')
        r=self.action(r,'assign',operator_id=self.admin['id'])
        r=self.action(r,'prepare');r=self.action(r,'ready');r=self.action(r,'transport')
        first=r['rolls'][0]['id']
        r=self.action(r,'deliver',receiver='Receiver A',roll_ids=[first])
        self.assertEqual(r['state'],'Entrega parcial');self.assertEqual(r['items'][0]['delivered'],1)
        first_code=next(roll['code'] for roll in r['rolls'] if roll['id']==first)
        self.assertIn('Cantidad: 1 | Rollos: '+first_code,r['events'][-1]['detail'])
        self.action(r,'deliver',422,receiver='Receiver A',roll_ids=[first])
        r=self.action(r,'deliver',receiver='Receiver B')
        self.assertEqual(r['state'],'Entregado');self.assertEqual(r['items'][0]['delivered'],2)
    def test_04_preferred_roll(self):
        response=self.client.post('/api/inventory',json={'code':'SPECIFIC-ROLL','part_id':self.part,'location_id':self.location,'kg':1250})
        self.assertEqual(response.status_code,201,response.text)
        roll_id=response.json()['id']
        payload={'key':str(uuid.uuid4()),'press_id':self.catalogs['presses'][0]['id'],'process_id':self.catalogs['processes'][0]['id'],'required_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'items':[{'part_id':self.part,'quantity':1,'preferred_roll_id':roll_id}]}
        response=self.client.post('/api/requests',json=payload);self.assertEqual(response.status_code,201,response.text)
        r=self.action(response.json(),'validate')
        self.assertEqual([x['id'] for x in r['rolls']],[roll_id])
        self.action(r,'cancel',notes='Finished preferred-roll test')
    def test_05_simulation(self):
        response=self.client.post('/simular',json={'solicitudes':10,'replicas':2})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(response.json()['corridas']),2)
        self.assertEqual(len(self.client.get('/api/simulations').json()),1)
        calibration=self.client.get('/api/simulations/calibration').json()
        self.assertEqual(calibration['minimum_samples'],5)
        self.assertEqual(calibration['parameters'],{})
        self.assertEqual(self.client.post('/simular',json={'preparacion_min':20,'preparacion_max':5}).status_code,422)
        a=una_corrida(Params(solicitudes=10),42);b=una_corrida(Params(solicitudes=10),42);self.assertEqual(a,b)
        with Session() as db:self.assertEqual(db.query(SimulationRun).count(),1)
    def test_06_digital_handover_acceptance(self):
        role=next(r for r in self.catalogs['roles'] if r['name']=='Operador')
        accounts=[]
        for name in ['incoming_operator','other_operator']:
            response=self.client.post('/api/users',json={'username':name,'password':'Incoming-password-123','role_id':role['id']})
            self.assertEqual(response.status_code,201,response.text);accounts.append(response.json())
        r,_=self.create()
        payload={'incoming_shift':'T3','receiving_user_id':accounts[0]['id'],'notes':'Atender pendiente de localizar'}
        self.assertEqual(self.client.post('/api/handovers',json={**payload,'receiving_user_id':self.admin['id']}).status_code,422)
        response=self.client.post('/api/handovers',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        h=response.json();self.assertIsNone(h['accepted_at'])
        snapshot=next(i['snapshot'] for i in h['items'] if i['request_id']==r['id'])
        self.assertEqual(snapshot['priority'],'Normal')
        r=self.action(r,'edit',priority='Urgente',notes='Necesidad critica del siguiente turno')
        url=f"/api/handovers/{h['id']}/accept"
        self.assertEqual(self.client.post(url,json={'notes':'Auto recepción inválida'}).status_code,403)
        with TestClient(app) as incoming:
            incoming.post('/api/auth/login',json={'username':'other_operator','password':'Incoming-password-123'})
            self.assertEqual(incoming.post(url,json={'notes':'No es el destinatario'}).status_code,403)
            incoming.post('/api/auth/login',json={'username':'production','password':'Production-test-123'})
            self.assertEqual(incoming.post(url,json={'notes':'Sin permiso de recepción'}).status_code,403)
            incoming.post('/api/auth/login',json={'username':'incoming_operator','password':'Incoming-password-123'})
            self.assertEqual(incoming.post(f"/api/requests/{r['id']}/actions",json={'action':'validate','version':r['version']}).status_code,403)
            self.assertEqual(incoming.post(f"/api/requests/{r['id']}/actions",json={'action':'prepare','version':r['version']}).status_code,403)
            self.assertEqual(incoming.post(url,json={'notes':'x'}).status_code,422)
            response=incoming.post(url,json={'notes':'Recibo y reviso los pendientes'})
            self.assertEqual(response.status_code,200,response.text)
            accepted=response.json();self.assertEqual(accepted['accepted_by_id'],accounts[0]['id']);self.assertIsNotNone(accepted['accepted_at'])
            self.assertEqual(incoming.post(url,json={'notes':'Segundo intento'}).status_code,409)
        with Session() as db:
            self.assertEqual(db.get(Handover,h['id']).accepted_by_id,accounts[0]['id'])
            self.assertIsNone(db.get(Request,r['id']).operator_id)
        saved=next(row for row in self.client.get('/api/handovers').json() if row['id']==h['id'])
        self.assertEqual(next(i['snapshot']['priority'] for i in saved['items'] if i['request_id']==r['id']),'Normal')
    def test_07_deadlines_incident_metrics_and_shift(self):
        r,_=self.create()
        before=self.client.get('/api/metrics').json()
        with Session.begin() as db:
            db.get(Request,r['id']).required_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=15)
        r=self.action(r,'incident',notes='Falta de acero detuvo la prensa',cause='Material no disponible',production_stopped=True)
        self.assertEqual(r['incidents'][0]['cause'],'Material no disponible')
        after=self.client.get('/api/metrics').json()
        self.assertEqual(after['production_stops'],before['production_stops']+1)
        self.assertEqual(after['due_soon'],before['due_soon']+1)
        self.assertTrue(any(x['cause']=='Material no disponible' for x in after['delay_causes']))
        r=self.action(r,'resolve',notes='Rollo recibido y suministro restablecido')
        self.assertIsNotNone(r['incidents'][0]['resolved_at'])
        self.assertGreaterEqual(self.client.get('/api/metrics').json()['downtime_minutes'],0)
        for hour,minute,expected in [(11,59,'T3'),(12,0,'T1'),(19,59,'T1'),(20,0,'T2'),(3,29,'T2'),(3,30,'T3')]:
            self.assertEqual(shift_at(datetime(2026,11,6,hour,minute))['shift'],expected)
        self.assertEqual(shift_at(datetime(2026,11,6,11,59))['date'],'2026-11-05')
        self.assertEqual(self.client.get('/api/metrics?start=2026-12-01&end=2026-01-01').status_code,422)
        self.assertEqual(self.client.get('/api/metrics?start=2099-01-01').json()['delivered'],0)
        export=self.client.get('/api/metrics/export');self.assertEqual(export.status_code,200)
        self.assertIn('movimientos',export.text)
        total_movements=sum(x['movements'] for x in after['movements_by_shift'])
        self.assertEqual(total_movements,3)  # Una confirmación de entrega completa y dos de entrega parcial.
    def test_08_extended_simulation_contract(self):
        params=Params(solicitudes=4,operadores=4,montacargas=4,turno_minutos=60,localizacion_min=3,localizacion_max=3,preparacion_min=4,preparacion_max=4,traslado_min=5,traslado_max=5,probabilidad_incidencia=100,incidencia_min=2,incidencia_max=2,tiempo_requerido_min=10,tolerancia_paro_min=3,distribucion='triangular')
        result=una_corrida(params,10)
        self.assertEqual(result['porcentaje_retraso'],100)
        self.assertEqual(result['porcentaje_riesgo_paro'],100)
        self.assertEqual(result['incidencias_promedio'],4)
        self.assertTrue(all(r['duracion']==14 and r['incidencia'] for r in result['registros']))
        self.assertTrue(0<=result['utilizacion_operadores']<=100)
        self.assertTrue(0<=result['utilizacion_montacargas']<=100)
        other=una_corrida(params.model_copy(update={'montacargas':1,'prioridad':'llegada'}),10)
        exogenous=lambda run:[(r['llegada'],r['urgente'],r['localizacion'],r['preparacion'],r['traslado'],r['tiempo_incidencia']) for r in run['registros']]
        self.assertEqual(exogenous(result),exogenous(other))
        response=self.client.post('/simular',json=params.model_dump());self.assertEqual(response.status_code,200,response.text)
        self.assertIn('no una probabilidad industrial validada',response.json()['nota'])
        self.assertEqual(self.client.post('/simular',json={'localizacion_min':10,'localizacion_max':5}).status_code,422)
    def material(self,label,count=0):
        p=self.client.post('/api/catalogs/parts',json={'name':'MAINT-'+label,'specification':'Acero controlado 2 mm'}).json()
        location=self.client.post('/api/catalogs/locations',json={'name':'LOC-'+label}).json()
        for n in range(count):
            response=self.client.post('/api/inventory',json={'code':f'MAINT-{label}-{n}','part_id':p['id'],'location_id':location['id'],'kg':1000})
            self.assertEqual(response.status_code,201,response.text)
        return p,location
    def request_for(self,part,quantity=1,preferred=None):
        payload={'key':str(uuid.uuid4()),'press_id':self.catalogs['presses'][0]['id'],'process_id':self.catalogs['processes'][0]['id'],'required_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'items':[{'part_id':part['id'],'quantity':quantity,'preferred_roll_id':preferred}]}
        response=self.client.post('/api/requests',json=payload);self.assertEqual(response.status_code,201,response.text)
        return response.json()
    def revision(self,r,**changes):
        return {**{k:r[k] for k in ['press_id','process_id','priority','risk','destination','notes']},'required_at':r['required_at']+'Z','version':r['version'],'justification':'Cambio de programa documentado','items':[{'part_id':i['part_id'],'quantity':i['requested'],'preferred_roll_id':i['preferred_roll_id']} for i in r['items']],**changes}
    def test_09_user_lifecycle(self):
        records=self.client.get('/api/users').json();admin=next(u for u in records if u['id']==self.admin['id'])
        payload={k:admin[k] for k in ['username','role_id','active','version']}
        self.assertEqual(self.client.patch(f"/api/users/{admin['id']}",json={**payload,'active':False}).status_code,409)
        role=next(r for r in self.catalogs['roles'] if r['name']=='Operador')
        production=next(r for r in self.catalogs['roles'] if r['name']=='Producción')
        created=self.client.post('/api/users',json={'username':'managed_user','password':'Maintenance-Password-123','role_id':role['id']}).json()
        with TestClient(app) as account:
            self.assertEqual(account.post('/api/auth/login',json={'username':'managed_user','password':'Maintenance-Password-123'}).status_code,200)
            record=next(u for u in self.client.get('/api/users').json() if u['id']==created['id'])
            update={'username':'renamed_user','role_id':production['id'],'active':True,'version':record['version']}
            response=self.client.patch(f"/api/users/{created['id']}",json=update);self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['role'],'Producción');self.assertEqual(account.get('/api/auth/me').status_code,401)
            self.assertEqual(self.client.patch(f"/api/users/{created['id']}",json=update).status_code,409)
            update['version']=response.json()['version'];update['active']=False
            response=self.client.patch(f"/api/users/{created['id']}",json=update);self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(account.post('/api/auth/login',json={'username':'renamed_user','password':'Maintenance-Password-123'}).status_code,401)
            update['version']=response.json()['version'];update['active']=True
            response=self.client.patch(f"/api/users/{created['id']}",json=update);self.assertEqual(response.status_code,200)
            update['version']=response.json()['version'];update['username']='admin'
            self.assertEqual(self.client.patch(f"/api/users/{created['id']}",json=update).status_code,409)
    def test_10_password_changes_and_resets(self):
        role=next(r for r in self.catalogs['roles'] if r['name']=='Operador')
        account=self.client.post('/api/users',json={'username':'password_user','password':'Original-Password-123','role_id':role['id']}).json()
        with TestClient(app) as first,TestClient(app) as second:
            for client in [first,second]:self.assertEqual(client.post('/api/auth/login',json={'username':'password_user','password':'Original-Password-123'}).status_code,200)
            self.assertEqual(first.post('/api/auth/password',json={'current_password':'wrong','new_password':'Replacement-Password-123'}).status_code,403)
            self.assertEqual(first.post('/api/auth/password',json={'current_password':'Original-Password-123','new_password':'Replacement-Password-123'}).status_code,200)
            self.assertEqual(first.get('/api/auth/me').status_code,200);self.assertEqual(second.get('/api/auth/me').status_code,401)
            self.assertEqual(second.post('/api/auth/login',json={'username':'password_user','password':'Original-Password-123'}).status_code,401)
            self.assertEqual(second.post('/api/auth/login',json={'username':'password_user','password':'Replacement-Password-123'}).status_code,200)
            self.assertEqual(self.client.post(f"/api/users/{account['id']}/password",json={'new_password':'Admin-Reset-Password-123'}).status_code,200)
            self.assertEqual(first.get('/api/auth/me').status_code,401);self.assertEqual(second.get('/api/auth/me').status_code,401)
            self.assertEqual(second.post('/api/auth/login',json={'username':'password_user','password':'Admin-Reset-Password-123'}).status_code,200)
        history=self.client.get('/api/history').text
        self.assertNotIn('Replacement-Password-123',history);self.assertNotIn('Admin-Reset-Password-123',history)
    def test_11_catalog_maintenance(self):
        part,location=self.material('CATALOG',2)
        update={'name':part['code'],'specification':'Otra especificacion','active':True,'version':part['version']}
        self.assertEqual(self.client.patch(f"/api/catalogs/parts/{part['id']}",json=update).status_code,409)
        response=self.client.patch(f"/api/catalogs/locations/{location['id']}",json={'name':location['code'],'active':False,'version':location['version']})
        self.assertEqual(response.status_code,200,response.text)
        r=self.request_for(part);self.action(r,'validate',409)
        location=response.json()
        self.assertFalse(any(x['eligible'] for x in self.client.get('/api/inventory').json() if x['part_id']==part['id']))
        self.assertEqual(self.client.patch(f"/api/catalogs/locations/{location['id']}",json={'name':location['code'],'active':True,'version':location['version']}).status_code,200)
        r=self.action(r,'validate')
        self.assertEqual(self.client.patch(f"/api/catalogs/parts/{part['id']}",json={'name':part['code'],'specification':part['specification'],'active':False,'version':part['version']}).status_code,409)
        lift=self.client.post('/api/catalogs/forklifts',json={'name':'MAINT-LIFT'}).json()
        response=self.client.patch(f"/api/catalogs/forklifts/{lift['id']}",json={'name':lift['code'],'active':False,'version':lift['version']});self.assertEqual(response.status_code,200,response.text)
        lift=response.json();self.action(r,'assign',409,operator_id=self.admin['id'],forklift_id=lift['id'])
        response=self.client.patch(f"/api/catalogs/forklifts/{lift['id']}",json={'name':lift['code'],'active':True,'version':lift['version']});self.assertEqual(response.status_code,200)
        r=self.action(r,'assign',operator_id=self.admin['id'],forklift_id=lift['id'])
        lift=next(l for l in self.client.get('/api/catalogs').json()['forklifts'] if l['id']==lift['id'])
        self.assertEqual(self.client.patch(f"/api/catalogs/forklifts/{lift['id']}",json={'name':lift['code'],'active':False,'version':lift['version']}).status_code,409)
        self.action(r,'cancel',notes='Terminar prueba de catalogos')
    def test_12_request_revision_and_rollback(self):
        a,_=self.material('REV-A',4);b,_=self.material('REV-B',2)
        r=self.action(self.request_for(a,2),'validate');old=r.copy()
        payload=self.revision(r,items=[{'part_id':a['id'],'quantity':3},{'part_id':b['id'],'quantity':1}],priority='Urgente')
        response=self.client.patch(f"/api/requests/{r['id']}",json=payload);self.assertEqual(response.status_code,200,response.text)
        r=response.json();self.assertEqual(len(r['rolls']),4);self.assertEqual(r['priority'],'Urgente')
        self.assertEqual(self.client.patch(f"/api/requests/{r['id']}",json=self.revision(old)).status_code,409)
        state=[(roll['id'],roll['request_id'],roll['status']) for roll in self.client.get('/api/inventory').json()]
        response=self.client.patch(f"/api/requests/{r['id']}",json=self.revision(r,items=[{'part_id':a['id'],'quantity':100}]))
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(state,[(roll['id'],roll['request_id'],roll['status']) for roll in self.client.get('/api/inventory').json()])
        unchanged=next(row for row in self.client.get('/api/requests').json() if row['id']==r['id']);self.assertEqual(unchanged['version'],r['version'])
        response=self.client.patch(f"/api/requests/{r['id']}",json=self.revision(r,items=[{'part_id':a['id'],'quantity':1}]))
        self.assertEqual(response.status_code,200,response.text);r=response.json();self.assertEqual(len(r['rolls']),1)
        r=self.action(r,'assign',operator_id=self.admin['id']);r=self.action(r,'prepare');r=self.action(r,'ready');r=self.action(r,'transport')
        self.assertEqual(self.client.patch(f"/api/requests/{r['id']}",json=self.revision(r,items=[{'part_id':a['id'],'quantity':2}])).status_code,409)
        self.action(r,'deliver',receiver='Revision test receiver')
    def test_13_partial_delivery_revision(self):
        part,_=self.material('PARTIAL-REV',4)
        r=self.action(self.request_for(part,2),'validate');r=self.action(r,'assign',operator_id=self.admin['id'])
        r=self.action(r,'prepare');r=self.action(r,'ready');r=self.action(r,'transport')
        r=self.action(r,'deliver',receiver='First receiver',roll_ids=[r['rolls'][0]['id']])
        response=self.client.patch(f"/api/requests/{r['id']}",json=self.revision(r,items=[{'part_id':part['id'],'quantity':3}]))
        self.assertEqual(response.status_code,200,response.text);r=response.json()
        self.assertEqual(r['state'],'Tomado');self.assertEqual(r['items'][0]['delivered'],1)
        self.assertEqual(self.client.patch(f"/api/requests/{r['id']}",json=self.revision(r,items=[{'part_id':part['id'],'quantity':1}])).status_code,422)
        r=self.action(r,'prepare');r=self.action(r,'ready');r=self.action(r,'transport');r=self.action(r,'deliver',receiver='Final receiver')
        self.assertEqual(r['items'][0]['delivered'],3)
    def test_14_csv_import_review_and_atomicity(self):
        import json
        part,location=self.material('IMPORT')
        def preview(content,update=False,mapping=None):
            return self.client.post('/api/inventory/import/preview',files={'file':('inventario.csv',content.encode('utf-8'),'text/csv')},data={'update_existing':str(update).lower(),'mapping':json.dumps(mapping or {})})
        content=f"codigo_rollo,numero_parte,ubicacion,kg,estado\nCSV-ONE,{part['code']},{location['code']},1000,DISP\nCSV-TWO,{part['code']},{location['code']},1200,DISP\n"
        review=preview(content);self.assertEqual(review.status_code,200,review.text);self.assertTrue(review.json()['valid'])
        self.assertFalse(any(r['code']=='CSV-ONE' for r in self.client.get('/api/inventory').json()))
        token=review.json()['token'];self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':token}).status_code,200)
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':token}).status_code,409)
        self.assertFalse(preview(content).json()['valid'])
        invalid=f"codigo_rollo,numero_parte,ubicacion,kg\nSHOULD-NOT-EXIST,{part['code']},{location['code']},1000\nINVALID,UNKNOWN,{location['code']},1000\n"
        self.assertFalse(preview(invalid).json()['valid']);self.assertFalse(any(r['code']=='SHOULD-NOT-EXIST' for r in self.client.get('/api/inventory').json()))
        custom=f"Identificador,Articulo,Zona,PesoReal\nCSV-MAPPED,{part['code']},{location['code']},900\n"
        self.assertFalse(preview(custom).json()['valid'])
        mapped=preview(custom,mapping={'codigo_rollo':'Identificador','numero_parte':'Articulo','ubicacion':'Zona','kg':'PesoReal'}).json();self.assertTrue(mapped['valid'])
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':mapped['token']}).status_code,200)
        roll=next(r for r in self.client.get('/api/inventory').json() if r['code']=='CSV-ONE')
        update=f"codigo_rollo,numero_parte,ubicacion,kg\nCSV-ONE,{part['code']},{location['code']},1500\nCSV-ATOMIC,{part['code']},{location['code']},1000\n"
        pending=preview(update,True).json();self.assertTrue(pending['valid'])
        r=self.action(self.request_for(part,preferred=roll['id']),'validate')
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':pending['token']}).status_code,409)
        self.assertFalse(any(x['code']=='CSV-ATOMIC' for x in self.client.get('/api/inventory').json()))
        self.action(r,'cancel',notes='Fin prueba importacion')
    def test_15_excel_and_updated_free_inventory(self):
        import io
        from openpyxl import Workbook
        part,location=self.material('XLSX')
        book=Workbook();sheet=book.active;sheet.append(['codigo_rollo','numero_parte','ubicacion','kg','estado']);sheet.append(['XLSX-ONE',part['code'],location['code'],1000,'DISP'])
        buffer=io.BytesIO();book.save(buffer)
        response=self.client.post('/api/inventory/import/preview',files={'file':('inventario.xlsx',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['valid'])
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':response.json()['token']}).status_code,200)
        text=f"codigo_rollo,numero_parte,ubicacion,kg\nXLSX-ONE,{part['code']},{location['code']},800\n"
        response=self.client.post('/api/inventory/import/preview',files={'file':('update.csv',text.encode(),'text/csv')},data={'update_existing':'true'})
        self.assertTrue(response.json()['valid']);token=response.json()['token']
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':token}).status_code,200)
        self.assertEqual(next(r['kg'] for r in self.client.get('/api/inventory').json() if r['code']=='XLSX-ONE'),800)
        sheet['D2']='=1+1';buffer=io.BytesIO();book.save(buffer);book.close()
        self.assertEqual(self.client.post('/api/inventory/import/preview',files={'file':('formula.xlsx',buffer.getvalue(),'application/octet-stream')}).status_code,422)
        self.assertEqual(self.client.post('/api/inventory/import/preview',files={'file':('broken.xlsx',b'broken','application/octet-stream')}).status_code,422)
        self.assertEqual(self.client.get('/api/inventory/import/template').status_code,200)
    def test_stock_workbook_imports_all_columns(self):
        from io import BytesIO
        from openpyxl import load_workbook

        template = self.client.get('/api/inventory/import/template?layout=stock')
        self.assertEqual(template.status_code, 200)
        book = load_workbook(BytesIO(template.content))
        sheet = book.active
        self.assertEqual(sheet.max_column, 17)
        sheet['A1'] = 'Número de artículo'
        sheet['G1'] = 'Planta de almacén'
        sheet['J1'] = 'Lote / N.º de serie'
        sheet['L1'] = 'Cantidad de existencias'
        sheet['M1'] = 'U.M.'
        sheet['N1'] = 'Fecha de recepción'
        sheet['N2'] = datetime(2024, 6, 25)

        def preview(unit):
            sheet['M2'] = unit
            buffer = BytesIO()
            book.save(buffer)
            response = self.client.post('/api/inventory/import/preview', files={
                'file': ('existencias.xlsx', buffer.getvalue(), 'application/octet-stream'),
            })
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        self.assertFalse(preview('PZ')['valid'])
        sheet['M2'] = 'KG'
        original = [cell.value for cell in sheet[2]]
        other_location = original.copy()
        other_location[7] = '1602OB'
        sheet.append(other_location)
        sheet.append(original)
        result = preview('KG')
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['source_layout'])
        self.assertEqual((result['creates'], result['duplicates']), (2, 1))
        self.assertEqual(result['sample'][0]['kg'], 3731)
        self.assertEqual(result['sample'][0]['source_data']['Fcha Recepcn'], '25/06/2024')
        self.assertEqual(result['sample'][0]['source_data']['Planta'], '100215')
        self.assertFalse(any(p['code'] == '03003AA' for p in self.client.get('/api/catalogs').json()['parts']))
        response = self.client.post('/api/inventory/import/commit', json={'token': result['token']})
        self.assertEqual(response.status_code, 200, response.text)
        roll = next(r for r in self.client.get('/api/inventory').json() if r['code'] == 'AX0196040005')
        self.assertEqual((roll['part'], roll['location'], roll['kg']), ('03003AA', '1601OB', 3731))
        self.assertEqual(roll['source_data'], result['sample'][0]['source_data'])
        same_lot = [r for r in self.client.get('/api/inventory').json() if (r['source_data'] or {}).get('Lote/Serie') == 'AX0196040005']
        self.assertEqual({r['location'] for r in same_lot}, {'1601OB', '1602OB'})
        self.assertEqual(len({r['code'] for r in same_lot}), 2)

        sheet.delete_rows(2, 3)
        sheet.append(other_location)
        sheet.append(original)
        buffer = BytesIO()
        book.save(buffer)
        book.close()
        response = self.client.post('/api/inventory/import/preview', files={
            'file': ('existencias.xlsx', buffer.getvalue(), 'application/octet-stream'),
        }, data={'update_existing': 'true'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['unchanged'], 2, response.text)

    @unittest.skipIf(engine.dialect.name!='sqlite','Covered by the PostgreSQL dump/restore test')
    def test_16_backup_and_offline_restore(self):
        import json,sqlite3,subprocess,sys
        from backups import database_path,backup_dir
        response=self.client.post('/api/backups',json={});self.assertEqual(response.status_code,201,response.text)
        name=response.json()['name'];download=self.client.get('/api/backups/'+name)
        self.assertEqual(download.status_code,200);self.assertTrue(download.content.startswith(b'SQLite format 3'))
        self.assertTrue(any(b['name']==name for b in self.client.get('/api/backups').json()))
        env=os.environ.copy();env['BACKUP_DIR']=str(backup_dir())
        commandline=[sys.executable,str(Path(__file__).with_name('manage.py')),'restore',name,'--confirm','RESTAURAR']
        blocked=subprocess.run(commandline,env=env,capture_output=True,text=True)
        self.assertNotEqual(blocked.returncode,0);self.assertIn('uso',blocked.stderr)
        target=Path(_temp.name)/'restore-target.db'
        with closing(sqlite3.connect(database_path())) as original,closing(sqlite3.connect(target)) as destination,destination:original.backup(destination)
        with closing(sqlite3.connect(target)) as db,db:db.execute("INSERT INTO parts(code,specification,active,version) VALUES('AFTER-SNAPSHOT','Recovery marker',1,1)")
        env['DATABASE_URL']='sqlite:///'+str(target)
        restored=subprocess.run(commandline,env=env,capture_output=True,text=True)
        self.assertEqual(restored.returncode,0,restored.stderr)
        recovery=json.loads(restored.stdout)['recovery']
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM parts WHERE code='AFTER-SNAPSHOT'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        with closing(sqlite3.connect(backup_dir()/recovery)) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM parts WHERE code='AFTER-SNAPSHOT'").fetchone()[0],1)
        (backup_dir()/'corrupt.db').write_bytes(b'not sqlite')
        commandline[commandline.index(name)]='corrupt.db'
        self.assertNotEqual(subprocess.run(commandline,env=env,capture_output=True).returncode,0)
        target.with_suffix('.maintenance.lock').unlink(missing_ok=True)
    def test_17_import_staleness_and_admin_permissions(self):
        import json
        part,location=self.material('STALE',1)
        roll=next(r for r in self.client.get('/api/inventory').json() if r['part_id']==part['id'])
        text=f"codigo_rollo,numero_parte,ubicacion,kg\n{roll['code']},{part['code']},{location['code']},1500\n"
        response=self.client.post('/api/inventory/import/preview',files={'file':('stale.csv',text.encode(),'text/csv')},data={'update_existing':'true'})
        self.assertEqual(response.status_code,200,response.text);token=response.json()['token']
        with Session.begin() as db:
            changed=db.get(Roll,roll['id']);changed.kg=1100;changed.version+=1
        self.assertEqual(self.client.post('/api/inventory/import/commit',json={'token':token}).status_code,409)
        self.assertEqual(next(r['kg'] for r in self.client.get('/api/inventory').json() if r['id']==roll['id']),1100)
        with TestClient(app) as production:
            self.assertEqual(production.post('/api/auth/login',json={'username':'production','password':'Production-test-123'}).status_code,200)
            self.assertEqual(production.get('/api/backups').status_code,403)
            self.assertEqual(production.post('/api/backups',json={}).status_code,403)
            self.assertEqual(production.post(f"/api/users/{self.admin['id']}/password",json={'new_password':'Should-Not-Apply-123'}).status_code,403)
            self.assertEqual(production.patch(f"/api/catalogs/parts/{part['id']}",json={'name':part['code'],'specification':part['specification'],'version':part['version'],'active':False}).status_code,403)
            self.assertEqual(production.post('/api/inventory/import/commit',json={'token':token}).status_code,403)
    @unittest.skipUnless(engine.dialect.name=='postgresql','PostgreSQL only')
    def test_18_postgres_backup_restore(self):
        import json,subprocess,sys
        from sqlalchemy import create_engine,text
        from backups import staging_database,pg_command,backup_dir
        response=self.client.post('/api/backups',json={});self.assertEqual(response.status_code,201,response.text)
        name=response.json()['name'];self.assertTrue(name.endswith('.dump'))
        self.assertEqual(self.client.get('/api/backups/'+name).content[:5],b'PGDMP')
        commandline=[sys.executable,str(Path(__file__).with_name('manage.py')),'restore',name,'--confirm','RESTAURAR']
        blocked=subprocess.run(commandline,env=os.environ.copy(),capture_output=True,text=True)
        self.assertNotEqual(blocked.returncode,0);self.assertIn('uso',blocked.stderr)
        with staging_database('metaride_test_restore_') as target:
            pg_command('pg_restore',['--clean','--if-exists','--no-owner','--no-privileges','--exit-on-error','--single-transaction','--dbname',target.database,backup_dir()/name],target)
            resource=create_engine(target)
            try:
                with resource.begin() as connection:connection.execute(text("INSERT INTO parts(code,specification,active,version) VALUES('AFTER-PG-SNAPSHOT','Restore marker',TRUE,1)"))
                environment=os.environ.copy();environment['DATABASE_URL']=target.render_as_string(hide_password=False)
                restored=subprocess.run(commandline,env=environment,capture_output=True,text=True)
                self.assertEqual(restored.returncode,0,restored.stderr)
                recovery=json.loads(restored.stdout)['recovery'];self.assertTrue((backup_dir()/recovery).exists())
                with resource.connect() as connection:
                    self.assertEqual(connection.scalar(text("SELECT count(*) FROM parts WHERE code='AFTER-PG-SNAPSHOT'")),0)
                    self.assertEqual(connection.scalar(text('SELECT count(*) FROM sessions')),0)
                    self.assertEqual(connection.scalar(text("SELECT count(*) FROM audit WHERE action='Base restaurada'")),1)
                (backup_dir()/'corrupt.dump').write_bytes(b'invalid archive')
                commandline[commandline.index(name)]='corrupt.dump'
                self.assertNotEqual(subprocess.run(commandline,env=environment,capture_output=True).returncode,0)
            finally:resource.dispose()

if __name__=='__main__': unittest.main(verbosity=2)
