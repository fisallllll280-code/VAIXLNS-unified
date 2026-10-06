"""Deterministic parser for the VAIXLNS ROOT LNS syntax.

Lineage: fisallllll280-code/vaixlns-csd-kernel@95e059bef6022edbfa6ed64e169dccadea668ea8
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import re

TOKEN = re.compile(
    r'(?P<WS>\s+)|(?P<STRING>"(?:\\.|[^"\\])*")|(?P<ARROW>->)|'
    r'(?P<SYMBOL>[{}\[\],])|(?P<ATOM>[A-Za-z0-9_.:/-]+)'
)

@dataclass(frozen=True)
class Tok:
    kind: str
    value: str
    position: int

def tokenize(source: str) -> list[Tok]:
    out=[]; pos=0
    for match in TOKEN.finditer(source):
        if match.start()!=pos:
            raise ValueError(f"UNEXPECTED_TOKEN_AT:{pos}")
        pos=match.end()
        kind=match.lastgroup
        if kind=="WS": continue
        out.append(Tok(kind,match.group(0),match.start()))
    if pos!=len(source):
        raise ValueError(f"UNEXPECTED_TOKEN_AT:{pos}")
    return out

class Parser:
    def __init__(self,source:str)->None:
        self.source=source; self.tokens=tokenize(source); self.i=0
    def peek(self)->Tok|None:
        return self.tokens[self.i] if self.i<len(self.tokens) else None
    def take(self)->Tok:
        token=self.peek()
        if token is None: raise ValueError("UNEXPECTED_EOF")
        self.i+=1; return token
    def expect(self,kind:str,value:str|None=None)->Tok:
        token=self.take()
        if token.kind!=kind or (value is not None and token.value!=value):
            raise ValueError(f"EXPECTED:{kind}:{value or ''}:GOT:{token.kind}:{token.value}")
        return token
    def scalar(self)->Any:
        token=self.take()
        if token.kind=="STRING":
            return bytes(token.value[1:-1],"utf-8").decode("unicode_escape")
        if token.kind!="ATOM": raise ValueError(f"EXPECTED_SCALAR:{token.value}")
        if token.value in {"true","false"}: return token.value=="true"
        try: return float(token.value) if "." in token.value else int(token.value)
        except ValueError: return token.value
    def value(self)->Any:
        token=self.peek()
        if token is None: raise ValueError("VALUE_REQUIRED")
        if token.kind=="SYMBOL" and token.value=="[":
            self.take(); values=[]
            while True:
                if self.peek() is None: raise ValueError("UNCLOSED_LIST")
                if self.peek().kind=="SYMBOL" and self.peek().value=="]":
                    self.take(); return values
                values.append(self.value())
                if self.peek() and self.peek().kind=="SYMBOL" and self.peek().value==",": self.take()
        return self.scalar()
    def add(self,target:dict[str,Any],key:str,value:Any)->None:
        if key not in target: target[key]=value
        elif isinstance(target[key],list): target[key].append(value)
        else: target[key]=[target[key],value]
    def block(self)->dict[str,Any]:
        self.expect("SYMBOL","{"); result={}
        while True:
            token=self.peek()
            if token is None: raise ValueError("UNCLOSED_BLOCK")
            if token.kind=="SYMBOL" and token.value=="}": self.take(); return result
            if token.kind!="ATOM": raise ValueError(f"EXPECTED_KEY:{token.value}")
            key=self.take().value
            if key=="link":
                source=self.expect("ATOM").value
                self.expect("ARROW","->")
                target_name=self.expect("ATOM").value
                result.setdefault("links",[]).append({"from":source,"to":target_name}); continue
            nxt=self.peek()
            if nxt and nxt.kind=="SYMBOL" and nxt.value=="{":
                self.add(result,key,self.block()); continue
            if nxt and nxt.kind in {"STRING","ATOM"}:
                saved=self.i; name=self.value()
                if self.peek() and self.peek().kind=="SYMBOL" and self.peek().value=="{":
                    self.add(result,key,{"name":name,**self.block()}); continue
                self.i=saved
            self.add(result,key,self.value())
    def parse(self)->dict[str,Any]:
        root_key=self.expect("ATOM").value
        return {root_key:self.block()}

def parse(source:str)->dict[str,Any]:
    return Parser(source).parse()
