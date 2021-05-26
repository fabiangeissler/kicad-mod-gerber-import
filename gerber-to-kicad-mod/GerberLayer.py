'''
Created on Feb 3, 2021

@author: fgeissler
'''

import gerber
import ezdxf
import os

import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff

import KicadModTree as kmt

from math import sqrt, atan2, pi, inf

from GerberNet import GerberNet

class GerberLayer(object):
    '''
    GerberLayer class contains the geometric primitives of one gerber layer.
    '''
    
    def __init__(self, id='F.Cu', arc_segments = 16, tolerance = 1e-6, color = '#20A020', filename = None):
        '''
        Initialize the layer using a gerber file.
        '''
        self.arc_segments = arc_segments
        self.tolerance = tolerance
        self.color = color
        self.id = id
        
        if(filename != None):
            # Get file extension
            _, ext = os.path.splitext(filename)
            
            if(ext == ".dxf"):
                # DXF file
                dxfdoc = ezdxf.readfile(filename)
                unit = dxfdoc.units
                
                convf = ezdxf.units.conversion_factor(unit, ezdxf.units.MM)
                
                self.nets = []
                
                for e in dxfdoc.modelspace():
                    if e.dxftype() == 'POLYLINE':
                        points = [[p.x * convf, p.y * convf] for p in e.points()]
                        poly = geo.Polygon(points)
                        
                        self.nets.append(GerberNet(poly))
                        
            else: 
                # Probably Gerber file (can have a lot of extensions)
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
        Load primitives from gerber file and convert to layer nets
        '''
        self.nets = []
        
        for p in gbr.primitives:
            if type(p) == gerber.primitives.Region:
                self.nets = self.nets + self._loadFileRegion(p)
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
    
    def getColor(self):
        return self.color
    
    def setColor(self, c):
        self.color = c
        
    def getID(self):
        return self.id
    
    def getMultiPolygon(self):
        '''
        Create a multi polygon object from all nets
        '''
        polys = []
        
        for p in self.nets:
            polys.append(p.getPolygon())
            
        return geo.MultiPolygon(polys)
    
    def _cleanupLayer(self):
        '''
        Merge all overlapping and touching polygons to nets, remove all pads. The corrected polygons are oriented counter-clockwise.
        Must be performed after loading a file to assemble the nets.
        '''
        # Union all touching polygons
        union = sop.unary_union(self.getMultiPolygon())
        
        if union.geom_type == 'MultiPolygon':
            # Orient polygons
            self.nets = [GerberNet(geo.polygon.orient(poly)) for poly in union]
        elif union.geom_type == 'Polygon':
            # Orient polygon
            self.nets = [GerberNet(geo.polygon.orient(union))]
    
    def boundingBox(self):
        '''
        Return bounding box of the layer.
        (xmin, ymin, xmax, ymax)
        '''
        mp = self.getMultiPolygon()
        
        return mp.bounds # (xmin, ymin, xmax, ymax)
    
    def getNets(self):
        return self.nets
    
    def closestNet(self, x, y):
        '''
        Find closest net to coordinates.
        Return tuple (net, dist)
        '''
        mindist = inf
        cnet = None
            
        pt = geo.Point(x, y)
            
        for n in self.nets:
            dist = n.getPolygon().distance(pt)
            
            # find closest net
            if(dist < mindist):
                cnet = n
                mindist = dist
                
        if cnet == None:
            print('WARN: No nets in layer!')
        else:
            return (cnet, mindist)
    
    def appendKicadLayer(self, kicad_mod, mod_layer='F.Cu', offset_x = 0, offset_y = 0, startpad=1):
        '''
        Write the layer to a kicad_mod object from the KicadModTree.
        '''
        n = startpad
        
        # iterate closed polygons
        for net in self.nets:
            if len(net.getPads()) == 0:
                # no pad = poly primitive        
                map = geo.mapping(net.getPolygon())
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x + offset_x, -y - offset_y])
                
                kicad_mod.append(kmt.Polygon(nodes=coords, layer=mod_layer, width=0))
                
            else:
                pads = net.getPads()
                # first pad is anchor
                anch = pads[0]
                
                # center point
                (pxmin, pymin, pxmax, pymax) = anch.bounds
                px = (pxmin + pxmax) / 2
                py = (pymin + pymax) / 2
                
                # size and rotation
                x1, y1 = anch.boundary.coords[0]
                x2, y2 = anch.boundary.coords[1]
                x3, y3 = anch.boundary.coords[2]
                w = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                h = sqrt((x2 - x3) ** 2 + (y2 - y3) ** 2)
                rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                
                # set pad rotation and transform polygon accordingly
                rot_poly = aff.rotate(net.getPolygon(), -rot, (px, py))
                
                # poly primitive        
                map = geo.mapping(rot_poly)
                coords = []
                
                for x, y in map['coordinates'][0]:
                    coords.append([x - px, -(y - py)])
                
                kipoly = kmt.Polygon(nodes=coords)
                
                # create pad
                kicad_mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_CUSTOM, layers = [mod_layer], 
                                   at=[px + offset_x, -(py + offset_y)], size=[w, h], rotation=rot, primitives=[kipoly], anchor_shape=kmt.Pad.SHAPE_RECT))
                
                # other pads are simple squares
                for i in range(1, len(pads)):
                    # center point
                    (pxmin, pymin, pxmax, pymax) = pads[i].bounds
                    px = (pxmin + pxmax) / 2 + offset_x
                    py = -((pymin + pymax) / 2 + offset_y)
                    
                    # size and rotation
                    x1, y1 = pads[i].boundary.coords[0]
                    x2, y2 = pads[i].boundary.coords[1]
                    x3, y3 = pads[i].boundary.coords[2]
                    w = sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                    h = sqrt((x2 - x3) ** 2 + (y2 - y3) ** 2)
                    rot = atan2((y1 - y2), (x1 - x2)) / pi * 180
                    
                    kicad_mod.append(kmt.Pad(number = n, type=kmt.Pad.TYPE_SMT, shape = kmt.Pad.SHAPE_RECT, layers = [mod_layer], 
                                       at=[px, py], size=[w, h], rotation=rot))
                
                # increase pad number
                n = n + 1
                
        return n
        