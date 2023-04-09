#!/usr/bin/env python3


from pycparser import c_parser, c_ast, c_generator
import math, sys, os.path
from pprint import pprint


# GLOBALS
code = ""
fname = ""
variables = []

class MyVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self.variables = {}
        self.current_parent = {}
    def generic_visit(self, node):
        oldparent = self.current_parent
        self.current_parent = node
        for c in node:
            self.visit(c)
        self.current_parent = oldparent

    def visit_Decl(self, node):
        var_name = node.name
        self.variables[var_name] = {'decl_in_scope':True, 'read': False, 'write': False}
        self.generic_visit(node)

    def visit_Assignment(self, node):
        if isinstance(node.lvalue, c_ast.ID):
            var_name = node.lvalue.name
            if var_name not in self.variables.keys():
                self.variables[var_name] = {'decl_in_scope':False, "read": False, "write": True}
            else:
                self.variables[var_name]["write"] = True
        self.visit(node.rvalue)

    def visit_ID(self, node):
        if not isinstance(self.current_parent, c_ast.FuncCall):
            var_name = node.name
            if var_name not in self.variables.keys():
                self.variables[var_name] = {'decl_in_scope':False, "read": True, "write": False}
            else:
                self.variables[var_name]["read"] = True
        self.generic_visit(node)
   
    def visit_UnaryOp(self, node):
        var_name = node.expr.name
        if '++' in node.op or '--' in node.op:
            if var_name not in self.variables.keys():
                self.variables[var_name] = {'decl_in_scope':False, "read": False, "write": True}
            else:
                self.variables[var_name]["write"] = True
        self.generic_visit(node)


class NodeVist(c_ast.NodeVisitor):
    def __init__(self):
        self.structs = []

    def visit_FuncDef(self, node):
        if node.decl.name == "main":
            self.structs = self.structs+(node.body.block_items)



def error(msg):
    print("Error:", msg)
    exit(0)

# ERROR CHECKS
if len(sys.argv) < 2:
    error("No file passed\n  - ladders.py [filename]")

if os.path.isfile(sys.argv[1]):
    f = open(sys.argv[1], "r")
    code = f.read()
    fname = sys.argv[1]
    if fname.split(".")[-1] != "lad":
        error("Invalid extension\n   - requires .lad file")
    f.close()
else:
    error(f"File not found\n  - {sys.argv[1]}")

tem1 = ""
tem2 = ""

for i in code.split("\n"):
    if i.strip() != "" and i.strip()[0] == "#" or i.strip()[:2] == "//":
        tem1 += i + "\n"
    else:
        tem2 += i + "\n"

code = tem2


parser = c_parser.CParser()
ast = parser.parse(code)
visitor = NodeVist()

visitor.visit(ast)

struct_list = visitor.structs


top_level_vars = {}
code_segments = []
for node in struct_list:
    # Parse the C code and get the AST

    # Visit the AST nodes and collect information about variables
    visitor = MyVisitor()
    visitor.visit(node)

    # Print the variables and whether they are read or written
    vars = {}
    if isinstance(node, c_ast.Decl):
        vars[node.name] = {'read': True, 'write': True, 'is_decl':True}
        top_level_vars[node.name] = -1
    for key, value in visitor.variables.items():
        if not value['decl_in_scope']:
            vars[key] = {'read': value['read'], 'write': value['write'], 'is_decl': False}
    if not len(vars.items()) == 0:
        generator = c_generator.CGenerator()
    vars['_node'] = generator.visit(node)
    code_segments.append(vars)

data = code_segments
vars = top_level_vars

pprint(data)

sched = {}
decs = []
n = len(data)

for i in range(n):
    print(vars)
    maxn = 0
    if len(data[i]) == 1:
        arr = sched.get(math.ceil(max(vars.values())), [])
        arr.append(i)
        sched[math.ceil(max(vars.values()))] = arr
        continue
    for var in data[i].keys():
        if var == "_node":
            continue
        v = data[i][var]
        if v["is_decl"]:
            decs.append(i)
            break
        if v["write"]:
            vars[var] = math.ceil(vars[var] + 1)
            maxn = maxn if maxn > vars[var] else math.floor(vars[var])
        elif v["read"]:
            vars[var] = math.floor(vars[var])
            maxn = maxn if maxn > vars[var] else vars[var] + 1
            vars[var] += 0.5
    for var in data[i].keys():
        if var == "_node":
            continue
        v = data[i][var]
        if v["is_decl"]:
            break
        vars[var] = maxn

    else:
        arr = sched.get(maxn, [])
        arr.append(i)
        sched[maxn] = arr

print(decs)
print(sched)

# gen sched
sname = f"{fname.split('.')[0]}.sched"
sched_data = "Declarations:\n" + ", ".join(map(str, decs)) + "\n\nSchedule:\n"
for i in sched.keys():
    sched_data += f"batch {i} : " + ", ".join(map(str, sched[i])) + "\n"

with open(sname, "w+") as f:
    f.write(sched_data)

# gen sched
sname = f"{fname.split('.')[0]}.c"
sched_data = "Declarations:\n" + ", ".join(map(str, decs)) + "\n\nSchedule:\n"
for i in sched.keys():
    sched_data += f"batch {i} : " + ", ".join(map(str, sched[i])) + "\n"


generator = c_generator.CGenerator()
output = "#include <omp.h>\n" + tem1 + "\n\n"

for i in ast.ext:
    if (isinstance(i, c_ast.FuncDef) and i.decl.name == "main"):
        output += "int main()\n{\n"
        for i in decs:
            output += data[i]["_node"] + ";\n"

        for i in sched.keys():
            output += "#pragma omp sections\n{\n"
            for j in sched[i]:
                output += "#pragma omp section\n{\n"
                output += data[j]["_node"] + ";\n"
                output += "}\n"
            output += "}\n"
        output += "return 0;\n}\n"
    else:
        output += generator.visit(i) + ";\n"

print(output)

with open(sname, "w+") as f:
    f.write(output)
