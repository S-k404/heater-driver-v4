"""Minimal S-expression parser/serializer for KiCad files."""
import re
class Sym(str):
    pass
class Raw(str):
    pass
_tok = re.compile(r'\s*(?:(\()|(\))|("(?:\\.|[^"\\])*")|([^\s()"]+))')
def parse(text):
    stack=[[]]; pos=0
    while True:
        m=_tok.match(text,pos)
        if not m or m.end()==pos: break
        pos=m.end()
        if m.group(1): stack.append([])
        elif m.group(2):
            l=stack.pop(); stack[-1].append(l)
        elif m.group(3) is not None:
            stack[-1].append(Raw(m.group(3)[1:-1]))
        else:
            stack[-1].append(Sym(m.group(4)))
    return stack[0]
def q(s):
    if isinstance(s,Raw): return '"'+s+'"'
    return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def dump(e,ind=0):
    if isinstance(e,list):
        simple=all(not isinstance(x,list) for x in e)
        if simple:
            return '('+' '.join(dump(x) for x in e)+')'
        out='('+' '.join(dump(x) for x in e if not isinstance(x,list))
        for x in e:
            if isinstance(x,list):
                out+='\n'+'\t'*(ind+1)+dump(x,ind+1)
        return out+'\n'+'\t'*ind+')'
    if isinstance(e,Sym): return str(e)
    if isinstance(e,(int,)): return str(e)
    if isinstance(e,float):
        s=('%.4f'%e).rstrip('0').rstrip('.')
        return s if s not in ('-0','') else '0'
    return q(e)
def find(e,key):
    return [x for x in e if isinstance(x,list) and x and x[0]==key]
def find1(e,key):
    r=find(e,key); return r[0] if r else None
