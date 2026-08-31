from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Manufacturer, Material, PrintJob, PrintJobSpool, PrintJobStatus, Spool

@pytest.fixture
def db_session():
    engine=create_database_engine('sqlite+pysqlite:///:memory:'); Base.metadata.create_all(engine); factory=create_session_factory(engine)
    with factory() as session: yield session
    engine.dispose()

@pytest.fixture
def spools(db_session: Session):
    m=Manufacturer(name='eSUN'); material=Material(name='PLA',category='PLA'); db_session.add_all([m,material]); db_session.flush()
    result=[Spool(code=f'FIL-{n}',manufacturer_id=m.id,material_id=material.id,color_name='black',initial_filament_weight_g=1000,current_filament_weight_g=1000) for n in range(3)]
    db_session.add_all(result); db_session.commit(); return result

def make_job(*spools: Spool):
    job=PrintJob(name='Multi'); job.spool_links=[PrintJobSpool(spool_id=s.id,position=i,estimated_weight_g=Decimal('10')*(i+1)) for i,s in enumerate(spools)]; return job

def test_print_job_owns_ordered_spool_links(db_session: Session, spools):
    job=make_job(*spools); db_session.add(job); db_session.commit()
    assert [link.spool_id for link in job.spool_links] == [s.id for s in spools]
    assert [link.position for link in job.spool_links] == [0,1,2]
    assert job.total_estimated_weight_g == Decimal('60')

def test_incomplete_estimate_has_no_misleading_total(db_session: Session, spools):
    job=make_job(*spools[:2]); job.spool_links[1].estimated_weight_g=None; db_session.add(job); db_session.commit()
    assert job.total_estimated_weight_g is None

def test_duplicate_spool_link_is_rejected(db_session: Session, spools):
    job=make_job(spools[0]); db_session.add(job); db_session.flush(); db_session.add(PrintJobSpool(print_job_id=job.id,spool_id=spools[0].id,position=1))
    with pytest.raises(IntegrityError): db_session.commit()

def test_jobs_keep_lifecycle_without_single_spool_field(db_session: Session, spools):
    job=make_job(spools[0]); job.status=PrintJobStatus.PRINTING; db_session.add(job); db_session.commit()
    assert not hasattr(job,'spool_id')
