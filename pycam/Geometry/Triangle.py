# -*- coding: utf-8 -*-
"""
$Id$

Copyright 2008-2010 Lode Leroy
Copyright 2010 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

from pycam.Geometry.Point import Point, Vector, normalized
from pycam.Geometry.Plane import Plane
from pycam.Geometry.Line import Line
from pycam.Geometry import TransformableContainer, IDGenerator
import pycam.Utils.log


try:
    import OpenGL.GL as GL
    import OpenGL.GLU as GLU
    import OpenGL.GLUT as GLUT
    GL_enabled = True
except ImportError:
    GL_enabled = False


class Triangle(IDGenerator, TransformableContainer):

    __slots__ = ["id", "p1", "p2", "p3", "normal", "minx", "maxx", "miny",
            "maxy", "minz", "maxz", "e1", "e2", "e3", "normal", "center",
            "radius", "radiussq", "middle"]

    def __init__(self, p1=None, p2=None, p3=None, n=None):
        # points are expected to be in ClockWise order
        super(Triangle, self).__init__()
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.normal = n
        self.reset_cache()

    def reset_cache(self):
        self.minx = min(self.p1[0], self.p2[0], self.p3[0])
        self.miny = min(self.p1[1], self.p2[1], self.p3[1])
        self.minz = min(self.p1[2], self.p2[2], self.p3[2])
        self.maxx = max(self.p1[0], self.p2[0], self.p3[0])
        self.maxy = max(self.p1[1], self.p2[1], self.p3[1])
        self.maxz = max(self.p1[2], self.p2[2], self.p3[2])
        self.e1 = Line(self.p1, self.p2)
        self.e2 = Line(self.p2, self.p3)
        self.e3 = Line(self.p3, self.p1)
        # calculate normal, if p1-p2-pe are in clockwise order
        if self.normal is None:
            self.normal = self.p3.sub(self.p1).cross(self.p2.sub( \
                    self.p1)).normalized()
        # make sure that the normal has always a unit length
        self.normal = normalized(self.normal)
        self.center = (self.p1 + self.p2 + self.p3) / 3
        self.plane = Plane(self.center, self.normal)
        # calculate circumcircle (resulting in radius and middle)
        denom = self.p2.sub(self.p1).cross(self.p3.sub(self.p2)).norm
        self.radius = (self.p2.sub(self.p1).norm \
                * self.p3.sub(self.p2).norm * self.p3.sub(self.p1).norm) \
                / (2 * denom)
        self.radiussq = self.radius ** 2
        denom2 = 2 * denom * denom
        alpha = self.p3.sub(self.p2).normsq \
                * self.p1.sub(self.p2).dot(self.p1.sub(self.p3)) / denom2
        beta  = self.p1.sub(self.p3).normsq \
                * self.p2.sub(self.p1).dot(self.p2.sub(self.p3)) / denom2
        gamma = self.p1.sub(self.p2).normsq \
                * self.p3.sub(self.p1).dot(self.p3.sub(self.p2)) / denom2
        self.middle = Point(
                self.p1[0] * alpha + self.p2[0] * beta + self.p3[0] * gamma,
                self.p1[1] * alpha + self.p2[1] * beta + self.p3[1] * gamma,
                self.p1[2] * alpha + self.p2[2] * beta + self.p3[2] * gamma)

    def __repr__(self):
        return "Triangle%d<%s,%s,%s>" % (self.id, self.p1, self.p2, self.p3)

    def copy(self):
        return self.__class__(self.p1.copy(), self.p2.copy(), self.p3.copy(),
                self.normal.copy())

    def next(self):
        yield self.p1
        yield self.p2
        yield self.p3
        yield self.normal

    def get_points(self):
        return (self.p1, self.p2, self.p3)

    def get_children_count(self):
        # tree points per triangle
        return 7

    def to_OpenGL(self, color=None, show_directions=False):
        if not GL_enabled:
            return
        if not color is None:
            GL.glColor4f(*color)
        GL.glBegin(GL.GL_TRIANGLES)
        # use normals to improve lighting (contributed by imyrek)
        normal_t = self.normal
        GL.glNormal3f(normal_t[0], normal_t[1], normal_t[2])
        # The triangle's points are in clockwise order, but GL expects
        # counter-clockwise sorting.
        GL.glVertex3f(self.p1[0], self.p1[1], self.p1[2])
        GL.glVertex3f(self.p3[0], self.p3[1], self.p3[2])
        GL.glVertex3f(self.p2[0], self.p2[1], self.p2[2])
        GL.glEnd()
        if show_directions: # display surface normals
            n = self.normal
            c = self.center
            d = 0.5
            GL.glBegin(GL.GL_LINES)
            GL.glVertex3f(c[0], c[1], c[2])
            GL.glVertex3f(c[0]+n[0]*d, c[1]+n[1]*d, c[2]+n[2]*d)
            GL.glEnd()
        if False: # display bounding sphere
            GL.glPushMatrix()
            middle = self.middle
            GL.glTranslate(middle[0], middle[1], middle[2])
            if not hasattr(self, "_sphere"):
                self._sphere = GLU.gluNewQuadric()
            GLU.gluSphere(self._sphere, self.radius, 10, 10)
            GL.glPopMatrix()
        if pycam.Utils.log.is_debug(): # draw triangle id on triangle face
            GL.glPushMatrix()
            c = self.center
            GL.glTranslate(c[0], c[1], c[2])
            p12 = self.p1.add(self.p2).mul(0.5)
            p3_12 = self.p3.sub(p12).normalized()
            p2_1 = self.p1.sub(self.p2).normalized()
            pn = p2_1.cross(p3_12)
            GL.glMultMatrixf((p2_1[0], p2_1[1], p2_1[2], 0, p3_12[0], p3_12[1],
                    p3_12[2], 0, pn[0], pn[1], pn[2], 0, 0, 0, 0, 1))
            n = self.normal.mul(0.01)
            GL.glTranslatef(n[0], n[1], n[2])
            maxdim = max((self.maxx - self.minx), (self.maxy - self.miny),
                    (self.maxz - self.minz))
            factor = 0.001
            GL.glScalef(factor * maxdim, factor * maxdim, factor * maxdim)
            w = 0
            id_string = "%s." % str(self.id)
            for ch in id_string:
                w += GLUT.glutStrokeWidth(GLUT.GLUT_STROKE_ROMAN, ord(ch))
            GL.glTranslate(-w/2, 0, 0)
            for ch in id_string:
                GLUT.glutStrokeCharacter(GLUT.GLUT_STROKE_ROMAN, ord(ch))
            GL.glPopMatrix()
        if False: # draw point id on triangle face
            c = self.center
            p12 = self.p1.add(self.p2).mul(0.5)
            p3_12 = self.p3.sub(p12).normalized()
            p2_1 = self.p1.sub(self.p2).normalized()
            pn = p2_1.cross(p3_12)
            n = self.normal.mul(0.01)
            for p in (self.p1, self.p2, self.p3):
                GL.glPushMatrix()
                pp = p.sub(p.sub(c).mul(0.3))
                GL.glTranslate(pp[0], pp[1], pp[2])
                GL.glMultMatrixf((p2_1[0], p2_1[1], p2_1[2], 0, p3_12[0], p3_12[1],
                        p3_12[2], 0, pn[0], pn[1], pn[2], 0, 0, 0, 0, 1))
                GL.glTranslatef(n[0], n[1], n[2])
                GL.glScalef(0.001, 0.001, 0.001)
                w = 0
                for ch in str(p.id):
                    w += GLUT.glutStrokeWidth(GLUT.GLUT_STROKE_ROMAN, ord(ch))
                    GL.glTranslate(-w/2, 0, 0)
                for ch in str(p.id):
                    GLUT.glutStrokeCharacter(GLUT.GLUT_STROKE_ROMAN, ord(ch))
                GL.glPopMatrix()

    def is_point_inside(self, p):
        # http://www.blackpawn.com/texts/pointinpoly/default.html
        # Compute vectors
        v0 = self.p3.sub(self.p1)
        v1 = self.p2.sub(self.p1)
        v2 = p.sub(self.p1)
        # Compute dot products
        dot00 = v0.dot(v0)
        dot01 = v0.dot(v1)
        dot02 = v0.dot(v2)
        dot11 = v1.dot(v1)
        dot12 = v1.dot(v2)
        # Compute barycentric coordinates
        denom = dot00 * dot11 - dot01 * dot01
        if denom == 0:
            return False
        invDenom = 1.0 / denom
        # Originally, "u" and "v" are multiplied with "1/denom".
        # We don't do this to avoid division by zero (for triangles that are
        # "almost" invalid).
        u = (dot11 * dot02 - dot01 * dot12) * invDenom
        v = (dot00 * dot12 - dot01 * dot02) * invDenom
        # Check if point is in triangle
        return (u > 0) and (v > 0) and (u + v < 1)

    def subdivide(self, depth):
        sub = []
        if depth == 0:
            sub.append(self)
        else:
            p4 = self.p1.add(self.p2).div(2)
            p5 = self.p2.add(self.p3).div(2)
            p6 = self.p3.add(self.p1).div(2)
            sub += Triangle(self.p1, p4, p6).subdivide(depth - 1)
            sub += Triangle(p6, p5, self.p3).subdivide(depth - 1)
            sub += Triangle(p6, p4, p5).subdivide(depth - 1)
            sub += Triangle(p4, self.p2, p5).subdivide(depth - 1)
        return sub

    def get_area(self):
        cross = self.p2.sub(self.p1).cross(self.p3.sub(self.p1))
        return cross.norm / 2

