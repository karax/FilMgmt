from pathlib import Path
from decimal import Decimal
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/'alembic.ini'; PREVIOUS='e4f9a3b2c817'; HEAD='d7a1e6b4c902'
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
 print_job_columns={column['name'] for column in ins.get_columns('print_jobs')}
 assert {'printer_serial','task_id','capture_mode','ams_snapshot','reconciliation_status'} <= print_job_columns
 assert {'enrichment_status','source_file_name','thumbnail_file_name','slicer_estimated_duration_seconds'} <= print_job_columns
 assert 'print_job_filament_usages' in ins.get_table_names()
 assert 'print_job_filament_reconciliations' in ins.get_table_names()
 assert {'spool_calibrations','tare_profiles','tare_measurements'} <= set(ins.get_table_names())
 assert 'uq_print_jobs_one_active_bambu_printer' in {index['name'] for index in ins.get_indexes('print_jobs')}
 assert 'ix_print_jobs_started_at' in {index['name'] for index in ins.get_indexes('print_jobs')}
 assert 'ix_spools_purchase_date' in {index['name'] for index in ins.get_indexes('spools')}
 assert 'ix_reconciliation_active_consumption_job_spool' in {index['name'] for index in ins.get_indexes('print_job_filament_reconciliations')}
 command.check(cfg)
 e.dispose()

def test_bambu_history_upgrade_preserves_existing_prints_and_roundtrips_when_empty(tmp_path,monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'bambu-history.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,'f2a8c7d190b4'); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO print_jobs(id,name,status,created_at,updated_at) VALUES(1,'existing','SUCCESS',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 command.upgrade(cfg,HEAD)
 with e.connect() as c:
  row=c.execute(text('SELECT name,status,printer_serial,capture_mode,ams_snapshot FROM print_jobs WHERE id=1')).one()
  assert row==('existing','SUCCESS',None,None,None)
 command.downgrade(cfg,'f2a8c7d190b4')
 with e.connect() as c: assert c.execute(text('SELECT name,status FROM print_jobs WHERE id=1')).one()==('existing','SUCCESS')
 e.dispose()

def test_bambu_history_downgrade_refuses_to_discard_captured_jobs(tmp_path,monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'bambu-history-protected.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,HEAD); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO print_jobs(name,status,printer_serial,capture_mode,created_at,updated_at) VALUES('captured','COMPLETED','SERIAL','LIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 with pytest.raises(RuntimeError,match='discard their history'): command.downgrade(cfg,'f2a8c7d190b4')
 with e.connect() as c: assert c.scalar(text("SELECT count(*) FROM print_jobs WHERE capture_mode='LIVE'"))==1
 e.dispose()

def test_wave3_upgrade_from_wave2_preserves_existing_jobs_and_inventory(tmp_path,monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'wave3.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,'6c4f2a9d8e10'); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'PLA','PLA',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(1,'FIL-W3',1,1,'Black',1.75,1000,777,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_jobs(id,name,status,printer_serial,capture_mode,created_at,updated_at) VALUES(1,'captured','COMPLETED','SERIAL','LIVE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'manual','SUCCESS',NULL,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 command.upgrade(cfg,HEAD)
 with e.connect() as c:
  assert c.execute(text("SELECT name,enrichment_status,enrichment_attempts FROM print_jobs ORDER BY id")).all()==[('captured','PENDING',0),('manual',None,0)]
  assert c.scalar(text("SELECT current_filament_weight_g FROM spools WHERE id=1"))==777
  assert c.scalar(text("SELECT count(*) FROM print_job_filament_usages"))==0
 command.downgrade(cfg,'6c4f2a9d8e10')
 with e.connect() as c:
  assert c.scalar(text("SELECT count(*) FROM print_jobs"))==2
  assert c.scalar(text("SELECT current_filament_weight_g FROM spools WHERE id=1"))==777
 e.dispose()

def test_wave3_downgrade_refuses_to_discard_enriched_usage(tmp_path,monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'wave3-protected.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,HEAD); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO print_jobs(id,name,status,printer_serial,capture_mode,enrichment_status,enriched_at,created_at,updated_at) VALUES(1,'captured','COMPLETED','SERIAL','LIVE','ENRICHED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_job_filament_usages(print_job_id,position,used_g,created_at,updated_at) VALUES(1,0,10,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 with pytest.raises(RuntimeError,match='discard it'): command.downgrade(cfg,'6c4f2a9d8e10')
 with e.connect() as c: assert c.scalar(text("SELECT count(*) FROM print_job_filament_usages"))==1
 e.dispose()


def test_wave4_upgrade_enqueues_existing_terminal_usage_without_changing_inventory(tmp_path, monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'wave4.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,'91b7c3d4e5f6'); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'PETG','PETG',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(1,'FIL-W4',1,1,'White',1.75,1000,684,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_jobs(id,name,status,capture_mode,enrichment_status,reconciliation_status,created_at,updated_at) VALUES(1,'complete','COMPLETED','LIVE','ENRICHED',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'cancelled','CANCELLED','LIVE','ENRICHED','PENDING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_job_filament_usages(id,print_job_id,position,material_type,used_g,created_at,updated_at) VALUES(1,1,0,'PETG',230.510,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,2,0,'PETG',230.510,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
 command.upgrade(cfg,HEAD)
 with e.connect() as c:
  assert c.execute(text("SELECT id,reconciliation_status FROM print_jobs ORDER BY id")).all()==[(1,'PENDING'),(2,'NEEDS_REVIEW')]
  assert c.scalar(text("SELECT current_filament_weight_g FROM spools WHERE id=1"))==684
  assert c.scalar(text("SELECT count(*) FROM print_job_filament_reconciliations"))==0
 e.dispose()


def test_wave4_downgrade_refuses_to_discard_reconciliation_audit(tmp_path, monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'wave4-protected.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,HEAD); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'PLA','PLA',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(1,'FIL-AUDIT',1,1,'Black',1.75,1000,900,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_jobs(id,name,status,capture_mode,enrichment_status,reconciliation_status,created_at,updated_at) VALUES(1,'audited','COMPLETED','LIVE','ENRICHED','RECONCILED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_job_filament_usages(id,print_job_id,position,material_type,used_g,created_at,updated_at) VALUES(1,1,0,'PLA',100,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO print_job_filament_reconciliations(print_job_id,filament_usage_id,spool_id,event_type,amount_g,sliced_estimated_g,remaining_before_g,remaining_after_g,manual_override,created_at) VALUES(1,1,1,'CONSUMPTION',100,100,1000,900,0,CURRENT_TIMESTAMP)"))
 with pytest.raises(RuntimeError,match='audit trail'): command.downgrade(cfg,'91b7c3d4e5f6')
 with e.connect() as c:
  assert c.scalar(text("SELECT count(*) FROM print_job_filament_reconciliations"))==1
  assert c.scalar(text("SELECT current_filament_weight_g FROM spools WHERE id=1"))==900
 e.dispose()


def test_wave5_upgrade_preserves_every_existing_spool_balance(tmp_path, monkeypatch):
 url=f"sqlite+pysqlite:///{tmp_path/'wave5.db'}"; monkeypatch.setenv('DATABASE_URL',url); cfg=Config(str(CONFIG)); command.upgrade(cfg,'a4e8c1f2b7d9'); e=create_engine(url)
 with e.begin() as c:
  c.execute(text("INSERT INTO manufacturers(id,name,created_at,updated_at) VALUES(1,'M',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO materials(id,name,category,created_at,updated_at) VALUES(1,'PETG','PETG',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  c.execute(text("INSERT INTO spools(id,code,manufacturer_id,material_id,color_name,diameter_mm,initial_filament_weight_g,current_filament_weight_g,currency,status,needs_drying,created_at,updated_at) VALUES(1,'FIL-0020',1,1,'White',1.75,1000,769.490,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),(2,'FIL-0021',1,1,'Black',1.75,1000,413.125,'EUR','OPEN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
  before=c.execute(text("SELECT id,current_filament_weight_g FROM spools ORDER BY id")).all()
 command.upgrade(cfg,HEAD)
 with e.connect() as c:
  assert c.execute(text("SELECT id,current_filament_weight_g FROM spools ORDER BY id")).all()==before
  assert c.scalar(text("SELECT count(*) FROM spool_calibrations"))==0
  assert c.scalar(text("SELECT count(*) FROM tare_profiles"))==0
  assert c.scalar(text("SELECT count(*) FROM tare_measurements"))==0
  assert c.scalar(text("PRAGMA integrity_check"))=='ok'
  assert c.execute(text("PRAGMA foreign_key_check")).all()==[]
 e.dispose()
