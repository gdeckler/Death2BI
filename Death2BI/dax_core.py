"""Bounded DAX AST interpreted by Python. Uploaded expressions never execute as code."""
import re, time, math
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

TOKEN=re.compile(r"\s+|//[^\n]*|--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|\[(?:\]\]|[^\]])*\]|\"(?:\"\"|[^\"])*\"|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_][\w.]*|==|&&|\|\||<>|<=|>=|[&+*/^=<>(),{}-]")
class Parser:
 def __init__(self,text,functions=None):
  self.functions={f["Name"].upper() for f in functions or []}
  if len(text)>2000000: raise ValueError('DAX expression exceeds 2 MB parser source limit')
  self.ts=[]; pos=0; code_size=0
  for m in TOKEN.finditer(text):
   if m.start()!=pos: raise ValueError('Unsupported DAX syntax near '+text[pos:pos+30])
   pos=m.end(); t=m.group()
   if not t.isspace() and not t.startswith(('//','/*','--')):
    code_size+=2 if t.startswith(chr(34)) else len(t)
    if code_size>100000:raise ValueError('DAX executable expression exceeds parser size limit')
    self.ts.append(t)
  if text[pos:].strip():
   if text[pos:].strip()==chr(34):raise ValueError('Unmatched trailing quote in source DAX at character '+str(pos+1))
   raise ValueError('Unsupported DAX syntax at character '+str(pos+1))
  if len(self.ts)>32768:raise ValueError('DAX token limit exceeded (32,768 tokens)')
  depth=0
  for token in self.ts:
   if token=='(':depth+=1
   if token==')':depth-=1
   if depth>64:raise ValueError('DAX nesting limit exceeded')
  self.i=0
 def peek(self): return self.ts[self.i] if self.i<len(self.ts) else ''
 def pop(self):
  t=self.peek()
  if not t: raise ValueError('Unexpected end of DAX')
  self.i+=1; return t
 def expect(self,t):
  if self.pop().upper()!=t: raise ValueError('Expected '+t)
 def parse(self):
  n=self.program()
  if self.peek(): raise ValueError('Unexpected DAX token '+self.peek())
  from dax_runtime import SPECIAL
  from dax_functions import FUNCTIONS
  def validate(node):
   if not isinstance(node,(tuple,list)):return
   if node and node[0]=='call':
    definition=SPECIAL.get(node[1]) or FUNCTIONS.get(node[1])
    if definition is None and node[1] in self.functions:definition=(0,99)
    if definition is None:raise ValueError('Unsupported DAX function: '+node[1]+' (see DAX_SUPPORT.md)')
    if not definition[0]<=len(node[2])<=definition[1]:raise ValueError('Invalid argument count for DAX '+node[1])
   for part in node:
    if isinstance(part,(tuple,list)):validate(part)
  validate(n)
  return n
 def program(self):
  vs=[]
  while self.peek().upper()=='VAR':
   self.pop(); name=self.pop(); self.expect('='); vs.append((name.casefold(),self.expr()))
  if vs: self.expect('RETURN')
  n=self.expr(); return ('let',vs,n) if vs else n
 def expr(self,minimum=0):
  t=self.pop(); u=t.upper()
  if t in (',',')','}'): self.i-=1; return ('lit',None)
  if u=='VAR': self.i-=1; return self.program()
  if u=='NOT' and self.peek()!='(': n=('call','NOT',[self.expr(3)])
  elif t in ('+','-'): n=('unary',t,self.expr(7))
  elif t=='(':
   n=self.program()
   if self.peek()==',':
    values=[n]
    while self.peek()==',':self.pop();values.append(self.expr())
    n=('tuple',values)
   self.expect(')')
  elif t=='{':
   values=[]
   if self.peek()!='}':
    while True:
     values.append(self.expr())
     if self.peek()!=',':break
     self.pop()
   self.expect('}');n=('table',values)
  elif t.startswith('['): n=('col',None,t[1:-1].replace(']]',']'))
  elif t.startswith('"'): n=('lit',t[1:-1].replace('""','"'))
  elif t[0].isdigit() or t.startswith('.'): n=('lit',float(t) if any(c in t for c in '.eE') else int(t))
  elif u=='DT' and self.peek().startswith('"'):n=('lit',dt.datetime.fromisoformat(self.pop()[1:-1]))
  elif self.peek()=='(':
   self.pop(); args=[]
   if self.peek()!=')':
    while True:
     args.append(self.program())
     if self.peek()!=',': break
     self.pop()
   self.expect(')'); n=('call',u,args)
  else:
   name=t[1:-1].replace("''", "'") if t.startswith("'") else t
   if self.peek().startswith('['): n=('col',name,self.pop()[1:-1].replace(']]',']'))
   else: n=('name',name)
  precedence={'||':1,'&&':2,'=':3,'==':3,'IN':3,'&':4,'<>':3,'<':3,'>':3,'<=':3,'>=':3,'+':5,'-':5,'*':6,'/':6,'^':8}
  while self.peek().upper() in precedence and precedence[self.peek().upper()]>=minimum:
   op=self.pop().upper(); n=('op',op,n,self.expr(precedence[op]+1))
  return n

def qi(x): return '"'+x.replace('"','""')+'"'
def sv(x):
 if x is None:return 'NULL'
 if isinstance(x,float):
  # A bare decimal literal may compare after rounding a DOUBLE column. Keep
  # fetched floating-point row identities typed as DOUBLE for exact roundtrips.
  if not math.isfinite(x):return "CAST('"+str(x)+"' AS DOUBLE)"
  value=repr(x);return value if 'e' in value.lower() else value+'e0'
 return str(x) if isinstance(x,(int,Decimal)) else "'"+str(x).replace("'","''")+"'"

def cached_ast(engine,expression):
    """Reuse immutable parsed expressions inside one secured calculation only."""
    expression=expression.strip().lstrip('=')
    expressions=engine.budget.setdefault('asts',{})
    if expression not in expressions:expressions[expression]=Parser(expression,engine.model.get('functions',[])).parse()
    return expressions[expression]

class CoreEvaluator:
    def __init__(self,con,model,contexts):
        self.con=con;self.model=model;self.contexts=contexts
        self.cache={};self.stack=[];self.deadline=time.monotonic()+8
    def measure(self,name,table=None):
        matches=[m for m in self.model['measures'] if m['Name'].casefold()==name.casefold() and (not table or m['TableName'].casefold()==table.casefold())]
        if len(matches)!=1:raise ValueError('Cannot resolve DAX measure '+name)
        measure=matches[0];key=(measure['TableName'],measure['Name'])
        if key in self.stack or len(self.stack)>=30:raise ValueError('Cyclic or excessive DAX measure dependency')
        self.stack.append(key)
        try:
            return self.run(cached_ast(self,measure['Expression']),{},None)
        finally:self.stack.pop()
    def run(self,n,env,row):
        if n[0]=='lit':return n[1]
        if n[0]=='let':
            local=dict(env)
            for name,expression in n[1]:local[name]=self.run(expression,local,row)
            return self.run(n[2],local,row)
        if n[0]=='name':
            if n[1].casefold() in env:return env[n[1].casefold()]
            if n[1].upper() in ('TRUE','FALSE'):return n[1].upper()=='TRUE'
            return self.table(n[1])
        raise ValueError('Unsupported DAX expression: '+str(n[:2]))
