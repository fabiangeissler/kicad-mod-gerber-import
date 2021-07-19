'''
Created on Feb 3, 2021

@author: fgeissler
'''

import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff
from math import inf, sqrt

class GerberNet(object):
    '''
    Closed gerber polygon structure containing one connected polygon net and associated pads
    '''

    def __init__(self, polygon = None, pads = None):
        '''
        Constructor
        '''
        self.polygon = polygon
        
        if pads == None:
            self.pads = []
        else:
            self.pads = pads
        
    def getPolygon(self):
        return self.polygon
    
    def getPads(self):
        return self.pads
    
    def triangulate(self):
        triangles = sop.triangulate(self.polygon)
        
        # remove traingles that are in polygon holes
        return [tri for tri in triangles if tri.within(self.polygon)]

    def generateRectPad(self, edge, shift=1, width=0, height=0.1):
        '''
        Create rectangular pad connected to net from closest boundary line. 
        
        shift moves the pad along the boundary normal direction. 
            A value of 1 moves the pad a half pad height to the outside, 
            making it effectively touch the outer boundary.
        
        width is the pad dimension along the line and 
        
        height is the pad dimension normal to the line.
        
        The latter two parameters may be set to zero for automatic adjust
        
        returns pad poly
        '''
        # coordinates and deltas
        x1, y1 = edge.coords[0]
        x2, y2 = edge.coords[1]
        
        dx = (x2 - x1)
        dy = (y2 - y1)
        llen = sqrt(dx ** 2 + dy ** 2)
        
        # check width and height
        if(width <= 0):
            width = llen
        
        if(height <= 0):
            height = width
        
        # normal vector along the line or pad width
        # direction n_w = (dx, dy) 
        # with length |n_w| = width/2
        nwx = width * dx / llen / 2
        nwy = width * dy / llen / 2
        
        # normal vector perpendicular to the edge line, 
        # along the pad height direction nh = (dy, -dx)
        # with length |n_h| = height/2
        nhx = height * dy / llen / 2
        nhy = -height * dx / llen / 2
        
        # pad center vector c = (cx, cy)
        cx = (x1 + x2) / 2 + nhx * shift
        cy = (y1 + y2) / 2 + nhy * shift

        # c  = (cx,  cy)    center vector
        # nh = (nhx, nhy)   height normal vector
        # nw = (nwx, nwy)   width normal vector
        #
        # pad corners: 
        #    c + nh + nw
        #    c - nh + nw
        #    c - nh - nw
        #    c + nh - nw
        return geo.Polygon([
            (cx + nhx + nwx, cy + nhy + nwy), 
            (cx - nhx + nwx, cy - nhy + nwy), 
            (cx - nhx - nwx, cy - nhy - nwy), 
            (cx + nhx - nwx, cy + nhy - nwy)
        ])
    
    def closestEdge(self, x, y):
        boundary = self.polygon.boundary
        mindist = inf
        cline = None
            
        pt = geo.Point(x, y)
            
        if boundary.geom_type != "MultiLineString":
            boundary = [boundary]
            
        for bound in boundary:
            for i in range(len(bound.coords) - 1):
                line = geo.LineString([bound.coords[i], bound.coords[i + 1]])
                dist = line.distance(pt)
                
                # find closest line
                if(dist < mindist):
                    cline = line
                    mindist = dist
                
        if cline == None:
            print('WARN: No edges in net poly!')
        else:
            return (cline, mindist)
        
    def addPad(self, poly):
        # add pad to pads list
        self.pads.append(poly)
        
        
        