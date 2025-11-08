"""
Seed script to create test data
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import (
    Account, User, Partner, Call, CallMetricsHourly,
    Transcript, Summary
)
from app.models.account import AccountType
from app.models.user import UserRole
from app.models.partner import PartnerKind
from app.models.call import CallDisposition
from app.models.summary import Sentiment

# Create engine
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed_data():
    """Seed the database with test data"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Create accounts
            admin_account = Account(
                id=uuid.uuid4(),
                name="Admin Account",
                slug="admin",
                type=AccountType.ADMIN,
            )
            publisher_account = Account(
                id=uuid.uuid4(),
                name="Publisher Co",
                slug="publisher-co",
                type=AccountType.PUBLISHER,
            )
            agency_account = Account(
                id=uuid.uuid4(),
                name="Agency Inc",
                slug="agency-inc",
                type=AccountType.AGENCY,
            )
            broker_account = Account(
                id=uuid.uuid4(),
                name="Broker LLC",
                slug="broker-llc",
                type=AccountType.BROKER,
            )
            
            session.add_all([admin_account, publisher_account, agency_account, broker_account])
            await session.flush()
            
            # Create users
            admin_user = User(
                id=uuid.uuid4(),
                account_id=admin_account.id,
                email="admin@hopwhistle.com",
                password_hash=get_password_hash("admin123"),
                role=UserRole.ADMIN,
            )
            publisher_user = User(
                id=uuid.uuid4(),
                account_id=publisher_account.id,
                email="manager@publisher.com",
                password_hash=get_password_hash("password123"),
                role=UserRole.MANAGER,
            )
            agency_user = User(
                id=uuid.uuid4(),
                account_id=agency_account.id,
                email="analyst@agency.com",
                password_hash=get_password_hash("password123"),
                role=UserRole.ANALYST,
            )
            
            session.add_all([admin_user, publisher_user, agency_user])
            await session.flush()
            
            # Create partners
            partners = []
            for account in [publisher_account, agency_account, broker_account]:
                for i in range(3):
                    partner = Partner(
                        id=uuid.uuid4(),
                        account_id=account.id,
                        kind=PartnerKind.PUBLISHER if account.type == AccountType.PUBLISHER
                        else PartnerKind.AGENCY if account.type == AccountType.AGENCY
                        else PartnerKind.BROKER,
                        name=f"{account.name} Partner {i+1}",
                    )
                    partners.append(partner)
                    session.add(partner)
            
            await session.flush()
            
            # Create 500 synthetic calls over past 30 days
            dispositions = list(CallDisposition)
            sentiments = [Sentiment.POSITIVE, Sentiment.NEUTRAL, Sentiment.NEGATIVE]
            
            base_time = datetime.utcnow() - timedelta(days=30)
            
            for i in range(500):
                # Random time in last 30 days
                call_start = base_time + timedelta(
                    seconds=random.randint(0, 30 * 24 * 60 * 60)
                )
                duration = random.randint(30, 600)  # 30 seconds to 10 minutes
                call_end = call_start + timedelta(seconds=duration)
                
                # Random account and partner
                account = random.choice([publisher_account, agency_account, broker_account])
                account_partners = [p for p in partners if p.account_id == account.id]
                partner = random.choice(account_partners) if account_partners else None
                
                disposition = random.choice(dispositions)
                billable = random.choice([True, False]) if disposition == CallDisposition.CONNECTED else False
                sale_made = billable and random.random() < 0.3  # 30% of billable calls result in sales
                sale_amount_cents = random.randint(5000, 15000) if sale_made else None
                
                call = Call(
                    id=uuid.uuid4(),
                    account_id=account.id,
                    partner_id=partner.id if partner else None,
                    external_call_id=f"EXT-{random.randint(100000, 999999)}",
                    started_at=call_start,
                    ended_at=call_end,
                    duration_sec=duration,
                    disposition=disposition,
                    billable=billable,
                    sale_made=sale_made,
                    sale_amount_cents=sale_amount_cents,
                    ani=f"+1{random.randint(2000000000, 9999999999)}",
                    dnis=f"+1{random.randint(2000000000, 9999999999)}",
                    agent_name=random.choice(["Jordan", "Alex", "Sam", "Taylor", "Casey", "Morgan"]),
                )
                session.add(call)
                await session.flush()
                
                # Create transcript for ~80% of calls
                if random.random() < 0.8:
                    transcript_text = f"Call transcript {i+1}. This is a sample transcript for testing purposes. "
                    transcript_text += "The agent discussed insurance options with the customer. "
                    transcript_text += "Customer asked about coverage details and pricing."
                    
                    transcript = Transcript(
                        id=uuid.uuid4(),
                        call_id=call.id,
                        language="en",
                        text=transcript_text,
                        words_json=None,
                    )
                    session.add(transcript)
                
                # Create summary for ~70% of calls
                if random.random() < 0.7:
                    sentiment = random.choice(sentiments)
                    summary = Summary(
                        id=uuid.uuid4(),
                        call_id=call.id,
                        summary=f"Call summary {i+1}: Customer inquiry about insurance coverage.",
                        key_points=[
                            "Discussed coverage options",
                            "Reviewed pricing",
                            "Customer showed interest" if sale_made else "Customer requested more information",
                        ],
                        sentiment=sentiment,
                    )
                    session.add(summary)
                
                # Update metrics hourly buckets
                bucket_start = call_start.replace(minute=0, second=0, microsecond=0)
                
                result = await session.execute(
                    select(CallMetricsHourly).where(
                        CallMetricsHourly.bucket_start == bucket_start,
                        CallMetricsHourly.account_id == account.id,
                        CallMetricsHourly.partner_id == partner.id if partner else None,
                    )
                )
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    metrics.total_calls += 1
                    if billable:
                        metrics.billable_calls += 1
                    if sale_made:
                        metrics.sales += 1
                    if disposition == CallDisposition.CONNECTED:
                        metrics.connected += 1
                        metrics.answers += 1
                else:
                    metrics = CallMetricsHourly(
                        bucket_start=bucket_start,
                        account_id=account.id,
                        partner_id=partner.id if partner else None,
                        total_calls=1,
                        billable_calls=1 if billable else 0,
                        sales=1 if sale_made else 0,
                        connected=1 if disposition == CallDisposition.CONNECTED else 0,
                        answers=1 if disposition == CallDisposition.CONNECTED else 0,
                        unique_callers=1,
                    )
                    session.add(metrics)
                
                if (i + 1) % 50 == 0:
                    print(f"Created {i + 1} calls...")
                    await session.commit()
                    async with session.begin():
                        pass
            
            await session.commit()
            print("✅ Seed data created successfully!")
            print(f"   - 4 accounts (admin, publisher, agency, broker)")
            print(f"   - 3 users")
            print(f"   - 9 partners")
            print(f"   - 500 calls")
            print(f"   - Transcripts and summaries")
            print("\nLogin credentials:")
            print("  admin@hopwhistle.com / admin123")
            print("  manager@publisher.com / password123")
            print("  analyst@agency.com / password123")


if __name__ == "__main__":
    asyncio.run(seed_data())

