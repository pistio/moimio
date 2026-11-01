"""Private stdin/stdout bootstrap channel for the trusted provisioner only.

Never pass its input/output through command arguments or ordinary logs. This
module is not an HTTP issuer, and normal startup does not invoke it.
"""
import asyncio
import hashlib
import json
import sys
from app.core.database import async_session_factory, engine
from app.services.hosted_access import issue_bootstrap

CONTRACT = 'moimio-core-bootstrap/v1'
FIELDS = {'contract','tenant_id','buyer_email','checkout_id','transaction_commitment','public_origin'}


async def issue(value):
    if not isinstance(value, dict) or set(value) != FIELDS or value['contract'] != CONTRACT:
        raise ValueError('PRIVATE_BOOTSTRAP_CONTRACT_REFUSED')
    engine.sync_engine.hide_parameters = True
    async with async_session_factory() as db:
        token = await issue_bootstrap(db, **{k:v for k,v in value.items() if k != 'contract'})
        await db.commit()
    return {'contract':CONTRACT,'tenant_id':value['tenant_id'],'checkout_id':value['checkout_id'],
            'bootstrap_token':token,'grant_digest':hashlib.sha256(token.encode()).hexdigest()}


def main():
    try:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError('PRIVATE_BOOTSTRAP_BOUND_REFUSED')
        result = asyncio.run(issue(json.loads(raw)))
    except Exception:
        # No SQL parameters, buyer identities, token or documentary input in errors.
        sys.stderr.write('PRIVATE_BOOTSTRAP_REVIEW_REQUIRED\n')
        return 1
    sys.stdout.write(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
