from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import Manufacturer, Material, PrintJob, PrintJobSpool, PrintJobStatus, PrintSpoolLock, Spool, SpoolStatus, WeightHistory

@pytest.fixture
def env(tmp_path):
 e=create_database_engine(f'sqlite+pysqlite:///{tmp_path}/api.db'); Base.metadata.create_all(e); F=create_session_factory(e)
 with F() as s:
  m=Manufacturer(name='M'); mat=Material(name='PLA',category='PLA'); s.add_all([m,mat]); s.flush()
  ss=[Spool(code=f'FIL-{i:04}',manufacturer_id=m.id,material_id=mat.id,color_name='x',initial_filament_weight_g=Decimal('1000'),current_filament_weight_g=Decimal('500')) for i in range(12)]; s.add_all(ss); s.commit(); ids=[x.id for x in ss]
 def dep():
  with F() as s: yield s
 app.dependency_overrides[get_db]=dep
 yield TestClient(app),F,ids
 app.dependency_overrides.clear(); e.dispose()

def payload(ids, **extra): return {'name':'Multi','spools':[{'spool_id':i,'estimated_weight_g':10} for i in ids],**extra}
def create(c,ids,**extra):
 r=c.post('/api/prints',json=payload(ids,**extra)); assert r.status_code==201,r.text; return r.json()

def test_create_read_limits_positions_and_totals(env):
 c,_,ids=env; one=create(c,ids[:1]); three=create(c,ids[:3]); ten=create(c,ids[:10])
 assert len(one['spools'])==1 and len(ten['spools'])==10
 assert [x['position'] for x in three['spools']]==[0,1,2] and Decimal(str(three['total_estimated_weight_g']))==30
 read=c.get(f"/api/prints/{three['id']}").json(); assert 'spool_id' not in read and len(read['spools'])==3
 assert c.post('/api/prints',json=payload([])).status_code==422
 assert c.post('/api/prints',json=payload([ids[0],ids[0]])).status_code==422
 assert c.post('/api/prints',json=payload([999999])).status_code==404

def test_incomplete_and_filter_and_patch(env):
 c,_,ids=env; a=create(c,ids[:2]); b=create(c,ids[1:3]);
 assert c.patch(f"/api/prints/{a['id']}",json={'spools':[{'spool_id':ids[0],'estimated_weight_g':80},{'spool_id':ids[1]}]}).json()['total_estimated_weight_g'] is None
 assert {x['id'] for x in c.get('/api/prints',params={'spool_id':ids[1]}).json()}=={a['id'],b['id']}
 changed=c.patch(f"/api/prints/{a['id']}",json={'spools':[{'spool_id':ids[1],'estimated_weight_g':20},{'spool_id':ids[0],'estimated_weight_g':30}]}).json()
 assert [x['spool_id'] for x in changed['spools']]==[ids[1],ids[0]]
 assert c.patch(f"/api/prints/{a['id']}",json={'spools':[]}).status_code==422

def test_start_locks_conflict_and_atomic_failure(env):
 c,F,ids=env; first=create(c,ids[:3]); assert c.post(f"/api/prints/{first['id']}/start").status_code==200
 with F() as s: assert len(s.scalars(select(PrintSpoolLock).where(PrintSpoolLock.print_job_id==first['id'])).all())==3; assert all(s.get(Spool,i).status is SpoolStatus.IN_USE for i in ids[:3])
 second=create(c,ids[2:4]); assert c.post(f"/api/prints/{second['id']}/start").status_code==409
 with F() as s: assert s.get(Spool,ids[3]).status is not SpoolStatus.IN_USE

def test_finish_multi_partial_zero_history_cost_and_rollback(env):
 c,F,ids=env; job=create(c,ids[:3]); c.post(f"/api/prints/{job['id']}/start")
 r=c.post(f"/api/prints/{job['id']}/finish",json={'consumptions':[{'spool_id':ids[0],'actual_weight_g':100},{'spool_id':ids[1],'actual_weight_g':40},{'spool_id':ids[2],'actual_weight_g':0}]}); assert r.status_code==200,r.text; body=r.json(); assert Decimal(str(body['total_actual_weight_g']))==140
 with F() as s:
  assert [s.get(Spool,i).current_filament_weight_g for i in ids[:3]]==[Decimal('400'),Decimal('460'),Decimal('500')]
  assert [s.get(Spool,i).status for i in ids[:3]]==[SpoolStatus.OPEN,SpoolStatus.OPEN,SpoolStatus.OPEN]
  assert s.get(PrintJob,job['id']).status is PrintJobStatus.SUCCESS
  assert len(s.scalars(select(WeightHistory).where(WeightHistory.source=='PRINT')).all())==2
  assert not s.scalars(select(PrintSpoolLock)).all(); links={x.spool_id:x for x in s.scalars(select(PrintJobSpool).where(PrintJobSpool.print_job_id==job['id'])).all()}; assert links[ids[2]].actual_weight_g==0
 bad=create(c,ids[3:5]); c.post(f"/api/prints/{bad['id']}/start");
 with F() as s: s.get(Spool,ids[4]).current_filament_weight_g=Decimal('20'); s.commit()
 assert c.post(f"/api/prints/{bad['id']}/finish",json={'consumptions':[{'spool_id':ids[3],'actual_weight_g':10},{'spool_id':ids[4],'actual_weight_g':40}]}).status_code==409
 with F() as s:
  assert s.get(PrintJob,bad['id']).status is PrintJobStatus.PRINTING
  assert s.get(Spool,ids[3]).current_filament_weight_g==500 and s.get(Spool,ids[4]).current_filament_weight_g==20
  assert s.get(Spool,ids[3]).status is SpoolStatus.IN_USE and s.get(Spool,ids[4]).status is SpoolStatus.IN_USE
  assert len(s.scalars(select(PrintSpoolLock).where(PrintSpoolLock.print_job_id==bad['id'])).all())==2
  assert len(s.scalars(select(WeightHistory).where(WeightHistory.source=='PRINT')).all())==2
  assert all(link.actual_weight_g is None and link.material_cost is None for link in s.scalars(select(PrintJobSpool).where(PrintJobSpool.print_job_id==bad['id'])).all())

def test_finish_recalculates_each_status_and_releases_zero_and_omitted_spools(env):
 c,F,ids=env
 selected=ids[:5]
 with F() as s:
  for spool_id,current in zip(selected,[500,250,100,500,500],strict=True):
   spool=s.get(Spool,spool_id); spool.current_filament_weight_g=Decimal(current); spool.status=SpoolStatus.OPEN
  s.get(Spool,selected[4]).needs_drying=True; s.get(Spool,selected[4]).status=SpoolStatus.NEEDS_DRYING
  s.commit()
 job=create(c,selected); assert c.post(f"/api/prints/{job['id']}/start").status_code==200
 response=c.post(f"/api/prints/{job['id']}/finish",json={'consumptions':[{'spool_id':selected[0],'actual_weight_g':50},{'spool_id':selected[1],'actual_weight_g':75},{'spool_id':selected[2],'actual_weight_g':100},{'spool_id':selected[3],'actual_weight_g':0}]})
 assert response.status_code==200,response.text
 with F() as s:
  assert [s.get(Spool,i).current_filament_weight_g for i in selected]==[Decimal('450'),Decimal('175'),Decimal('0'),Decimal('500'),Decimal('500')]
  assert [s.get(Spool,i).status for i in selected]==[SpoolStatus.OPEN,SpoolStatus.LOW,SpoolStatus.EMPTY,SpoolStatus.OPEN,SpoolStatus.NEEDS_DRYING]
  assert not s.scalars(select(PrintSpoolLock).where(PrintSpoolLock.print_job_id==job['id'])).all()
  links={link.spool_id:link for link in s.scalars(select(PrintJobSpool).where(PrintJobSpool.print_job_id==job['id'])).all()}
  assert links[selected[3]].actual_weight_g==0
  assert links[selected[4]].actual_weight_g is None

def test_finished_spool_can_be_reused_and_started_by_a_second_job(env):
 c,F,ids=env; spool_id=ids[0]
 with F() as s: spool_code=s.get(Spool,spool_id).code
 first=create(c,[spool_id]); assert c.post(f"/api/prints/{first['id']}/start").status_code==200
 assert c.post(f"/api/prints/{first['id']}/finish",json={'consumptions':[{'spool_id':spool_id,'actual_weight_g':10}]}).status_code==200
 assert c.get(f'/api/spools/{spool_code}').json()['status']=='OPEN'
 assert next(item for item in c.get('/api/spools').json() if item['id']==spool_id)['status']=='OPEN'
 second=create(c,[spool_id]); started=c.post(f"/api/prints/{second['id']}/start")
 assert started.status_code==200,started.text
 with F() as s:
  lock=s.get(PrintSpoolLock,spool_id)
  assert lock is not None and lock.print_job_id==second['id']
  assert s.get(Spool,spool_id).status is SpoolStatus.IN_USE
