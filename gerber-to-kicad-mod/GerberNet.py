'''
Created on Feb 3, 2021

@author: fgeissler
'''

import shapely.ops as sop
import shapely.geometry as geo
import shapely.affinity as aff
from math import inf

class GerberNet(object):
    '''
    Closed gerber polygon structure containing one connected polygon net and associated pads
    '''

    def __init__(self, polygon = None, pads = []):
        '''
        Constructor
        '''
        self.polygon = polygon
        self.pads = pads
        
    def getPolygon(self):
        return self.polygon
    
    def getPads(self):
        return self.pads
    
    def createRectPad(self, x, y, location='outside', ratio=0.5):
        '''
        Create rectangular pad connected to net from closest boundary line. 
        location can be 'inside', 'outside' or 'center'.
        ratio is the pad width/length ratio, where length is the length of the line the pad is created on.
        '''
        boundary = self.polygon.boundary
        mindist = inf
        cline = None
            
        pt = geo.Point(x, y)
            
        for i in range(len(boundary.coords) - 1):
            line = geo.LineString([boundary.coords[i], boundary.coords[i + 1]])
            dist = line.distance(pt)
            
            # find closest line
            if(dist < mindist):
                cline = line
                mindist = dist
        
        # generate pad
        x1, y1 = cline.coords[0]
        x2, y2 = cline.coords[1]
        dx = (x2 - x1)*ratio
        dy = (y2 - y1)*ratio
            
        if location == 'outside':
            poly = geo.Polygon([(x2,y2), (x1,y1), (x1+dy, y1-dx), (x2+dy,y2-dx)])
        elif location == 'inside':
            poly = geo.Polygon([(x1,y1), (x2,y2), (x2-dy,y2+dx), (x1-dy, y1+dx)])
        elif location == 'center':
            poly = geo.Polygon([(x1+dy/2,y1-dx/2), (x2+dy/2,y2-dx/2), (x2-dy/2,y2+dx/2), (x1-dy/2, y1+dx/2)])
        else:
            print('WARN: undefined pad location (', location, ')')
        