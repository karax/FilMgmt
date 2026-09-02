from pathlib import Path
from decimal import Decimal
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/'alembic.ini'; PREVIOUS='e4f9a3b2c817'; HEAD='f2a8c7d190b4'
def setup(tmp_path,monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'migration.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,PREVIOUS); return cfg,create_engine(url)

def test_multi_spool_backfill_and_safe_roundtrip(tmp_path,monkeypatch):
 cfg,e=setup(tmp_path,monkeypatch)
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")); c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'PLA','PLA',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  for i in range(1,4): c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(:i,:code,1,1,'x',1.75,1000,500,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{'i':i,'code':f'FIL-{i}'})
  c.execute(text("INSERT INTO print_jobs(id,name,spool_id,status,estimated_weight_g,actual_weight_g,estimated_time_minutes,actual_time_minutes,filament_cost_per_g,material_cost,material_cost_currency,started_at,finished_at,created_at,updated_at) VALUES (1,'planned',1,'PLANNED',120,NULL,180,NULL,NULL,NULL,NULL,NULL,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'printing',2,'PRINTING',80,NULL,NULL,NULL,NULL,NULL,NULL,CURRENT_TIMESTAMP,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(3,'success',3,'SUCCESS',100,92.5,NULL,60,.02,1.85,'EUR',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 command.upgrade(cfg,'head'); ins=inspect(e); assert {'print_job_spools','print_spool_locks'} <= set(ins.get_table_names()); assert {'spool_id','estimated_weight_g','actual_weight_g','material_cost'}.isdisjoint({x['name'] for x in ins.get_columns('print_jobs')})
 with e.connect() as c:
  assert c.scalar(text('select count(*) from print_jobs'))==3 and c.scalar(text('select count(*) from print_job_spools'))==3 and c.scalar(text('select count(*) from print_spool_locks where spool_id=2 and print_job_id=2'))==1
  r=c.execute(text('select estimated_weight_g,actual_weight_g,filament_cost_per_g,material_cost,material_cost_currency from print_job_spools where print_job_id=3')).one(); assert tuple(map(str,r))==('100','92.5','0.02','1.85','EUR')
 command.downgrade(cfg,PREVIOUS)
 with e.connect() as c: assert c.scalar(text('select count(*) from print_jobs'))==3 and c.scalar(text('select spool_id from print_jobs where id=3'))==3
 command.upgrade(cfg,'head')
 with e.connect() as c: assert c.scalar(text('select count(*) from print_job_spools'))==3 and c.scalar(text('select count(*) from print_spool_locks where spool_id=2'))==1
 e.dispose()

def test_unsafe_downgrade_aborts_without_data_loss(tmp_path,monkeypatch):
 cfg,e=setup(tmp_path,monkeypatch); command.upgrade(cfg,'head')
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")); c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'P','P',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"));
  for i in (1,2): c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(:i,:c,1,1,'x',1.75,1000,500,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{'i':i,'c':f'F{i}'})
  c.execute(text("INSERT INTO print_jobs(id,name,status,created_at,updated_at) VALUES(1,'multi','PLANNED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")); c.execute(text("INSERT INTO print_job_spools(print_job_id,spool_id,position,created_at,updated_at) VALUES(1,1,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(1,2,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 with pytest.raises(RuntimeError,match='multiple spools'): command.downgrade(cfg,PREVIOUS)
 with e.connect() as c: assert c.scalar(text('select count(*) from print_job_spools where print_job_id=1'))==2
 e.dispose()

def test_fresh_head_has_store_name_without_storage_schema(tmp_path, monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'fresh.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG))
 command.upgrade(cfg,HEAD); e=create_engine(url); ins=inspect(e)
 assert 'locations' not in ins.get_table_names()
 spool_columns={column['name'] for column in ins.get_columns('spools')}
 assert 'store_name' in spool_columns
 assert 'location_id' not in spool_columns
 command.check(cfg)
 e.dispose()
