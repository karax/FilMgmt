"""atomic multi-spool print jobs

Revision ID: b33a1c9d2e71
Revises: e4f9a3b2c817
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision = 'b33a1c9d2e71'
down_revision = 'e4f9a3b2c817'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('print_job_spools', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('print_job_id', sa.Integer(), sa.ForeignKey('print_jobs.id', ondelete='RESTRICT'), nullable=False), sa.Column('spool_id', sa.Integer(), sa.ForeignKey('spools.id', ondelete='RESTRICT'), nullable=False), sa.Column('position', sa.Integer(), nullable=False), sa.Column('estimated_weight_g', sa.Numeric(10,3)), sa.Column('actual_weight_g', sa.Numeric(10,3)), sa.Column('filament_cost_per_g', sa.Numeric(12,6)), sa.Column('material_cost', sa.Numeric(12,4)), sa.Column('material_cost_currency', sa.String(3)), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint('print_job_id','spool_id',name='uq_print_job_spools_print_job_spool'), sa.CheckConstraint('position >= 0',name='ck_print_job_spools_position_non_negative'), sa.CheckConstraint('estimated_weight_g IS NULL OR estimated_weight_g > 0',name='ck_print_job_spools_estimated_weight_positive'), sa.CheckConstraint('actual_weight_g IS NULL OR actual_weight_g >= 0',name='ck_print_job_spools_actual_weight_non_negative'))
    op.create_index('ix_print_job_spools_print_job_id','print_job_spools',['print_job_id'])
    op.create_index('ix_print_job_spools_spool_id','print_job_spools',['spool_id'])
    op.create_table('print_spool_locks', sa.Column('spool_id',sa.Integer(),sa.ForeignKey('spools.id',ondelete='RESTRICT'),primary_key=True), sa.Column('print_job_id',sa.Integer(),sa.ForeignKey('print_jobs.id',ondelete='RESTRICT'),nullable=False), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_print_spool_locks_print_job_id','print_spool_locks',['print_job_id'])
    conn=op.get_bind()
    legacy=conn.execute(sa.text('SELECT id, spool_id, estimated_weight_g, actual_weight_g, filament_cost_per_g, material_cost, material_cost_currency, status FROM print_jobs WHERE spool_id IS NOT NULL')).mappings().all()
    for row in legacy:
        conn.execute(sa.text('INSERT INTO print_job_spools (print_job_id,spool_id,position,estimated_weight_g,actual_weight_g,filament_cost_per_g,material_cost,material_cost_currency,created_at,updated_at) VALUES (:id,:spool_id,0,:estimated_weight_g,:actual_weight_g,:filament_cost_per_g,:material_cost,:material_cost_currency,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)'),row)
        if row['status']=='PRINTING': conn.execute(sa.text('INSERT INTO print_spool_locks (spool_id,print_job_id,created_at) VALUES (:spool_id,:id,CURRENT_TIMESTAMP)'),row)
    expected=len(legacy); actual=conn.scalar(sa.text('SELECT count(*) FROM print_job_spools'))
    if actual != expected: raise RuntimeError(f'Multi-spool backfill failed: expected {expected}, got {actual}')
    with op.batch_alter_table('print_jobs') as batch:
        batch.drop_index('uq_print_jobs_one_printing_per_spool')
        batch.drop_index('ix_print_jobs_spool_id')
        batch.drop_constraint('ck_print_jobs_estimated_weight_positive', type_='check')
        batch.drop_constraint('ck_print_jobs_actual_weight_non_negative', type_='check')
        batch.drop_column('spool_id'); batch.drop_column('estimated_weight_g'); batch.drop_column('actual_weight_g'); batch.drop_column('filament_cost_per_g'); batch.drop_column('material_cost'); batch.drop_column('material_cost_currency')

def downgrade() -> None:
    conn=op.get_bind(); multi=conn.scalar(sa.text('SELECT count(*) FROM (SELECT print_job_id FROM print_job_spools GROUP BY print_job_id HAVING count(*) > 1)'))
    if multi: raise RuntimeError('Cannot downgrade multi-spool migration: one or more PrintJobs have multiple spools; downgrade would be destructive.')
    with op.batch_alter_table('print_jobs') as batch:
        batch.add_column(sa.Column('spool_id',sa.Integer(),nullable=True)); batch.add_column(sa.Column('estimated_weight_g',sa.Numeric(10,3))); batch.add_column(sa.Column('actual_weight_g',sa.Numeric(10,3))); batch.add_column(sa.Column('filament_cost_per_g',sa.Numeric(12,6))); batch.add_column(sa.Column('material_cost',sa.Numeric(12,4))); batch.add_column(sa.Column('material_cost_currency',sa.String(3)))
        batch.create_check_constraint('ck_print_jobs_estimated_weight_positive','estimated_weight_g IS NULL OR estimated_weight_g > 0')
        batch.create_check_constraint('ck_print_jobs_actual_weight_non_negative','actual_weight_g IS NULL OR actual_weight_g >= 0')
    conn.execute(sa.text('UPDATE print_jobs SET spool_id=(SELECT spool_id FROM print_job_spools p WHERE p.print_job_id=print_jobs.id), estimated_weight_g=(SELECT estimated_weight_g FROM print_job_spools p WHERE p.print_job_id=print_jobs.id), actual_weight_g=(SELECT actual_weight_g FROM print_job_spools p WHERE p.print_job_id=print_jobs.id), filament_cost_per_g=(SELECT filament_cost_per_g FROM print_job_spools p WHERE p.print_job_id=print_jobs.id), material_cost=(SELECT material_cost FROM print_job_spools p WHERE p.print_job_id=print_jobs.id), material_cost_currency=(SELECT material_cost_currency FROM print_job_spools p WHERE p.print_job_id=print_jobs.id)'))
    if conn.scalar(sa.text('SELECT count(*) FROM print_jobs WHERE spool_id IS NULL')): raise RuntimeError('Cannot downgrade: PrintJobs without spool links cannot satisfy legacy schema.')
    with op.batch_alter_table('print_jobs') as batch:
        batch.alter_column('spool_id',nullable=False); batch.create_index('ix_print_jobs_spool_id',['spool_id']); batch.create_index('uq_print_jobs_one_printing_per_spool',['spool_id'],unique=True,sqlite_where=sa.text("status = 'PRINTING'"))
    op.drop_index('ix_print_spool_locks_print_job_id',table_name='print_spool_locks'); op.drop_table('print_spool_locks')
    op.drop_index('ix_print_job_spools_spool_id',table_name='print_job_spools'); op.drop_index('ix_print_job_spools_print_job_id',table_name='print_job_spools'); op.drop_table('print_job_spools')
