# -*- coding: utf-8 -*-
"""
$Id$

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

from pycam.Geometry.Triangle import Triangle
try:
    import ode
except ImportError:
    ode = None


ShapeCylinder = lambda radius, height: ode.GeomCylinder(None, radius, height)
ShapeCapsule = lambda radius, height: ode.GeomCapsule(None, radius, height - (2 * radius))

_ode_override_state = None


def generate_physics(model, cutter, physics=None):
    if physics is None:
        physics = PhysicalWorld()
    physics.reset()
    physics.add_mesh((0, 0, 0), model.triangles())
    shape_info = cutter.get_shape("ODE")
    physics.set_drill(shape_info[0], (0.0, 0.0, 0.0))
    return physics

def is_ode_available():
    global _ode_override_state
    if not _ode_override_state is None:
        return _ode_override_state
    else:
        if ode is None:
            return False
        else:
            return True

def override_ode_availability(state):
    global _ode_override_state
    _ode_override_state = state

def convert_triangles_to_vertices_faces(triangles):
    corners = []
    faces = []
    id_index_map = {}
    for t in triangles:
        coords = []
        # TODO: check if we need to change the order of points for non-AOI models as well
        for p in (t.p1, t.p3, t.p2):
            # add the point to the id/index mapping, if necessary
            if not id_index_map.has_key(p.id):
                corners.append((p.x, p.y, p.z))
                id_index_map[p.id] = len(corners) - 1
            coords.append(id_index_map[p.id]) 
        faces.append(coords)
    return corners, faces

def get_parallelepiped_geom(low_points, high_points, space=None):
    triangles = (
            # front side
            Triangle(low_points[0], low_points[1], high_points[0]),
            Triangle(low_points[1], high_points[1], high_points[0]),
            # right side
            Triangle(low_points[1], low_points[2], high_points[1]),
            Triangle(low_points[2], high_points[2], high_points[1]),
            # back side
            Triangle(low_points[2], low_points[3], high_points[2]),
            Triangle(low_points[3], high_points[3], high_points[2]),
            # left side
            Triangle(low_points[3], low_points[0], high_points[3]),
            Triangle(low_points[0], high_points[0], high_points[3]),
            # bottom side
            Triangle(low_points[1], low_points[0], low_points[2]),
            Triangle(low_points[3], low_points[2], low_points[0]),
            # high side
            Triangle(high_points[0], high_points[1], high_points[2]),
            Triangle(high_points[2], high_points[3], high_points[0]),
    )
    mesh = ode.TriMeshData()
    vertices, faces = convert_triangles_to_vertices_faces(triangles)
    mesh.build(vertices, faces)
    geom = ode.GeomTriMesh(mesh, space)
    return geom


class PhysicalWorld:

    def __init__(self):
        self._world = ode.World()
        self._space = ode.Space()
        self._obstacles = []
        self._contacts = ode.JointGroup()
        self._drill = None
        self._drill_offset = None
        self._collision_detected = False

    def reset(self):
        self._world = ode.World()
        self._space = ode.Space()
        self._obstacles = []
        self._contacts = ode.JointGroup()
        self._drill = None
        self._drill_offset = None
        self._collision_detected = False

    def _add_geom(self, geom, position, append=True):
        body = ode.Body(self._world)
        body.setPosition(position)
        body.setGravityMode(False)
        geom.setBody(body)
        if append:
            self._obstacles.append(geom)

    def add_mesh(self, position, triangles):
        mesh = ode.TriMeshData()
        vertices, faces = convert_triangles_to_vertices_faces(triangles)
        mesh.build(vertices, faces)
        geom = ode.GeomTriMesh(mesh, self._space)
        self._add_geom(geom, position)

    def set_drill(self, shape, position):
        #geom = ode.GeomTransform(self._space)
        #geom.setOffset(position)
        #geom.setGeom(shape)
        #shape.setOffset(position)
        self._space.add(shape)
        # sadly PyODE forgets to update the "space" attribute that we need in
        # the cutters' "extend" functions
        shape.space = self._space
        self._add_geom(shape, position, append=False)
        self._drill_offset = position
        self._drill = shape
        self.reset_drill()

    def extend_drill(self, diff_x, diff_y, diff_z):
        try:
            func = self._drill.extend_shape
        except ValueError:
            return
        func(diff_x, diff_y, diff_z)

    def reset_drill(self):
        try:
            func = self._drill.reset_shape
        except ValueError:
            return
        func()

    def set_drill_position(self, position):
        if self._drill:
            position = (position[0] + self._drill_offset[0], position[1] + self._drill_offset[1], position[2] + self._drill_offset[2])
            self._drill.setPosition(position)

    def _get_rays_for_geom(self, geom):
        """ TODO: this is necessary due to a bug in the trimesh collision
        detection code of ODE v0.11.1. Remove this as soon as the code is fixed.
        http://sourceforge.net/tracker/index.php?func=detail&aid=2973876&group_id=24884&atid=382799
        """
        minz, maxz = geom.getAABB()[-2:]
        currx, curry, currz = geom.getPosition()
        ray = ode.GeomRay(self._space, maxz-minz)
        ray.set((currx, curry, maxz), (0.0, 0.0, -1.0))
        return [ray]

    def check_collision(self):
        # get all drill shapes
        try:
            drill_shapes = self._drill.children[:]
        except AttributeError:
            drill_shapes = []
        drill_shapes.append(self._drill)
        # add a ray to each shape
        collision_shapes = []
        for drill_shape in drill_shapes:
            collision_shapes.extend(self._get_rays_for_geom(drill_shape))
            collision_shapes.append(drill_shape)
        # go through all obstacles and check for collisions with a drill shape
        for body in self._obstacles:
            for drill_shape in collision_shapes:
                if ode.collide(drill_shape, body):
                    return True
        return False

    def get_space(self):
        return self._space
