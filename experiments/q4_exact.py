"""Exact rational predicates for Q4 directional witness certificates."""
from fractions import Fraction


def q(value):
    if isinstance(value,Fraction): return value
    if isinstance(value,int): return Fraction(value)
    if not isinstance(value,str):
        raise TypeError('exact coordinates must be integer or decimal strings')
    return Fraction(value)


def point(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2:
        raise ValueError('point must have two coordinates')
    return q(value[0]),q(value[1])


def cross(o,a,b):
    return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])


def hull(points):
    pts=sorted(set(points))
    if len(pts)<=1:return pts
    lower=[]
    for p in pts:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(pts):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def in_closed_convex_polygon(p, polygon):
    h=hull(polygon)
    return len(h)>=3 and all(cross(h[i],h[(i+1)%len(h)],p)>=0 for i in range(len(h)))


def squared_distance(a,b):
    return (a[0]-b[0])**2+(a[1]-b[1])**2


def cell_vertices(depth,ix,iy,domain=Fraction(1800)):
    width=2*domain/Fraction(2**depth)
    x=-domain+ix*width;y=-domain+iy*width
    return ((x,y),(x+width,y),(x+width,y+width),(x,y+width))


def cell_outside_disk(vertices,radius=Fraction(1800)):
    lo_x,lo_y=vertices[0];hi_x,hi_y=vertices[2]
    x=Fraction(0) if lo_x<=0<=hi_x else min((lo_x,hi_x),key=abs)
    y=Fraction(0) if lo_y<=0<=hi_y else min((lo_y,hi_y),key=abs)
    return x*x+y*y>radius*radius


def witness_valid(vertices,stations,witness,radius):
    if len(set(witness))<3 or any(i<0 or i>=len(stations) for i in witness):return False
    selected=[stations[i] for i in witness]
    h=hull(selected)
    return len(h)>=3 and all(in_closed_convex_polygon(v,h) for v in vertices) and all(
        squared_distance(v,s)<=radius*radius for v in vertices for s in selected)


def overlap_guard_valid(station_id,stations,witness,radius,domain_radius):
    p=stations[station_id]
    if squared_distance(p,(Fraction(0),Fraction(0)))>domain_radius*domain_radius:return False
    if station_id in witness:return False
    return witness_valid((p,),stations,witness,radius)
