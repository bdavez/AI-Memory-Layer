# backend/validate_server.py
import ast
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(ROOT, "server.py")

def main():
    with open(SERVER, "r") as f:
        src = f.read()

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"[FAIL] Syntax error in server.py: {e}")
        sys.exit(1)

    funcs = {}
    routes = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            funcs.setdefault(node.name, 0)
            funcs[node.name] += 1
            self.generic_visit(node)

        def visit_Call(self, node):
            # crude detection of @app.route decorators
            if isinstance(node.func, ast.Attribute) and node.func.attr == "route":
                if node.args and isinstance(node.args[0], ast.Constant):
                    routes.append(node.args[0].value)
            self.generic_visit(node)

    Visitor().visit(tree)

    dup_funcs = [name for name, count in funcs.items() if count > 1]
    if dup_funcs:
        print(f"[FAIL] Duplicate function definitions: {dup_funcs}")
        sys.exit(1)

    if len(routes) != len(set(routes)):
        print("[FAIL] Duplicate route paths detected")
        sys.exit(1)

    print("[OK] server.py structure looks clean.")

if __name__ == "__main__":
    main()
