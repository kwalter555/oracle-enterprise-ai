"""Container metadata-only database preflight. Does not call a model."""
import argparse
import json
import sqlite3
from database import Oracle
from service import load_config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--database', action='store_true')
    group.add_argument('--audit', action='store_true', help='Last 20 local events; no SQL, questions or results printed.')
    args=parser.parse_args()
    try:
        if args.audit:
            db=sqlite3.connect('file:/state/approvals.sqlite?mode=ro',uri=True)
            try:
                rows=db.execute('SELECT at,proposal_id,event FROM audit ORDER BY sequence DESC LIMIT 20').fetchall()
                print(json.dumps(rows))
            finally: db.close()
            raise SystemExit(0)
        config = load_config('/run/secrets/sql-review.json')
        result = Oracle(config).preflight()
        print(json.dumps(result))
        print('No analytical queries, Select AI calls or database changes made.')
    except Exception as error:
        # No connection strings, SQL, wallet contents or passwords in diagnostics.
        details = error.args[0] if error.args else None
        code = getattr(details, 'full_code', '')
        print('FAILED: ' + type(error).__name__ + (' / ' + code if code else ''))
        print('Stop here. Check account grants, wallet, passwords and network access locally.')
        raise SystemExit(1)
