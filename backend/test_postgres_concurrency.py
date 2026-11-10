"""Real PostgreSQL transactions competing for steel, operators and equipment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import os
import tempfile
import threading
import unittest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from database import engine,Session,Request,Roll,User
from main import app

@unittest.skipUnless(engine.dialect.name=='postgresql' and os.getenv('METARIDE_TEST_DATABASE_URL'),'Requires an explicitly disposable PostgreSQL test database')
class PostgresConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='metaride-pg-concurrency-')
        os.environ['BACKUP_DIR']=cls.temp.name
        cls.context=TestClient(app);cls.client=cls.context.__enter__()
        result=cls.client.post('/api/auth/login',json={'username':'admin','password':'Testing-only-Admin-1234'})
        assert result.status_code==200,result.text
        cls.admin=result.json();cls.catalogs=cls.client.get('/api/catalogs').json()
    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None);engine.dispose();cls.temp.cleanup()
    def resource(self,rolls):
        code=uuid.uuid4().hex[:12]
        part=self.client.post('/api/catalogs/parts',json={'name':'RACE-'+code,'specification':'Steel concurrency test'}).json()
        location=self.client.post('/api/catalogs/locations',json={'name':'LOC-'+code}).json()
        ids=[]
        for n in range(rolls):
            result=self.client.post('/api/inventory',json={'code':f'{code}-{n}','part_id':part['id'],'location_id':location['id'],'kg':1000})
            self.assertEqual(result.status_code,201,result.text);ids.append(result.json()['id'])
        return part,location,ids
    def request(self,part,preferred=None):
        payload={'key':str(uuid.uuid4()),'press_id':self.catalogs['presses'][0]['id'],'process_id':self.catalogs['processes'][0]['id'],'required_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'items':[{'part_id':part['id'],'quantity':1,'preferred_roll_id':preferred}]}
        result=self.client.post('/api/requests',json=payload);self.assertEqual(result.status_code,201,result.text);return result.json()
    def operator(self,role='Operador'):
        role_id=next(r['id'] for r in self.catalogs['roles'] if r['name']==role)
        name='race_'+uuid.uuid4().hex[:12]
        result=self.client.post('/api/users',json={'username':name,'password':'Race-Password-1234','role_id':role_id})
        self.assertEqual(result.status_code,201,result.text);return result.json()
    def action(self,r,action,**values):
        return self.client.post(f"/api/requests/{r['id']}/actions",json={'version':r['version'],'action':action,**values})
    def parallel(self,functions):
        barrier=threading.Barrier(len(functions))
        def call(function):barrier.wait(timeout=20);return function()
        with ThreadPoolExecutor(max_workers=len(functions)) as pool:return list(pool.map(call,functions))
    def test_01_one_roll_has_one_reservation(self):
        part,_,rolls=self.resource(1)
        first=self.request(part,rolls[0]);second=self.request(part,rolls[0])
        results=self.parallel([lambda:self.action(first,'validate'),lambda:self.action(second,'validate')])
        self.assertEqual(sorted(r.status_code for r in results),[200,409],[r.text for r in results])
        with Session() as db:
            roll=db.get(Roll,rolls[0]);self.assertEqual(roll.status,'RESERVADO');self.assertIn(roll.request_id,[first['id'],second['id']])
            self.assertEqual(sum(db.get(Request,r['id']).state=='Validado' for r in [first,second]),1)
    def test_02_eight_requests_reserve_distinct_rolls(self):
        part,_,rolls=self.resource(8);requests=[self.request(part) for _ in range(8)]
        results=self.parallel([lambda r=r:self.action(r,'validate') for r in requests])
        self.assertTrue(all(r.status_code==200 for r in results),[r.text for r in results])
        selected=[r.json()['rolls'][0]['id'] for r in results]
        self.assertEqual(len(set(selected)),8);self.assertEqual(set(selected),set(rolls))
    def test_03_operator_not_double_assigned(self):
        part,_,_=self.resource(2);operator=self.operator()
        requests=[self.action(self.request(part),'validate').json() for _ in range(2)]
        results=self.parallel([lambda r=r:self.action(r,'assign',operator_id=operator['id']) for r in requests])
        self.assertEqual(sorted(r.status_code for r in results),[200,409],[r.text for r in results])
        with Session() as db:self.assertEqual(len(list(db.scalars(select(Request).where(Request.operator_id==operator['id'],Request.state=='Tomado')))),1)
    def test_04_forklift_not_double_assigned(self):
        part,_,_=self.resource(2);operators=[self.operator() for _ in range(2)]
        lift=self.client.post('/api/catalogs/forklifts',json={'name':'LIFT-'+uuid.uuid4().hex[:10]}).json()
        requests=[self.action(self.request(part),'validate').json() for _ in range(2)]
        results=self.parallel([lambda r=r,op=op:self.action(r,'assign',operator_id=op['id'],forklift_id=lift['id']) for r,op in zip(requests,operators)])
        self.assertEqual(sorted(r.status_code for r in results),[200,409],[r.text for r in results])
        with Session() as db:self.assertEqual(len(list(db.scalars(select(Request).where(Request.forklift_id==lift['id'],Request.state=='Tomado')))),1)
    def test_05_one_version_has_one_transition(self):
        part,_,_=self.resource(0);r=self.request(part)
        results=self.parallel([lambda:self.action(r,'incident',notes='First concurrent report'),lambda:self.action(r,'incident',notes='Second concurrent report')])
        self.assertEqual(sorted(x.status_code for x in results),[200,409],[x.text for x in results])
        current=next(x for x in self.client.get('/api/requests').json() if x['id']==r['id'])
        self.assertEqual(len(current['incidents']),1);self.assertEqual(current['version'],r['version']+1)
    def test_06_location_deactivation_cannot_race_reservation(self):
        part,location,rolls=self.resource(1);r=self.request(part)
        results=self.parallel([lambda:self.action(r,'validate'),lambda:self.client.patch(f"/api/catalogs/locations/{location['id']}",json={'name':location['code'],'version':location['version'],'active':False})])
        self.assertTrue(all(result.status_code<500 for result in results),[x.text for x in results])
        self.assertNotEqual([result.status_code for result in results],[200,200])
        with Session() as db:
            from database import Location
            if db.get(Roll,rolls[0]).status=='RESERVADO':self.assertTrue(db.get(Location,location['id']).active)
    def test_07_stale_admin_cannot_demote_the_other(self):
        accounts=[self.operator('Administrador') for _ in range(2)]
        production=next(r['id'] for r in self.catalogs['roles'] if r['name']=='Producción')
        records={u['id']:u for u in self.client.get('/api/users').json()}
        with TestClient(app) as a,TestClient(app) as b:
            for client,user in zip([a,b],accounts):self.assertEqual(client.post('/api/auth/login',json={'username':user['username'],'password':'Race-Password-1234'}).status_code,200)
            def demote(client,target):
                row=records[target['id']]
                return client.patch(f"/api/users/{row['id']}",json={'username':row['username'],'role_id':production,'active':True,'version':row['version']})
            results=self.parallel([lambda:demote(a,accounts[1]),lambda:demote(b,accounts[0])])
            self.assertEqual(sorted(result.status_code for result in results),[200,403],[x.text for x in results])
        with Session() as db:self.assertEqual(sum(db.get(User,account['id']).role.name=='Administrador' for account in accounts),1)
    def test_08_database_constraint_protects_resource(self):
        part,_,_=self.resource(1);operator=self.operator();r=self.action(self.request(part),'validate').json()
        self.assertEqual(self.action(r,'assign',operator_id=operator['id']).status_code,200)
        with Session() as db:
            db.add(Request(key=str(uuid.uuid4()),press_id=r['press_id'],process_id=r['process_id'],requester_id=self.admin['id'],operator_id=operator['id'],priority='Normal',state='Tomado',required_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=1)))
            with self.assertRaises(IntegrityError):db.commit()
            db.rollback()

if __name__=='__main__':unittest.main(verbosity=2)
