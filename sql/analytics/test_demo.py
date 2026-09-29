"""Offline fixture checks; does not connect to Oracle or change files.

SQLite checks adapted table constraints and independent reference calculations.
This does not validate Oracle PL/SQL compilation; 02 performs the live checks.
"""
from pathlib import Path
from datetime import date, timedelta
import json
import re
import sqlite3

source = Path(__file__).with_name('01-create-analytics-data.sql').read_text()
ddl = re.findall(r"EXECUTE IMMEDIATE q'~(CREATE TABLE .*?)~';", source, re.S)
assert len(ddl) == 5
assert not re.search(r'\b(DROP|TRUNCATE|DELETE|UPDATE|MERGE)\s', source, re.I)
assert 'INSERT INTO demo_projects' not in source.lower()
assert source.index('IF l_count <> 0') < source.index('CREATE TABLE')
db = sqlite3.connect(':memory:')
db.execute('PRAGMA foreign_keys=ON')
for statement in ddl:
    statement = re.sub(r'VARCHAR2\(\d+ CHAR\)', 'TEXT', statement)
    statement = re.sub(r'NUMBER\(\d+,\d+\)', 'REAL', statement)
    statement = re.sub(r'NUMBER\(\d+\)', 'INTEGER', statement)
    statement = re.sub(r'\bDATE\b', 'TEXT', statement)
    db.execute(statement)

as_of = date(2026, 9, 24)
for i, name in enumerate(['Development', 'Operations', 'Analytics', 'Customer support'], 1):
    db.execute('INSERT INTO demo_a_departments VALUES (?,?)', (i, name))
for e in range(1, 25):
    db.execute('INSERT INTO demo_a_employees VALUES (?,?,?,?)',
               (e, f'Demo employee {e:02}', (e-1) % 4+1,
                date(2024, (e-1) % 12+1, 8).isoformat()))

cost_id = 0
for p in range(1, 37):
    year, local = (2025, p) if p <= 18 else (2026, p-18)
    start = date(year, (local-1) % 9+1, 5+10*((local-1)//9))
    end = start+timedelta(days=150)
    actual = end.isoformat() if end <= as_of else None
    status = 'ZAVRSEN' if actual else ('PAUZIRAN' if p % 11 == 0 else 'U_TIJEKU')
    manager = (p-1) % 24+1
    budget = 8000 if p % 7 == 0 else 25000+500*p
    db.execute('INSERT INTO demo_a_projects VALUES (?,?,?,?,?,?,?,?,?,?,?)',
               (p, f'AN-{year}-{local:02}', f'Demo analytics project {p:02}',
                f'Demo customer {(p-1)%6+1:02}', (manager-1) % 4+1, manager,
                start.isoformat(), end.isoformat(), actual, status, budget))
    for k in range(6):
        cost_date = start+timedelta(days=25*k)
        if cost_date <= as_of:
            cost_id += 1
            db.execute('INSERT INTO demo_a_costs VALUES (?,?,?,?,?)',
                       (cost_id, p, cost_date.isoformat(),
                        ['RAD', 'CLOUD', 'LICENCE', 'VANJSKE_USLUGE'][k % 4],
                        500+97*p+137*k))

leave_id = 0
def leave(e, day, kind, status):
    global leave_id
    assert day.weekday() < 5
    assert status != 'ISKORISTEN' or day <= as_of
    leave_id += 1
    db.execute('INSERT INTO demo_a_leave_days VALUES (?,?,?,?,?,?)',
               (leave_id, e, day.isoformat(), kind, status, 1))

for year in (2025, 2026):
    base = date(year, 7, 7 if year == 2025 else 6)
    for e in range(1, 25):
        if e <= (20 if year == 2025 else 22):
            for d in range(5):
                leave(e, base+timedelta(days=7*((e-1) % 3)+d), 'GODISNJI', 'ISKORISTEN')
        leave(e, date(year, 6, 9 if year == 2025 else 8), 'GODISNJI', 'OTKAZAN')
        leave(e, date(year, 2, 3 if year == 2025 else 2), 'EDUKACIJA', 'ISKORISTEN')
for e in range(1, 25):
    for d in range(2):
        leave(e, date(2026, 10, 5+d), 'GODISNJI', 'ODOBREN')

assert not db.execute('PRAGMA foreign_key_check').fetchall()
assert db.execute('SELECT COUNT(*) FROM demo_a_leave_days').fetchone()[0] == 354
assert db.execute("SELECT COUNT(*) FROM demo_a_costs WHERE cost_date>'2026-09-24'").fetchone()[0] == 0
assert db.execute('SELECT COUNT(*) FROM demo_a_projects p JOIN demo_a_employees e ON e.employee_id=p.manager_id WHERE p.department_id<>e.department_id').fetchone()[0] == 0

result = {'counts': {}, 'annual': {}}
for table in ('departments','employees','projects','costs','leave_days'):
    result['counts'][table] = db.execute('SELECT COUNT(*) FROM demo_a_'+table).fetchone()[0]
for year in (2025,2026):
    start, end = f'{year}-01-01', f'{year+1}-01-01'
    result['annual'][year] = {
        'projects_started': db.execute('SELECT COUNT(*) FROM demo_a_projects WHERE start_date>=? AND start_date<?',(start,end)).fetchone()[0],
        'projects_active': db.execute('SELECT COUNT(*) FROM demo_a_projects WHERE start_date<? AND (actual_end_date IS NULL OR actual_end_date>=?)',(end,start)).fetchone()[0],
        'costs_eur': db.execute('SELECT SUM(amount_eur) FROM demo_a_costs WHERE cost_date>=? AND cost_date<?',(start,end)).fetchone()[0],
        'leave_employees': db.execute("SELECT COUNT(DISTINCT employee_id) FROM demo_a_leave_days WHERE leave_type='GODISNJI' AND leave_status='ISKORISTEN' AND leave_date>=? AND leave_date<?",(start,end)).fetchone()[0],
        'leave_days': db.execute("SELECT SUM(day_fraction) FROM demo_a_leave_days WHERE leave_type='GODISNJI' AND leave_status='ISKORISTEN' AND leave_date>=? AND leave_date<?",(start,end)).fetchone()[0]
    }
    assert result['annual'][year]['projects_started'] == 18
    assert result['annual'][year]['leave_employees'] == (20 if year==2025 else 22)
    assert result['annual'][year]['leave_days'] == (100 if year==2025 else 110)
result['total_cost_eur'] = db.execute('SELECT SUM(amount_eur) FROM demo_a_costs').fetchone()[0]
result['total_budget_eur'] = db.execute('SELECT SUM(budget_eur) FROM demo_a_projects').fetchone()[0]
result['overspend_projects'] = db.execute('SELECT COUNT(*) FROM (SELECT p.project_id FROM demo_a_projects p JOIN demo_a_costs c ON c.project_id=p.project_id GROUP BY p.project_id,p.budget_eur HAVING SUM(c.amount_eur)>p.budget_eur)').fetchone()[0]
print(json.dumps(result, indent=2))
print('PASS: offline reference data, foreign keys, date rules, uniqueness and baseline answers. Oracle runtime not tested.')
