"""Fail-closed, deliberately small Oracle SELECT dialect for synthetic demo data.

SQLGlot is a parser, not a security validator. This layer explicitly restricts
AST node types, names, columns and functions; only its canonical output executes.
Do not broaden this policy to arbitrary production SQL without security review.
"""
import datetime
import hashlib
import re
import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

TABLES = {
    'DEMO_A_DEPARTMENTS': {'DEPARTMENT_ID', 'DEPARTMENT_NAME'},
    'DEMO_A_EMPLOYEES': {'EMPLOYEE_ID', 'EMPLOYEE_NAME', 'DEPARTMENT_ID', 'HIRED_ON'},
    'DEMO_A_PROJECTS': {'PROJECT_ID', 'PROJECT_CODE', 'PROJECT_NAME', 'CUSTOMER_NAME',
                        'DEPARTMENT_ID', 'MANAGER_ID', 'START_DATE', 'PLANNED_END_DATE',
                        'ACTUAL_END_DATE', 'PROJECT_STATUS', 'BUDGET_EUR'},
    'DEMO_A_COSTS': {'COST_ID', 'PROJECT_ID', 'COST_DATE', 'COST_CATEGORY', 'AMOUNT_EUR'},
    'DEMO_A_LEAVE_DAYS': {'LEAVE_DAY_ID', 'EMPLOYEE_ID', 'LEAVE_DATE', 'LEAVE_TYPE',
                          'LEAVE_STATUS', 'DAY_FRACTION'},
}
ALLOWED = {
    'Select', 'From', 'Table', 'TableAlias', 'Identifier', 'Column', 'Alias',
    'Where', 'Group', 'Having', 'Order', 'Ordered', 'Join', 'Distinct', 'Literal',
    'Null', 'Star', 'Paren', 'And', 'Or', 'Not', 'EQ', 'NEQ', 'GT', 'GTE', 'LT',
    'LTE', 'Is', 'Between', 'In', 'Like', 'Add', 'Sub', 'Mul', 'Div', 'Neg',
    'Count', 'Sum', 'Avg', 'Min', 'Max', 'Abs', 'Round', 'Coalesce', 'Nullif',
    'Extract', 'Var', 'DateStrToDate', 'StrToDate', 'Case', 'If',
}


class Rejected(ValueError):
    pass


def digest(sql):
    return hashlib.sha256(sql.encode('utf-8')).hexdigest()


def validate_question(question):
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise Rejected('Question must contain 1-2000 characters.')
    if any(ord(c) < 32 or ord(c) == 127 for c in question):
        raise Rejected('Control characters are not accepted.')
    if re.search(r'SELECT\s+AI', question, re.I):
        raise Rejected('Send a question, not a SELECT AI command.')
    return question.strip()


def canonical_sql(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw.encode()) > 16000:
        raise Rejected('SQL proposal is missing or too long.')
    # Refuse comments, hints, links and control syntax even inside literals.
    if any(mark in raw for mark in ('--', '/*', '*/', '@', '`', '\\')):
        raise Rejected('Comments, hints, links and escape syntax are not permitted.')
    if any(ord(c) < 32 and c not in '\r\n\t' for c in raw):
        raise Rejected('Control characters in SQL are not permitted.')
    text = raw.strip()
    if text.endswith(';'):
        text = text[:-1].rstrip()
    if ';' in text:
        raise Rejected('Only one statement is permitted.')
    try:
        trees = sqlglot.parse(text, read='oracle', error_level=ErrorLevel.RAISE)
    except Exception:
        raise Rejected('Cannot parse this proposal as an allowed Oracle SELECT.') from None
    if len(trees) != 1 or type(trees[0]) is not exp.Select:
        raise Rejected('Only a single plain SELECT is permitted.')
    tree = trees[0]
    nodes = list(tree.walk())
    if len(nodes) > 400 or len(list(tree.find_all(exp.Select))) != 1:
        raise Rejected('Complex/nested queries are outside this demo policy.')
    for node in nodes:
        if type(node).__name__ not in ALLOWED or node.comments:
            raise Rejected('Unsupported SQL construct: ' + type(node).__name__)
        if isinstance(node, exp.Identifier):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', node.name):
                raise Rejected('Only simple SQL identifiers are allowed.')
            # Canonical SQL always quotes normalized names, including aliases.
            node.set('this', node.name.upper())
            node.set('quoted', True)
        if isinstance(node, exp.Star) and type(node.parent) is not exp.Count:
            raise Rejected('List columns explicitly; only COUNT(*) may use a star.')
        if isinstance(node, exp.Var):
            if type(node.parent) is not exp.Extract or node.name.upper() not in {'YEAR', 'MONTH', 'DAY'}:
                raise Rejected('Only YEAR, MONTH or DAY extraction is allowed.')
        if type(node).__name__ in {'DateStrToDate', 'StrToDate'}:
            value = node.args.get('this')
            if not isinstance(value, exp.Literal) or not value.is_string:
                raise Rejected('Dates must be ISO date literals.')
            try:
                if datetime.date.fromisoformat(value.this).isoformat() != value.this:
                    raise ValueError()
            except ValueError:
                raise Rejected('Dates must be YYYY-MM-DD literals.') from None
            if type(node).__name__ == 'StrToDate':
                fmt = node.args.get('format')
                if not isinstance(fmt, exp.Literal) or fmt.this != '%Y-%m-%d':
                    raise Rejected('Only the ISO date format is allowed.')
    tables = list(tree.find_all(exp.Table))
    if not 1 <= len(tables) <= 5:
        raise Rejected('Use between one and five permitted demo tables.')
    aliases = {}
    available = set()
    for table in tables:
        if table.catalog or table.db != 'WEBUI_MCP' or table.name not in TABLES:
            raise Rejected('Only the five explicit WEBUI_MCP.DEMO_A_* tables are allowed.')
        alias = table.alias_or_name
        if alias in aliases:
            raise Rejected('Table aliases must be unique.')
        aliases[alias] = TABLES[table.name]
        available |= TABLES[table.name]
    output_aliases = {node.alias for node in tree.expressions if isinstance(node, exp.Alias)}
    for column in tree.find_all(exp.Column):
        if column.catalog or column.db or column.args.get('join_mark'):
            raise Rejected('Unsupported qualified/legacy column expression.')
        if column.table:
            if column.table not in aliases or column.name not in aliases[column.table]:
                raise Rejected('Column is not in the selected demo table.')
        elif column.name not in available | output_aliases:
            raise Rejected('Unknown demo column or output alias.')
    for join in tree.find_all(exp.Join):
        if join.args.get('on') is None or join.args.get('using') or join.args.get('method'):
            raise Rejected('Joins require an explicit ON condition; no cross/natural/USING joins.')
    try:
        canonical = tree.sql(dialect='oracle', identify=True, pretty=True,
                             unsupported_level=ErrorLevel.RAISE)
    except Exception:
        raise Rejected('Cannot safely render the supported Oracle subset.') from None
    if len(canonical.encode()) > 16000:
        raise Rejected('Canonical SQL exceeds the review limit.')
    return canonical
