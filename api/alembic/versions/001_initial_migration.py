"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-11-08 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable TimescaleDB extension if available (will fail silently if not)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    
    # Enable pg_trgm for full-text search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('type', sa.Enum('publisher', 'agency', 'broker', 'admin', name='accounttype'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_accounts_slug'), 'accounts', ['slug'], unique=True)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'manager', 'analyst', 'viewer', name='userrole'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_account_id'), 'users', ['account_id'], unique=False)
    op.create_index('ix_users_account_email', 'users', ['account_id', 'email'], unique=False)
    
    # Create partners table
    op.create_table(
        'partners',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.Enum('publisher', 'agency', 'broker', name='partnerkind'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_partners_account_id'), 'partners', ['account_id'], unique=False)
    op.create_index('ix_partners_account_kind', 'partners', ['account_id', 'kind'], unique=False)
    
    # Create calls table
    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('external_call_id', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_sec', sa.Integer(), nullable=True),
        sa.Column('disposition', sa.Enum('connected', 'no_answer', 'busy', 'failed', 'rejected', name='calldisposition'), nullable=False),
        sa.Column('billable', sa.Boolean(), nullable=False),
        sa.Column('sale_made', sa.Boolean(), nullable=False),
        sa.Column('sale_amount_cents', sa.Integer(), nullable=True),
        sa.Column('ani', sa.String(length=50), nullable=True),
        sa.Column('dnis', sa.String(length=50), nullable=True),
        sa.Column('agent_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calls_account_id'), 'calls', ['account_id'], unique=False)
    op.create_index(op.f('ix_calls_partner_id'), 'calls', ['partner_id'], unique=False)
    op.create_index(op.f('ix_calls_external_call_id'), 'calls', ['external_call_id'], unique=False)
    op.create_index(op.f('ix_calls_billable'), 'calls', ['billable'], unique=False)
    op.create_index(op.f('ix_calls_sale_made'), 'calls', ['sale_made'], unique=False)
    op.create_index('ix_calls_account_started', 'calls', ['account_id', 'started_at'], unique=False)
    op.create_index('ix_calls_partner_started', 'calls', ['partner_id', 'started_at'], unique=False)
    
    # Create call_metrics_hourly table
    op.create_table(
        'call_metrics_hourly',
        sa.Column('bucket_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('total_calls', sa.Integer(), nullable=False),
        sa.Column('billable_calls', sa.Integer(), nullable=False),
        sa.Column('sales', sa.Integer(), nullable=False),
        sa.Column('answers', sa.Integer(), nullable=False),
        sa.Column('connected', sa.Integer(), nullable=False),
        sa.Column('unique_callers', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ),
        sa.PrimaryKeyConstraint('bucket_start', 'account_id', 'partner_id')
    )
    
    # Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('words_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('call_id')
    )
    op.create_index(op.f('ix_transcripts_call_id'), 'transcripts', ['call_id'], unique=True)
    # Full-text search index using GIN
    op.execute("CREATE INDEX idx_transcript_fts ON transcripts USING gin(to_tsvector('english', text));")
    
    # Create summaries table
    op.create_table(
        'summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('key_points', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sentiment', sa.Enum('pos', 'neu', 'neg', name='sentiment'), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('call_id')
    )
    op.create_index(op.f('ix_summaries_call_id'), 'summaries', ['call_id'], unique=True)
    
    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.Enum('received', 'processed', 'error', name='webhookstatus'), nullable=False),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Convert calls table to TimescaleDB hypertable if TimescaleDB is available
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('calls', 'started_at', if_not_exists => TRUE);
                PERFORM create_hypertable('call_metrics_hourly', 'bucket_start', if_not_exists => TRUE);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('webhook_events')
    op.drop_table('summaries')
    op.drop_table('transcripts')
    op.drop_table('call_metrics_hourly')
    op.drop_table('calls')
    op.drop_table('partners')
    op.drop_table('users')
    op.drop_table('accounts')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS webhookstatus;")
    op.execute("DROP TYPE IF EXISTS sentiment;")
    op.execute("DROP TYPE IF EXISTS calldisposition;")
    op.execute("DROP TYPE IF EXISTS partnerkind;")
    op.execute("DROP TYPE IF EXISTS userrole;")
    op.execute("DROP TYPE IF EXISTS accounttype;")

