"""Regression checks: arming state must be checked inside the execution lock."""
import inspect
import ast
import secure_trade_routes as routes


def _lock_contains_arm_guard(fn):
    tree = ast.parse(inspect.getsource(fn))
    function = tree.body[0]
    locks = [node for node in ast.walk(function)
             if isinstance(node, ast.With) and any(
                 isinstance(item.context_expr, ast.Name) and item.context_expr.id == '_LOCK'
                 for item in node.items)]
    assert locks, 'Trading route must acquire the shared lock'
    assert any(isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)
               and isinstance(n.operand, ast.Name) and n.operand.id == '_ARMED'
               for lock in locks for statement in lock.body for n in ast.walk(statement)), \
        'Trading armed check must occur inside the shared lock'


def test_preview_arm_guard_inside_lock():
    _lock_contains_arm_guard(routes.preview)


def test_execute_arm_guard_inside_lock():
    _lock_contains_arm_guard(routes.execute)
