"""Just enough of KiCad's S-expression format to edit a schematic without disturbing the rest of it.

parse() returns nested lists of atoms; every list also records where it sits in the source text
(Node.span), so an edit can cut or insert whole items and leave every other byte alone. That keeps
the diff of a regenerated schematic down to the parts that actually changed.
"""
import re

TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


class Node(list):
    span = (0, 0)

    @property
    def head(self):
        return self[0] if self and isinstance(self[0], str) else None

    def find(self, head):
        return next((c for c in self if isinstance(c, Node) and c.head == head), None)

    def findall(self, head):
        return [c for c in self if isinstance(c, Node) and c.head == head]

    def value(self, head, i=1):
        c = self.find(head)
        return c[i] if c is not None and len(c) > i else None


def unquote(s):
    return s[1:-1].replace('\\"', '"').replace('\\\\', '\\') if s.startswith('"') else s


def quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def parse(text):
    stack, root = [], None
    for m in TOKEN.finditer(text):
        t = m.group()
        if t == '(':
            n = Node(); n.span = (m.start(), None)
            if stack: stack[-1].append(n)
            stack.append(n)
        elif t == ')':
            n = stack.pop(); n.span = (n.span[0], m.end())
            if not stack: root = n
        else:
            stack[-1].append(unquote(t) if t.startswith('"') else t)
    return root


def props(sym):
    """{property name: value} of a placed symbol."""
    return {p[1]: p[2] for p in sym.findall('property')}
