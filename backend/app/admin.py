"""Explicit operator-only initial administrator provisioning."""
import argparse
from sqlalchemy import select
from .database import SessionLocal,User,Audit
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==args.email.lower().strip()))
        if not user:parser.error('Register this email through the application first')
        user.role='admin';db.add(Audit(owner_id=user.id,action='operator:provision_admin',target=user.id));db.commit()
        print('Administrator role provisioned. Sign in again to refresh the interface.')
if __name__=='__main__':main()
