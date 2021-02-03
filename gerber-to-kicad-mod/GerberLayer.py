'''
Created on Feb 3, 2021

@author: fgeissler
'''

import gerber

import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff

import KicadModTree as kmt

from math import sqrt, atan2, pi

from GerberNet import GerberNet

class GerberLayer(object):
    '''
    GerberLayer class contains the geometric primitives of one gerber layer.
    '''
    
    def __init__(self, arc_segments = 16, tolerance = 1e-6, filename = None):
        '''
        Initialize the layer using a gerber file.
        '''
        self.arc_segments = arc_segments
        self.tolerance = tolerance
        
        if(filename != None):
            # Parse gerber file
            gbr = gerber.read(filename)
            # Convert to metric units
            gbr.to_metric()
            # Load primitives from file
            self._loadFilePrimitives(gbr)  
            # Cleanup
            self._cleanupLayer()  
        
    def _loadFilePrimitives(self, gbr):
        '''
        Load primitives from gerber file and convert to layer primitives
        '''
        self.primitives = []
        
        for p in gbr.primitives:
            if type(p) == gerber.primitives.Region:
                self.primitives = self.primitives + self._loadFileRegion(p)
            else:
                print('Unsupported Primitive Type:', type(p))
                continue

    def _loadFileRegion(self, reg):
        '''
        Load region from file and generte primitive polygon
        '''
        lines = []
        
        for p in reg.primitives:
            # Check if type supported
            if type(p) == gerber.primitives.Line:
                lines.append((p.start, p.end))
            else:
                print('Unsupported Primitive Type:', type(p))
                continue
            
        return [GerberNet(poly) for poly in sop.polygonize(lines)]
    
    def _getMultiPolygon(self):
        '''
        Create a multi polygon object from all primitives
        '''
        polys = []
        
        for p in self.primitives:
            polys.append(p.getPolygon())
            
        return geo.MultiPolygon(polys)
    
    def _cleanupLayer(self):
        '''
        Merge all overlapping and touching polygons, remove all pads. The corrected polygons are oriented counter-clockwise.
        '''
        # Union all touching polygons
        union = sop.unary_union(self._getMultiPolygon())
        # Orient polygons
        self.primitives = [GerberNet(geo.polygon.orient(poly)) for poly in union]
    
    def boundingBox(self):
        '''
        Return bounding box of the layer.
        (xmin, ymin, xmax, ymax)
        '''
        mp = self._getMultiPolygon()
        
        return mp.bounds # (xmin, ymin, xmax, ymax)
    
    def appendKicadLayer(self, kicad_mod, mod_layer='F.Cu', offset_x = 0, offset_y = 0):
        '''
        Write the layer to a kicad_mod object from the KicadModTree.
        '''
        n = 1
        
        # iterate closed polygons
        for poly in self.closedPolygons:
            # find pads
            pads = []
            
            for p in self.pads:
                if(p.distance(poly) < self.tolerance):
                    pads.append(p)
                    
            if len(pads) == 0:
                # no pad = poly primitive        
                map = geo.mapping(poly)
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x + offset_x, -y - offset_y])
                
                kicad_mod.append(kmt.Polygon(nodes=coords, layer=mod_layer, width=0))
                
            else:
                # first pad is anchor
                anch = pads[0]
                
                # center point
                (pxmin, pymin, pxmax, pymax) = anch.bounds
                px = (pxmin + pxmax) / 2
                py = (pymin + pymax) / 2
                
                # size and rotation
                x1, y1 = anch.boundary.coords[0]
                x2, y2 = anch.boundary.coords[1]
                l = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                
                # set pad rotation and transform polygon accordingly
                rot_poly = aff.rotate(poly, -rot, (px, py))
                
                # poly primitive        
                map = geo.mapping(rot_poly)
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x - px, -(y - py)])
                
                kipoly = kmt.Polygon(nodes=coords)
                
                # create pad
                kicad_mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_CUSTOM, layers = [mod_layer], 
                                   at=[px + offset_x, -(py + offset_y)], size=[l, l], rotation=rot, primitives=[kipoly], anchor_shape=kmt.Pad.SHAPE_RECT))
                
                # other pads are simple squares
                for i in range(1, len(pads)):
                    # center point
                    (pxmin, pymin, pxmax, pymax) = pads[i].bounds
                    px = (pxmin + pxmax) / 2 + offset_x
                    py = -((pymin + pymax) / 2 + offset_y)
                    
                    # size and rotation
                    x1, y1 = pads[i].boundary.coords[0]
                    x2, y2 = pads[i].boundary.coords[1]
                    l = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                    rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                    
                    kicad_mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_RECT, layers = [mod_layer], 
                                       at=[px, py], size=[l, l], rotation=rot))
                
                # increase pad number
                n = n + 1
        