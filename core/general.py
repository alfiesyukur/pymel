"""
The core module contains all of the functions which do not fall under the category of `pymel.core.windows`, `pymel.core.node`, or `ctx`.
"""


import sys, os, re
from getpass import getuser
from socket import gethostname

# to make sure Maya is up
import pymel.mayahook as mayahook

try:
    import maya.cmds as cmds
    import maya.mel as mm
except ImportError:
    pass

import sys, os, re, inspect, warnings, timeit, time
import pymel.util as util
import pymel.factories as _factories
from pymel.factories import queryflag, editflag, createflag, MetaMayaNodeWrapper
#from pymel.api.wrappedtypes import * # wrappedtypes must be imported first
import pymel.api as api
#from pmtypes.ranges import *
from pmtypes.wrappedtypes import *
import pmtypes.path as _path
import pymel.util.nameparse as nameparse


"controls whether functions that return dag nodes use the long name by default"
longNames = False


#-----------------------------------------------
#  Enhanced Commands
#-----------------------------------------------


def about(**kwargs):
    """
Modifications:
    - added apiVersion/api flag to about command for version 8.5 and 8.5sp1
    """
    if kwargs.get('apiVersion', kwargs.get('api',False)):
        try:
            return cmds.about(api=1)
        except TypeError:
            return { 
             '8.5 Service Pack 1': 200701,
             '8.5': 200700,
             }[ cmds.about(version=1)]
             
    return cmds.about(**kwargs)

class Version( util.Singleton ):
    """
    Class for storing apiVersions, which are the best method for comparing versions.
    
    >>> if Version.current > Version.v85:
    >>>     print "The current version is later than Maya 8.5"
    """
    current = about(apiVersion=True)

    v85      = 200700
    v85sp1   = 200701
    v2008    = 200800
#    v2008sp1  = 200806
    v2008ext2 = 200806
    v2009     = 200900
#
#    def isCompatible( self, apiVersion ):
#        return self._current >= apiVersion
          
#-----------------------
#  Object Manipulation
#-----------------------

def select(*args, **kwargs):
    """
Modifications:
    - passing an empty list no longer causes an error. instead, the selection is cleared
    
    """
    
    try:
        cmds.select(*util.stringify(args), **kwargs)
    except TypeError, msg:
        if args == ([],):
            cmds.select(cl=True)
        else:
            raise TypeError, msg
#select.__doc__ = mel.help('select') + select.__doc__

def move(obj, *args, **kwargs):
    """
Modifications:
    - allows any iterable object to be passed as first argument::
    
        move("pSphere1", [0,1,2])
        
NOTE: this command also reorders the argument order to be more intuitive, with the object first
    """
    if len(args) == 1 and util.isIterable(args[0]):
        args = tuple(args[0])
    args = args + (obj,)
    return cmds.move(*args, **kwargs)

def scale(obj, *args, **kwargs):
    """
Modifications:
    - allows any iterable object to be passed as first argument::
    
        scale("pSphere1", [0,1,2])
        
NOTE: this command also reorders the argument order to be more intuitive, with the object first
    """
    if len(args) == 1 and util.isIterable(args[0]):
        args = tuple(args[0])
    args = args + (obj,)
    return cmds.scale(*args, **kwargs)
    
def rotate(obj, *args, **kwargs):
    """
Modifications:
    - allows any iterable object to be passed as first argument::
    
        rotate("pSphere1", [0,1,2])
        
NOTE: this command also reorders the argument order to be more intuitive, with the object first
    """
    if len(args) == 1 and util.isIterable(args[0]):
        args = tuple(args[0])
    args = args + (obj,)
    return cmds.rotate(*args, **kwargs)



#-----------------------
#  Attributes
#-----------------------
        
def connectAttr( source, destination, **kwargs ):
    """
Maya Bug Fix: 
    - even with the 'force' flag enabled, the command would raise an error if the connection already existed. 
    
    """
    if kwargs.get('force', False) or kwargs.get('f', False):    
        try:
            cmds.connectAttr( source, destination, **kwargs )
        except RuntimeError:
            pass
    else:
        cmds.connectAttr( source, destination, **kwargs )

def disconnectAttr( source, destination=None, **kwargs ):
    """
Modifications:
    - If no destination is passed, all inputs and outputs will be disconnected from the attribute
    """
    source = Attribute(source)
    if destination:
        return cmds.disconnectAttr( source, destination, **kwargs )
    else:
        for source, destination in source.outputs( connections=True, plugs=True ):
            cmds.disconnectAttr( source, destination, **kwargs )
            
        for destination, source in source.inputs( connections=True, plugs=True ):
            cmds.disconnectAttr( source, destination, **kwargs )    
        
def getAttr( attr, default=None, **kwargs ):
    """
Maya Bug Fix:
    - maya pointlessly returned vector results as a tuple wrapped in 
        a list ( ex.  '[(1,2,3)]' ). This command unpacks the vector for you.
Modifications:
    - casts double3 datatypes to Vector
    - casts matrix datatypes to Matrix
    - casts vectorArrays from a flat array of floats to an array of Vectors
    - when getting a multi-attr, maya would raise an error, but pymel will return a list of
         values for the multi-attr
    - added a default argument. if the attribute does not exist and this argument is not None, this default value will be returned
    """
    def listToMat( l ):
        return Matrix(
            [     [    l[0], l[1], l[2], l[3]    ],
            [    l[4], l[5], l[6], l[7]    ],
            [    l[8], l[9], l[10], l[11]    ],
            [    l[12], l[13], l[14], l[15] ]    ])
    
    def listToVec( l ):
        vecRes = []
        for i in range( 0, len(res), 3):
            vecRes.append( Vector( res[i:i+3] ) )
        return vecRes

    # stringify fix
    attr = unicode(attr)

    try:
        res = cmds.getAttr( attr, **kwargs)
        
        if isinstance(res, list) and len(res):
            if isinstance(res[0], tuple):
                res = res[0]
                if cmds.getAttr( attr, type=1) == 'double3':
                    return Vector(list(res))
            #elif cmds.getAttr( attr, type=1) == 'matrix':
            #    return listToMat(res)
            else:
                try:
                    return { 
                        'matrix': listToMat,
                        'vectorArray' : listToVec
                        }[cmds.getAttr( attr, type=1)](res)
                except KeyError: pass
        return res
    
    # perhaps it errored because it's a multi attribute
    except RuntimeError, msg:
        try:
            attr = Attribute(attr)
            if attr.isMulti():
                return [attr[i].get() for i in range(attr.size())]
            raise RuntimeError, msg
        except AttributeError, msg:
            if default is not None:
                return default
            else:
                raise AttributeError, msg

    
# getting and setting                    
def setAttr( attr, *args, **kwargs):
    """
Maya Bug Fix:
    - setAttr did not work with type matrix. 
Modifications:
    - No need to set type, this will automatically be determined
    - Adds support for passing a list or tuple as the second argument for datatypes such as double3.
    - When setting stringArray datatype, you no longer need to prefix the list with the number of elements - just pass a list or tuple as with other arrays
    - Added 'force' kwarg, which causes the attribute to be added if it does not exist. 
        - if no type flag is passed, the attribute type is based on type of value being set (if you want a float, be sure to format it as a float, e.g.  3.0 not 3)
        - currently does not support compound attributes
        - currently supported python-to-maya mappings:        
            - float     S{->} double
            - int        S{->} long
            - str        S{->} string
            - bool        S{->} bool
            - Vector    S{->} double3
            - Matrix    S{->} matrix
            - [str]        S{->} stringArray
    """
    datatype = kwargs.get( 'type', kwargs.get( 'typ', None) )
    
    # if there is only one argument we do our special pymel tricks
    if len(args) == 1:
        
        arg = args[0]
        
        # force flag
        force = kwargs.pop('force', kwargs.pop('f', False) )
        
        
        # vector, matrix, and arrays
        if util.isIterable(arg):
                                
            if datatype is None:
                # if we're using force flag and the attribute does not exist
                # we can infer the type from the passed value
                attr = Attribute(attr)
                if force and not attr.exists():
                    
                    try:
                        if isinstance( arg[0], basestring ):
                            datatype = 'stringArray'
                        #elif isinstance( arg[0], int ):
                        #    datatype = 'Int32Array'
                        #elif isinstance( arg[0], float ):
                        #    datatype = 'doubleArray'    
                        elif isinstance( arg[0], list ):
                            datatype = 'vectorArray'
                        elif isinstance( arg, Vector):
                            datatype = 'double3'
                        elif isinstance( arg, Matrix ):
                            datatype = 'matrix'
                        else:
                            raise ValueError, "pymel.core.setAttr: %s is not a supported type for use with the force flag" % type(arg[0])
                                                
                        print "adding", attr, datatype
                        attr.add( dt=datatype ) 
                        kwargs['type'] = datatype
                        
                    # empty array is being passed
                    # if the attribute exists, this is ok
                    except IndexError:
                        raise ValueError, "pymel.core.setAttr: when setting 'force' keyword to create a new array attribute, you must provide an array with at least one element"                      
                    
                    except TypeError:
                        raise ValueError, "pymel.core.setAttr: %s is not a supported type" % type(args)
                    
                    kwargs['type'] = datatype
                
                else:
                    if isinstance( arg, Vector):
                        datatype = 'double3'
                    elif isinstance( arg, Matrix ):
                        datatype = 'matrix'
                    else:        
                        datatype = getAttr( attr, type=1)
                        if not datatype:
                            #print "Getting datatype", attr
                            datatype = addAttr( attr, q=1, dataType=1) #[0] # this is returned as a single element list
                    
                        # set datatype for arrays
                        # we could do this for all, but i'm uncertain that it needs to be 
                        # done and it might cause more problems
                        if datatype.endswith('Array'):
                            kwargs['type'] = datatype
        
            
            # string arrays:
            #    first arg must be the length of the array being set
            # ex:
            #     setAttr('loc.strArray',["first", "second", "third"] )    
            # becomes:
            #     cmds.setAttr('loc.strArray',3,"first", "second", "third",type='stringArray')
            if datatype == 'stringArray':
                args = tuple( [len(arg)] + arg )
            
            # vector arrays:
            #    first arg must be the length of the array being set
            #    empty values are placed between vectors
            # ex:
            #     setAttr('loc.vecArray',[1,2,3],[4,5,6],[7,8,9] )    
            # becomes:
            #     cmds.setAttr('loc.vecArray',3,[1,2,3],"",[4,5,6],"",[7,8,9],type='vectorArray')
            elif datatype == 'vectorArray':            
                arg = list(arg)
                size = len(arg)
                try:
                    tmpArgs = [arg.pop(0)]
                    for filler, real in zip( [""]*(size-1), arg ):
                        tmpArgs.append( filler )
                        tmpArgs.append( real )
                except IndexError:
                    tmpArgs = []
                            
                args = tuple( [size] + tmpArgs )
                #print args

            # others: 
            #    args must be expanded
            # ex:
            #     setAttr('loc.foo',[1,2,3] )    
            # becomes:
            #     cmds.setAttr('loc.foo',1,2,3 )    
            else:
                args = tuple(arg)
                
        # non-iterable types
        else:
            if datatype is None:
                attr = Attribute(attr)    
                if force and not attr.exists(): 
                    if isinstance( arg, basestring ):
                        attr.add( dt='string' )
                        kwargs['type'] = 'string'
                    elif isinstance( arg, int ):
                        attr.add( at='long' ) 
                    elif isinstance( arg, float ):
                        attr.add( at='double' ) 
                    elif isinstance( arg, bool ):
                        attr.add( at='bool' ) 
                    else:
                        raise TypeError, "%s.setAttr: %s is not a supported type for use with the force flag" % ( __name__, type(arg) )
                                        
                elif isinstance(arg,basestring):
                    kwargs['type'] = 'string'

    if datatype == 'matrix':
        cmd = 'setAttr -type "matrix" "%s" %s' % (attr, ' '.join( map( str, args ) ) )
        mm.eval(cmd)
        return 
    
    # stringify fix
    attr = unicode(attr)   

    try:
        cmds.setAttr( attr, *args, **kwargs)
    except TypeError, msg:
        val = kwargs.pop( 'type', kwargs.pop('typ', False) )
        typ = addAttr( attr, q=1, at=1)
        if val == 'string' and typ == 'enum':
            enums = addAttr(attr, q=1, en=1).split(":")
            index = enums.index( args[0] )
            args = ( index, )
            cmds.setAttr( attr, *args, **kwargs)
        else:
            raise TypeError, msg
            
def addAttr( *args, **kwargs ):
    """
Modifications:
    - allow python types to be passed to set -at type
            str        S{->} string
            float     S{->} double
            int        S{->} long
            bool    S{->} bool
            Vector    S{->} double3
    - when querying dataType, the dataType is no longer returned as a list
    """
    at = kwargs.pop('attributeType', kwargs.pop('at', None ))
    if at is not None:
        try: 
            kwargs['at'] = {
                float: 'double',
                int: 'long',
                bool: 'bool',
                Vector: 'double3',
                str: 'string',
                unicode: 'string'
            }[at]
        except KeyError:
            kwargs['at'] = at
    
    # MObject Fix
    args = map(unicode, args) 
    res = cmds.addAttr( *args, **kwargs )
    if kwargs.get( 'q', kwargs.get('query',False) ) and kwargs.get( 'dt', kwargs.get('dataType',False) ):
        res = res[0]
    
    return res

def hasAttr( pyObj, attr ):
    "convenience function for determining if an object has an attribute"
    if not isinstance( pyObj, PyNode ):
        raise TypeError, "hasAttr requires a PyNode instance and a string"
    try:
        pyObj.attr(attr)
        return True
    except AttributeError: pass
    return False

#-----------------------
#  List Functions
#-----------------------
        
def listConnections(*args, **kwargs):
    """
Modifications:
    - returns an empty list when the result is None
    - When 'connections' flag is True, the attribute pairs are returned in a 2D-array::
    
        [['checker1.outColor', 'lambert1.color'], ['checker1.color1', 'fractal1.outColor']]
        
    - added sourceFirst keyword arg. when sourceFirst is true and connections is also true, 
        the paired list of plugs is returned in (source,destination) order instead of (thisnode,othernode) order.
        this puts the pairs in the order that disconnectAttr and connectAttr expect.
    """
    def makePairs(l):
        res = []
        if l is None:
            return res
            
        for i in range(0, len(l),2):
            res.append( ( PyNode(l[i]), PyNode(l[i+1]) )  )
        return res
    
    args = util.stringify(args)   
    
    if kwargs.get('connections', kwargs.get('c', False) ) :    
              
        if kwargs.pop('sourceFirst',False):
            source = kwargs.get('source', kwargs.get('s', True ) )
            dest = kwargs.get('destination', kwargs.get('d', True ) )

            if source:                
                if not dest:
                    return [ (s, d) for d, s in makePairs( cmds.listConnections( *args,  **kwargs ) ) ]
                else:
                    res = []
                    kwargs.pop('destination', None)
                    kwargs['d'] = False                    
                    res = [ (s, d) for d, s in makePairs(cmds.listConnections( *args,  **kwargs )) ]                    

                    kwargs.pop('source', None)
                    kwargs['s'] = False
                    kwargs['d'] = True
                    return makePairs(cmds.listConnections( *args,  **kwargs )) + res
                    
            # if dest passes through to normal method 
            
        return makePairs( cmds.listConnections( *args,  **kwargs ) )

    else:
        return map(PyNode, util.listForNone(cmds.listConnections( *args,  **kwargs )) )

def listHistory( *args, **kwargs ):
    """
Modifications:
    - returns an empty list when the result is None
    - added a much needed 'type' filter
    """
    
    if 'type' in kwargs:
        typ = kwargs.pop('type')
        return filter( lambda x: cmds.nodeType(x) == typ, map( PyNode, cmds.listHistory( *args,  **kwargs ) )  )
    return map(PyNode, util.listForNone(cmds.listHistory( *args,  **kwargs ) ) )

        
def listFuture( *args, **kwargs ):
    """
Modifications:
    - returns an empty list when the result is None
    - added a much needed 'type' filter
    """
    kwargs['future'] = True
    if 'type' in kwargs:
        typ = kwargs.pop('type')
        return filter( lambda x: cmds.nodeType(x) == typ, map( PyNode, cmds.listHistory( *args,  **kwargs ) )  )
    return map(PyNode, util.listForNone(cmds.listHistory( *args,  **kwargs )) )

        
def listRelatives( *args, **kwargs ):
    """
Maya Bug Fix
    - allDescendents and shapes flags did not work in combination
    
Modifications:
    - returns an empty list when the result is None
    - returns wrapped classes
    """
    # Stringify Fix
    args = [ unicode(x) for x in args ]
    if kwargs.get( 'allDescendents', kwargs.get('ad', False) ) and kwargs.pop( 'shapes', kwargs.pop('s', False) ):        
        kwargs['fullPath'] = True
        kwargs.pop('f', None)

        res = cmds.listRelatives( *args, **kwargs)
        if res is None:
            return
        return ls( res, shapes=1)

    if longNames:
        kwargs['fullPath'] = True
        kwargs.pop('f', None)
                
    return map(PyNode, util.listForNone(cmds.listRelatives(*args, **kwargs)))


def ls( *args, **kwargs ):
    """
Modifications:
    - Added new keyword: 'editable' - this will return the inverse set of the readOnly flag. i.e. non-read-only nodes
    """
    if longNames:
        kwargs['long'] = True
        kwargs.pop('l', None)
    
    if kwargs.pop('editable', False):
        allNodes = util.listForNone(cmds.ls(*args, **kwargs))
        kwargs['readOnly'] = True
        kwargs.pop('ro',True)
        roNodes = util.listForNone(cmds.ls(*args, **kwargs))
        
        # faster way?
        return map( PyNode, filter( lambda x: x not in roNodes, allNodes ) )
    
    # this has been removed because the method below
    # is 3x faster because it gets the pymel.core.node type along with the pymel.core.node list
    # unfortunately, it's still about 2x slower than cmds.ls
    #return map(PyNode, util.listForNone(cmds.ls(*args, **kwargs)))
    
    if kwargs.get( 'readOnly', kwargs.get('ro', False) ):
        # when readOnly is provided showType is ignored
        return map(PyNode, util.listForNone(cmds.ls(*args, **kwargs)))
        
    if kwargs.get( 'showType', kwargs.get('st', False) ):
        tmp = util.listForNone(cmds.ls(*args, **kwargs))
        res = []
        for i in range(0,len(tmp),2):
            # res.append( PyNode( tmp[i], tmp[i+1] ) )
            res.append( PyNode( tmp[i] ) )
            res.append( tmp[i+1] )
        return res    
    
    if kwargs.get( 'nodeTypes', kwargs.get('nt', False) ):
        # when readOnly is provided showType is ignored
        return cmds.ls(*args, **kwargs)   
    
#    kwargs['showType'] = True
#    tmp = util.listForNone(cmds.ls(*args, **kwargs))
#    res = []
#    for i in range(0,len(tmp),2):
#        res.append( PyNode( tmp[i], tmp[i+1] ) )
#    
#    return res
    return map(PyNode, util.listForNone(cmds.ls(*args, **kwargs)))
    
    '''
    showType = kwargs.get( 'showType', kwargs.get('st', False) )
    kwargs['showType'] = True
    kwargs.pop('st',None)    
    res = []
    if kwargs.get( 'readOnly', kwargs.get('ro', False) ):
        
        ro = cmds.ls(*args, **kwargs) # showType flag will be ignored
        
        # this was unbelievably slow
        
        kwargs.pop('readOnly',None)
        kwargs.pop('ro',None)
        all = cmds.ls(*args, **kwargs)
        for pymel.core.node in ro:
            try:    
                idx = all.index(pymel.core.node)
                all.pop(idx)
                typ = all.pop(idx+1)
                res.append( PyNode( pymel.core.node, typ ) ) 
                if showType:
                    res.append( typ )
            except ValueError: pass
        return res
    else:
        tmp = util.listForNone(cmds.ls(*args, **kwargs))
        for i in range(0,len(tmp),2):
            typ = tmp[i+1]
            res.append( PyNode( tmp[i],  ) )    
            if showType:
                res.append( typ )
        
        return res
    '''

def listTransforms( *args, **kwargs ):
    """
Modifications:
    - returns wrapped classes
    """

    res = cmds.listRelatives(  cmds.ls(*args, **kwargs), p=1, path=1 )
    return map( PyNode, res ) #, ['transform']*len(res) )


    
#-----------------------
#  Objects
#-----------------------

def nodeType( node, **kwargs ):
    
    # still don't know how to do inherited via api
    if kwargs.get( 'inherited', kwargs.get( 'i', False) ):
        return cmds.nodeType( unicode(node), **kwargs )
        
    obj = None
    objName = None

    if isinstance(arg, DependNode) :
        obj = arg.__apiobject__()
    elif isinstance(arg, Attribute) :
        obj = arg.plugNode().__apiobject__()
    elif isinstance(arg, api.MObject) :
        # TODO : convert MObject attributes to DependNode
        if api.isValidMObjectHandle(api.MObjectHandle(arg)) :
            obj = arg
        else :
            obj = None
    elif isinstance(arg,basestring) :
        #obj = api.toMObject( arg.split('.')[0] )
        # don't spend the extra time converting to MObject
        return cmds.nodeType( node, **kwargs )
    if obj:
        if kwargs.get( 'apiType', kwargs.get( 'api', False) ):
            return obj.apiTypeStr()
        # default
        try:
            return api.MFnDependencyNode( obj ).typeName()
        except RuntimeError: pass
        
def group( *args, **kwargs ):
    """
Modifications
    - if no objects are provided for grouping, the empty flag is automatically set
    """
    if not args and not cmds.ls(sl=1):
        kwargs['empty'] = True
    return Transform( cmds.group( *util.stringify(args), **kwargs) )
    #except RuntimeError, msg:
    #    print msg
    #    if msg == 'Not enough objects or values.':
    #        kwargs['empty'] = True
    #        return Transform( cmds.group(**kwargs) )

def duplicate( *args, **kwargs ):
    """
Modifications:
    - returns wrapped classes
    """
    return map(PyNode, cmds.duplicate( *args, **kwargs ) )

    
def instance( *args, **kwargs ):
    """
Modifications:
    - returns wrapped classes
    """
    return map(PyNode, cmds.instance( *args, **kwargs ) )    

'''        
def attributeInfo( *args, **kwargs ):
    """
Modifications:
    - returns an empty list when the result is None
    - returns wrapped classes
    """
    
    return map(PyNode, util.listForNone(cmds.attributeInfo(*args, **kwargs)))
'''

def rename( obj, newname, **kwargs):
    """
Modifications:
    - if the full path to an object is passed as the new name, the shortname of the object will automatically be used
    """
    # added catch to use object name explicitly when object is a Pymel Node
    if isinstance( newname, PyNode ):
        newname = newname.name()
    if isinstance (obj, PyNode) :
        obj = obj.name()
        
    return PyNode( cmds.rename( obj, newname, **kwargs ) )
    
def createNode( *args, **kwargs):
    return PyNode( cmds.createNode( *args, **kwargs ) )
            
                
def sets( objectSet, **kwargs):
    """
Modifications
    - resolved confusing syntax: operating set is always the first and only arg::
    
        sets( 'blinn1SG', forceElement=['pSphere1', 'pCube1'] )
        sets( 'blinn1SG', flatten=True )
        
    - returns wrapped classes
        
    """
    setSetFlags = [
    'subtract', 'sub',
    'union', 'un',
    'intersection', 'int',    
    'isIntersecting', 'ii',
    'isMember', 'im',    
    'split', 'sp',    
    'noWarnings', 'nw',    
    'addElement', 'add',
    'include', 'in',
    'remove', 'rm',    
    'forceElement', 'fe'
    ]
    setFlags = [
    'copy', 'cp',        
    'clear', 'cl',
    'flatten', 'fl'
    ]
    
    args = (objectSet,)
    
    #     this:
    #        sets('myShadingGroup', forceElement=1)
    #    must be converted to:
    #        sets(forceElement='myShadingGroup')
        
    for flag, value in kwargs.items():    
        if flag in setSetFlags:
            # move arg over to kwarg
            if util.isIterable(value):
                args = tuple(value)
            elif isinstance( value, basestring ):
                args = (value,)
            else:
                args = ()
            kwargs[flag] = objectSet
            break
        elif flag in setFlags:
            kwargs[flag] = args[0]
            args = ()
            
    if kwargs.get( 'query', kwargs.get('q',False) ):
        size = len(kwargs)
        if size == 1 or (size==2 and kwargs.get( 'nodesOnly', kwargs.get('no',False) )  ) :
            return map( PyNode, util.listForNone(cmds.sets( *args, **kwargs )) )
            
    return cmds.sets( *args, **kwargs )
    
    '''
    #try:
    #    elements = elements[0]
    #except:
    #    pass
    
    #print elements
    if kwargs.get('query', kwargs.get( 'q', False)):
        #print "query", kwargs, len(kwargs)
        if len(kwargs) == 1:
            # list of elements
            
            return set( cmds.sets( elements, **kwargs ) or [] )
        # other query
        return cmds.sets( elements, **kwargs )
        
    elif kwargs.get('clear', kwargs.get( 'cl', False)):        
        return cmds.sets( **kwargs )
    
    
    #if isinstance(elements,basestring) and cmds.ls( elements, sets=True):
    #    elements = cmds.sets( elements, q=True )
    
    #print elements, kwargs    
    nonCreationArgs = set([
                'edit', 'e',
                'isIntersecting', 'ii',
                'isMember', 'im',
                'subtract', 'sub',
                'union', 'un',
                'intersection', 'int'])
    if len( nonCreationArgs.intersection( kwargs.keys()) ):
        #print "creation"
        return cmds.sets( *elements, **kwargs )

    # Creation
    #args = _convertListArgs(args)
    #print "creation"
    return ObjectSet(cmds.sets( *elements, **kwargs ))
    '''
'''
def delete(*args, **kwargs):
    """
Modifications:
    - added quiet keyword: the command will not fail on an empty list, and will not print warnings for read-only objects
    """
    if kwargs.pop('quiet',False):
        if len(args) ==1 and util.isIterable(args[0]) and not args[0]:
            return
'''
   
def currentTime( *args, **kwargs ):
    """
Modifications:
    - if no args are provided, the command returns the current time -- the equivalent of::
    
        >>> cmds.currentTime(q=1)
    """
    
    if not args and not kwargs:
        return cmds.currentTime(q=1)
    else:
        return cmds.currentTime(*args, **kwargs)
            
def getClassification( *args ):
    """
Modifications:
    - previously returned a list with a single colon-separated string of classifications. now returns a list of classifications
    """
    return cmds.getClassification(*args)[0].split(':')
    

#--------------------------
# New Commands
#--------------------------

def getCurrentTime():
    """get the current time as a float"""
    return cmds.currentTime(q=1)
    
def setCurrentTime( time ):
    """set the current time """
    return cmds.currentTime(time)

def selected( **kwargs ):
    """ls -sl"""
    kwargs['sl'] = 1
    return ls( **kwargs )


_thisModule = __import__(__name__, globals(), locals(), ['']) # last input must included for sub-modules to be imported correctly

                                
#def spaceLocator(*args, **kwargs):
#    """
#Modifications:
#    - returns a locator instead of a list with a single locator
#    """
#    res = cmds.spaceLocator(**kwargs)
#    try:
#        return Transform(res[0])
#    except:
#        return res
    
def instancer(*args, **kwargs):
    """
Maya Bug Fix:
    - name of newly created instancer was not returned
    """ 
    # instancer does not like PyNode objects
    args = map( unicode, args )   
    if kwargs.get('query', kwargs.get('q',False)):
        return cmds.instancer(*args, **kwargs)
    if kwargs.get('edit', kwargs.get('e',False)):
        cmds.instancer(*args, **kwargs)
        return PyNode( args[0], 'instancer' )
    else:
        instancers = cmds.ls(type='instancer')
        cmds.instancer(*args, **kwargs)
        return PyNode( list( set(cmds.ls(type='instancer')).difference( instancers ) )[0], 'instancer' )


def _getPymelType(arg) :
    """ Get the correct Pymel Type for an object that can be a MObject, PyNode or name of an existing Maya object,
        if no correct type is found returns DependNode by default.
        
        If the name of an existing object is passed, the name and MObject will be returned
        If a valid MObject is passed, the name will be returned as None
        If a PyNode instance is passed, its name and MObject will be returned
        """
        
    def getPymelTypeFromObject(obj):
        fnDepend = api.MFnDependencyNode( obj )      
        mayaType = fnDepend.typeName()
        pymelType = mayaTypeToPyNode( mayaType, DependNode )
        return pymelType
    
    obj = None
    objName = None
    
    passedType = ''
 
  
    #--------------------------   
    # API object testing
    #--------------------------   
    if isinstance(arg, api.MObject) :     
        obj = api.MObjectHandle( arg )
        if api.isValidMObjectHandle( obj ) :
            pymelType = getPymelTypeFromObject( obj.object() )        
        else:
            raise ValueError, "Unable to determine Pymel type: the passed MObject is not valid" 
                      
    elif isinstance(arg, api.MObjectHandle) :      
        obj = arg
        if api.isValidMObjectHandle( obj ) :          
            pymelType = getPymelTypeFromObject( obj.object() )    
        else:
            raise ValueError, "Unable to determine Pymel type: the passed MObjectHandle is not valid" 
        
    elif isinstance(arg, api.MDagPath) :
        obj = arg
        if api.isValidMDagPath( obj ):
            pymelType = getPymelTypeFromObject( obj.node() )    
        else:
            raise ValueError, "Unable to determine Pymel type: the passed MDagPath is not valid"
                               
    elif isinstance(arg, api.MPlug) : 
        obj = arg
        if api.isValidMPlug(arg):
            pymelType = Attribute
        else :
            raise ValueError, "Unable to determine Pymel type: the passed MPlug is not valid" 

    #---------------------------------
    # No Api Object : Virtual PyNode 
    #---------------------------------   
    elif objName :
        # non existing node
        pymelType = DependNode
        if '.' in objName :
            # TODO : some better checking / parsing
            pymelType = Attribute 
    else :
        raise ValueError, "Unable to determine Pymel type for %r" % arg         
    
    return pymelType, obj, objName
#--------------------------
# Object Wrapper Classes
#--------------------------
ProxyUnicode = util.proxyClass( unicode, 'ProxyUnicode', dataFuncName='name', remove=['__getitem__', 'translate']) # 2009 Beta 2.1 has issues with passing classes with __getitem__

class PyNode(ProxyUnicode):
    """ Abstract class that is base for all pymel nodes classes, will try to detect argument type if called directly
        and defer to the correct derived class """
    _name = None              # unicode
    
    _apiobject = None         # for DependNode : api.MObjectHandle
                              # for DagNode    : api.MDagPath
                              # for Attribute  : api.MPlug
                              
    _node = None              # Attribute Only: stores the PyNode for the plug's node
    _apimfn = None
    def __new__(cls, *args, **kwargs):
        """ Catch all creation for PyNode classes, creates correct class depending on type passed.
        
        For nodes:
            MObject
            MObjectHandle
            MDagPath
            string/unicode
            
        For attributes:
            MPlug
            MDagPath, MPlug
            string/unicode
        """
        
        #print cls.__name__, cls
        
        pymelType = None
        obj = None
        name = None
        attrNode = None
        
        if args :
            

            if len(args)>1 :
                # Attribute passed as two args: ( node, attr )
                # valid types:
                #    node : MObject, MObjectHandle, MDagPath
                #    attr : MPlug  (TODO: MObject and MObjectHandle )
                # One very important reason for allowing an attribute to be specified as two args instead of as an MPlug
                # is that the node can be represented as an MDagPath which will differentiate between instances, whereas
                # an MPlug loses this distinction.
                
                attrNode = args[0]
                argObj = args[1]
                if not isinstance( attrNode, DependNode ):
                    attrNode = PyNode( attrNode )
                if isinstance(argObj,basestring) :
                    # convert from string to api objects.
                    res = api.toApiObject( argObj, dagPlugs=False )
                else:
                    res = argObj   
                pymelType, obj, name = _getPymelType( res )
                
            else:
                argObj = args[0]

                if isinstance(argObj,basestring) :
                    # convert from string to api objects.
                    res = api.toApiObject( argObj, dagPlugs=True )
                    # DagNode Plug
                    if isinstance(res, tuple):
                        # Plug or Component
                        attrNode = PyNode(res[0])
                        argObj = res[1]
                    # DependNode Plug
                    elif isinstance(res,api.MPlug):
                        attrNode = PyNode(res.node())
                        argObj = res
                    # Other Object
                    elif res:
                        argObj = res
                    else:
                        raise ValueError, "Object does not exist: " + argObj
                elif isinstance( argObj, Attribute ):
                    attrNode = argObj._node
                    argObj = argObj._apiobject
                    
                pymelType, obj, name = _getPymelType( argObj )
                
            #print pymelType, obj, name, attr
            
            # Virtual (non-existent) objects will be cast to their own virtual type.
            # so, until we make that, we're rejecting them
            assert obj # real objects only
            #assert obj or name
            
        else :
            raise ValueError, 'PyNode expects at least one argument: an object name, MObject, MObjectHandle, MDagPath, or MPlug'
        
        # print "type:", pymelType
        # print "PyNode __new__ : called with obj=%r, cls=%r, on object of type %s" % (obj, cls, pymelType)
        # if an explicit class was given (ie: pyObj=DagNode('pCube1')) just check if actual type is compatible
        # if none was given (ie generic pyObj=PyNode('pCube1')) then use the class corresponding to the type we found
        newcls = None
            
        if cls is not PyNode :
            # a PyNode class was explicitely required, if an existing object was passed to init check that the object type
            # is compatible with the required class, if no existing object was passed, create an empty PyNode of the required class
            # TODO : can add object creation option in the __init__ if desired
            
            #if issubclass(pymelType, cls):
            newcls = cls
        else :
            newcls = pymelType
   
        if newcls :  
            self = super(PyNode, cls).__new__(newcls)
            self._name = name
            if attrNode:
                #print 'ATTR', attr, obj, pymelType
                self._node = attrNode
            self._apiobject = obj
            return self
        else :
            raise TypeError, "Cannot make a %s out of a %r object" % (cls.__name__, pymelType)   

    def __init__(self, *args, **kwargs):
        """this  prevents the api class which is the second base, from being automatically instantiated. This __init__ should
        be overridden on subclasses of PyNode"""
        pass
    
    def __radd__(self, other):
        if isinstance(other, basestring):
            return other.__add__( self.name() )
        else:
            raise TypeError, "cannot concatenate '%s' and '%s' objects" % ( other.__class__.__name__, self.__class__.__name__)
    
    def stripNamespace(self, levels=0):
        """
        Returns the object's name with its namespace removed.  The calling instance is unaffected.
        The optional levels keyword specifies how many levels of cascading namespaces to strip, starting with the topmost (leftmost).
        The default is 0 which will remove all namespaces.
        """
        
        nodes = []
        for x in self.split('|'):
            y = x.split('.')
            z = y[0].split(':')
            if levels:
                y[0] = ':'.join( z[min(len(z)-1,levels):] )
    
            else:
                y[0] = z[-1]
            nodes.append( '.'.join( y ) )
        return self.__class__( '|'.join( nodes) )

    def swapNamespace(self, prefix):
        """Returns the object's name with its current namespace replaced with the provided one.  
        The calling instance is unaffected."""    
        return self.addPrefix( self.stripNamespace(), prefix+':' )
            
    def namespaceList(self):
        """Useful for cascading references.  Returns all of the namespaces of the calling object as a list"""
        return self.lstrip('|').rstrip('|').split('|')[-1].split(':')[:-1]
            
    def namespace(self):
        """Returns the namespace of the object with trailing colon included"""
        return ':'.join(self.namespaceList()) + ':'
        
    def addPrefix(self, prefix):
        """Returns the object's name with a prefix added to the beginning of the name"""
        name = self
        leadingSlash = False
        if name.startswith('|'):
            name = name[1:]
            leadingSlash = True
        name =  '|'.join( map( lambda x: prefix+x, name.split('|') ) ) 
        if leadingSlash:
            name = '|' + name
        return name 
                
                        
#    def attr(self, attr):
#        """access to attribute of a node. returns an instance of the Attribute class for the 
#        given attribute."""
#        return Attribute( '%s.%s' % (self, attr) )

    def exists(self, **kwargs):
        "objExists"
        if self.__apiobject__() :
            return True
        else :
            return False
                 
    objExists = exists
        
    cmds.nodeType = cmds.nodeType

    def select(self, **kwargs):
        forbiddenKeys = ['all', 'allDependencyNodes', 'adn', 'allDagObjects' 'ado', 'clear', 'cl']
        for key in forbiddenKeys:
            if key in kwargs:
                raise TypeError, "'%s' is an inappropriate keyword argument for object-oriented implementation of this command" % key
        # stringify
        return cmds.select( self.name(), **kwargs )    

    def deselect( self ):
        self.select( deselect=1 )
    
    listConnections = listConnections
        
    connections = listConnections

    listHistory = listHistory
        
    history = listHistory

    listFuture = listFuture
                
    future = listFuture

_factories.GenHolder.store(PyNode)
_factories.PyNodeNamesToPyNodes()['PyNode'] = PyNode
_factories.ApiTypeRegister.register('MObject', PyNode, inCast=lambda x: PyNode(x).__apimobject__() )
_factories.ApiTypeRegister.register('MDagPath', PyNode, inCast=lambda x: PyNode(x).__apimdagpath__() )
_factories.ApiTypeRegister.register('MPlug', PyNode, inCast=lambda x: PyNode(x).__apimplug__() )
                    
from animation import listAnimatable as _listAnimatable

from system import namespaceInfo

#-----------------------------------------------
#  Global Settings
#-----------------------------------------------


#-----------------------------------------------
#  Scene Class
#-----------------------------------------------

class Scene(util.Singleton):
    def __getattr__(self, obj):
        return PyNode( obj )

SCENE = Scene()

class ComponentArray(object):
    def __init__(self, name):
        self._name = name
        self._iterIndex = 0
        self._node = self.node()
        
    def __str__(self):
        return self._name
        
    def __repr__(self):
        return "ComponentArray('%s')" % self
    
    #def __len__(self):
    #    return 0
        
    def __iter__(self):
        """iterator for multi-attributes
        
            >>> for attr in SCENE.Nexus1.attrInfo(multi=1)[0]: print attr
            
        """
        return self
                
    def next(self):
        """iterator for multi-attributes
        
            >>> for attr in SCENE.Nexus1.attrInfo(multi=1)[0]: print attr
            
        """
        if self._iterIndex >= len(self):
            raise StopIteration
        else:                        
            new = self[ self._iterIndex ]
            self._iterIndex += 1
            return new
            
    def __getitem__(self, item):
        
        def formatSlice(item):
            step = item.step
            if step is not None:
                return '%s:%s:%s' % ( item.start, item.stop, step) 
            else:
                return '%s:%s' % ( item.start, item.stop ) 
        
        '''    
        if isinstance( item, tuple ):            
            return [ Component('%s[%s]' % (self, formatSlice(x)) ) for x in  item ]
            
        elif isinstance( item, slice ):
            return Component('%s[%s]' % (self, formatSlice(item) ) )

        else:
            return Component('%s[%s]' % (self, item) )
        '''
        if isinstance( item, tuple ):            
            return [ self.returnClass( self._node, formatSlice(x) ) for x in  item ]
            
        elif isinstance( item, slice ):
            return self.returnClass( self._node, formatSlice(item) )

        else:
            return self.returnClass( self._node, item )


    def plugNode(self):
        'plugNode'
        return PyNode( str(self).split('.')[0])
                
    def plugAttr(self):
        """plugAttr"""
        return '.'.join(str(self).split('.')[1:])

    node = plugNode
                
class Component(object):
    def __init__(self, node, item):
        self._item = item
        self._node = node
                
    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, self)
        
    def node(self):
        'plugNode'
        return self._node
    
    def item(self):
        return self._item    
        
    def move( self, *args, **kwargs ):
        return move( self, *args, **kwargs )
    def scale( self, *args, **kwargs ):
        return scale( self, *args, **kwargs )    
    def rotate( self, *args, **kwargs ):
        return rotate( self, *args, **kwargs )

                
class Attribute(PyNode):
    """
    Attributes
    ==========
    
    The Attribute class is your one-stop shop for all attribute related functions. Modifying attributes follows a fairly
    simple pattern:  `setAttr` becomes L{set<Attribute.set>}, `getAttr` becomes L{get<Attribute.get>}, `connectAttr`
    becomes L{connect<Attribute.connect>} and so on.  
    
    Accessing Attributes
    --------------------
    Most of the time, you will access instances of the Attribute class via `DependNode` or one of its subclasses. This example demonstrates
    that the Attribute class like the `DependNode` classes are based on a unicode string, and so when printed will 
    
        >>> s = polySphere()[0]
        >>> if s.visibility.isKeyable() and not s.visibility.isLocked():
        >>>     s.visibility = True
        >>>     s.visibility.lock()
        
        >>> print s.v.type()      # shortnames also work    
        bool
    
    Note that when the attribute is created there is currently no check for whether or not the attribute exists, just as there is 
    no check when creating instances of DependNode classes. This is both for speed and also because it can be useful to get a virtual
    representation of an object or attribute before it exists. 

    Getting Attribute Values
    ------------------------
    To get an attribute, you use the L{'get'<Attribute.get>} method. Keep in mind that, where applicable, the values returned will 
    be cast to pymel classes. This example shows that rotation (along with translation and scale) will be returned as `Vector`.
    
        >>> rot = s.rotate.get()
        >>> print rot
        [0.0, 0.0, 0.0]
        >>> print type(rot) # rotation is returned as a vector class
        <class 'pymel.core.vector.Vector'>

    Setting Attributes Values
    -------------------------
    there are several ways to set attributes in pymel.core.  maybe there's too many....
    
        >>> s.rotate.set([4,5,6])   # you can pass triples as a list
        >>> s.rotate.set(4,5,6)     # or not    
        >>> s.rotate = [4,5,6]      # my personal favorite

    Connecting Attributes
    ---------------------
    Since the Attribute class inherits the builtin string, you can just pass the Attribute to the `connect` method. The string formatting
    is handled for you.
                
        >>> s.rotateX.connect( s.rotateY )
    
    there are also handy operators for L{connect<Attribute.__rshift__>} and L{disconnect<Attribute.__ne__>}

        >>> c = polyCube()[0]        
        >>> s.tx >> c.tx    # connect
        >>> s.tx <> c.tx    # disconnect
            
    Avoiding Clashes between Attributes and Class Methods
    -----------------------------------------------------
    All of the examples so far have shown the shorthand syntax for accessing an attribute. The shorthand syntax has the most readability, 
    but it has the drawaback that if the attribute that you wish to acess has the same name as one of the class methods of the node
    then an error will be raised. There is an alternatives which will avoid this pitfall.
            
    attr Method
    ~~~~~~~~~~~
    The attr method is the safest way the access an attribute, and can even be used to access attributes that conflict with 
    python's own special methods, and which would fail using shorthand syntax. This method is passed a string which
    is the name of the attribute to be accessed. This gives it the added advantage of being capable of recieving attributes which 
    are determine at runtime: 
    
        >>> s.addAttr('__init__')
        >>> s.attr('__init__').set( .5 )
        >>> for axis in ['X', 'Y', 'Z']: s.attr( 'translate' + axis ).lock()    
    """
    attrItemReg = re.compile( '\[(\d+)\]$')
    
    #def __repr__(self):
    #    return "Attribute('%s')" % self
    
    def __apiobject__(self) :
        "Return the default API object (MPlug) for this attribute, if it is valid"
        return self.__apimplug__()
    
    def __apimobject__(self):
        "Return the MObject for this attribute, if it is valid"
        obj = self._apiobject.object()
        if api.isValidMObject( obj ):
            return object
    
    def __apimplug__(self) :
        "Return the MPlug for this attribute, if it is valid"
        # TODO: check validity
        return self._apiobject

    def __apimdagpath__(self) :
        "Return the MDagPath for the node of this attribute, if it is valid"
        try:
            return self.node().__mdagpath__()
        except AttributeError: pass
    
    def __apimfn__(self):
        if self._apimfn:
            return self._apimfn
        else:
            obj = self.__apiobject__().attribute()
            if obj:
                self._apimfn = api.MFnAttribute( obj )
                return self._apimfn
                           
#    def __init__(self, attrName):
#        assert isinstance( api.__apiobject__(), api.MPlug )
        
#        if '.' not in attrName:
#            raise TypeError, "%s: Attributes must include the node and the attribute. e.g. 'nodeName.attributeName' " % self
#        self._name = attrName
#        # TODO : MObject support
#        self.__dict__['_multiattrIndex'] = 0
#        
#    def __getitem__(self, item):
#       #return Attribute('%s[%s]' % (self, item) )
#       return Attribute( self._node, self.__apiobject__().elementByLogicalIndex(item) )
    __getitem__ = _factories.wrapApiMethod( api.MPlug, 'elementByLogicalIndex', '__getitem__' )
    #elementByPhysicalIndex = _factories.wrapApiMethod( api.MPlug, 'elementByPhysicalIndex' )
    
    def attr(self, attr):
        node = self.node()
        attrObj = node.__apimfn__().attribute(attr)
        return Attribute( node, self.__apimplug__().child( attrObj ) )
    
    
    def __getattr__(self, attr):
        return self.attr(attr)
    
    # Added the __call__ so to generate a more appropriate exception when a class method is not found 
    def __call__(self, *args, **kwargs):
        raise TypeError("The object <%s> does not support the '%s' method" % (repr(self.node()), self.plugAttr()))
    
    '''
    def __iter__(self):
        """iterator for multi-attributes
        
            >>> for attr in SCENE.Nexus1.attrInfo(multi=1)[0]: print attr
            
        """
        if self.isMulti():
            return self
        else:
            raise TypeError, "%s is not a multi-attribute and cannot be iterated over" % self
            
    def next(self):
        """iterator for multi-attributes
        
            >>> for attr in SCENE.Nexus1.attrInfo(multi=1)[0]: print attr
            
        """
        if self.__dict__['_multiattrIndex'] >= self.size():
            raise StopIteration
        else:            
            attr = Attribute('%s[%s]' % (self, self.__dict__['_multiattrIndex']) )
            self.__dict__['_multiattrIndex'] += 1
            return attr
    '''        
 
 
    def __repr__(self):
        return u"%s('%s')" % (self.__class__.__name__, self.name())

    def __str__(self):
        return "%s" % self.name()

    def __unicode__(self):
        return u"%s" % self.name()

    def name(self):
        """ Returns the full name of that attribute(plug) """
        obj = self.__apiobject__()
        if obj:
            return self.plugNode().name() + '.' + obj.partialName( False, True, True, False, False, True )
        return self._name
    
    def nodeName(self):
        """ Returns the node name of that attribute(plug) """
        pass
    
    def attributeName(self):
        pass
    
    def attributeNames(self):
        pass


       
    def array(self):
        """
        Returns the array (multi) attribute of the current element
            >>> n = Attribute('lambert1.groupNodes[0]')
            >>> n.array()
            'lambert1.groupNode'
        """
        try:
            return Attribute( self._node, self.__apiobject__().array() )
            #att = Attribute(Attribute.attrItemReg.split( self )[0])
            #if att.isMulti() :
            #    return att
            #else :
            #    raise TypeError, "%s is not a multi attribute" % self
        except:
            raise TypeError, "%s is not a multi attribute" % self


    # TODO : do not list all children elements by default, allow to do 
    #        skinCluster1.weightList.elements() for first level elements weightList[x]
    #        or skinCluster1.weightList.weights.elements() for all weightList[x].weights[y]

    def elements(self):
        return cmds.listAttr(self.array(), multi=True)
        
    
    def plugNode(self):
        'plugNode'
        #return PyNode( str(self).split('.')[0])
        return self._node
                
    def plugAttr(self):
        """plugAttr
        
            >>> SCENE.persp.t.tx.plugAttr()
            't.tx'
        """
        return '.'.join(str(self).split('.')[1:])
    
    def lastPlugAttr(self):
        """
        
            >>> SCENE.persp.t.tx.lastPlugAttr()
            'tx'
        """
        return Attribute.attrItemReg.split( self.name().split('.')[-1] )[0]
        
    node = plugNode
    
    def nodeName( self ):
        'basename'
        return self.plugNode.name()
    
#    def item(self):
#        try: 
#            return int(Attribute.attrItemReg.search(self).group(1))
#        except: return None
        
    item = _factories.wrapApiMethod( api.MPlug, 'logicalIndex', 'item' )
    index = _factories.wrapApiMethod( api.MPlug, 'logicalIndex', 'index' )
    
    def setEnums(self, enumList):
        cmds.addAttr( self, e=1, en=":".join(enumList) )
    
    def getEnums(self):
        return cmds.addAttr( self, q=1, en=1 ).split(':')    
            
    # getting and setting                    
    set = setAttr            
    get = getAttr
    setKey = _factories.functionFactory( cmds.setKeyframe, rename='setKey' )       
    
    
    #----------------------
    # Connections
    #----------------------    
                    
    isConnected = cmds.isConnected
    
            
    #def __irshift__(self, other):
    #    """operator for 'isConnected'
    #        sphere.tx >>= box.tx
    #    """ 
    #    print self, other, cmds.isConnected(self, other)
    #    return cmds.isConnected(self, other)
    

    connect = connectAttr
        
    def __rshift__(self, other):
        """operator for 'connectAttr'
            sphere.tx >> box.tx
        """ 
        return connectAttr( self, other, force=True )
                
    disconnect = disconnectAttr

    def __ne__(self, other):
        """operator for 'disconnectAttr'
            sphere.tx <> box.tx
        """ 
        return cmds.disconnectAttr( self, other )
                
    def inputs(self, **kwargs):
        'listConnections -source 1 -destination 0'
        kwargs['source'] = True
        kwargs.pop('s', None )
        kwargs['destination'] = False
        kwargs.pop('d', None )
        
        return listConnections(self, **kwargs)
    
    def outputs(self, **kwargs):
        'listConnections -source 0 -destination 1'
        kwargs['source'] = False
        kwargs.pop('s', None )
        kwargs['destination'] = True
        kwargs.pop('d', None )
        
        return listConnections(self, **kwargs)
    
    def insertInput(self, node, nodeOutAttr, nodeInAttr ):
        """connect the passed node.outAttr to this attribute and reconnect
        any pre-existing connection into node.inAttr.  if there is no
        pre-existing connection, this method works just like connectAttr. 
        
        for example, for two nodes with the connection::
                
            a.out-->b.in
            
        running this command::
        
            b.insertInput( 'c', 'out', 'in' )
            
        causes the new connection order (assuming 'c' is a node with 'in' and 'out' attributes)::
                
            a.out-->c.in
            c.out-->b.in
        """
        inputs = self.inputs(plugs=1)
        self.connect( node + '.' + nodeOutAttr, force=1 )
        if inputs:
            inputs[0].connect( node + '.' + nodeInAttr )

    #----------------------
    # Modification
    #----------------------
    
    def alias(self, **kwargs):
        """aliasAttr"""
        return cmds.aliasAttr( self, **kwargs )    
                            
    def add( self, **kwargs):    
        kwargs['longName'] = self.plugAttr()
        kwargs.pop('ln', None )
        return addAttr( self.node(), **kwargs )    
                    
    def delete(self):
        """deleteAttr"""
        return cmds.deleteAttr( self )
    
    def remove( self, **kwargs):
        'removeMultiInstance'
        #kwargs['break'] = True
        return cmds.removeMultiInstance( self, **kwargs )
        
    # Edge, Vertex, CV Methods
#    def getTranslation( self, **kwargs ):
#        """xform -translation"""
#        kwargs['translation'] = True
#        kwargs['query'] = True
#        return Vector( cmds.xform( self, **kwargs ) )
        
    #----------------------
    # Info Methods
    #----------------------
    
    def isDirty(self, **kwargs):
        return cmds.isDirty(self, **kwargs)
        
    def affects( self, **kwargs ):
        return map( lambda x: Attribute( '%s.%s' % ( self.node(), x )),
            cmds.affects( self.plugAttr(), self.node()  ) )

    def affected( self, **kwargs ):
        return map( lambda x: Attribute( '%s.%s' % ( self.node(), x )),
            cmds.affects( self.plugAttr(), self.node(), by=True  ))
                
    # getAttr info methods
    def type(self):
        "getAttr -type"
        return cmds.getAttr(self, type=True)
 
            
    def size(self):
        "getAttr -size"
        #return cmds.getAttr(self, size=True)    
        try:
            return self.__apiobject__().numElements()
        except RuntimeError:
            pass
        
#    def isElement(self):
#        """ Is the attribute an element of a multi(array) attribute """
#        #return (Attribute.attrItemReg.search(str(self).split('.')[-1]) is not None)
#        return self.__apiobject__().isElement()
#        
#    def isKeyable(self):
#        "getAttr -keyable"
#        return cmds.getAttr(self, keyable=True)
#
#    def setKeyable(self, state):
#        "setAttr -keyable"
#        return cmds.setAttr(self, keyable=state)
#    
#    def isLocked(self):
#        "getAttr -lock"
#        return cmds.getAttr(self, lock=True)    
#
#    def setLocked(self, state):
#        "setAttr -locked"
#        return cmds.setAttr(self, lock=state)
        
    def lock(self):
        "setAttr -locked 1"
        return self.setLocked(True)
        
    def unlock(self):
        "setAttr -locked 0"
        return self.setLocked(False)
    
#    def isInChannelBox(self):
#        "getAttr -channelBox"
#        return cmds.getAttr(self, channelBox=True)    
#        
#    def showInChannelBox(self, state):
#        "setAttr -channelBox"
#        return cmds.setAttr(self, channelBox=state)  
#            
#    def isCaching(self):
#        "getAttr -caching"
#        return cmds.getAttr(self, caching=True)
#              
#    def setCaching(self, state):
#        "setAttr -caching"
#        return cmds.setAttr(self, caching=state)
#                
    def isSettable(self):
        "getAttr -settable"
        return cmds.getAttr(self, settable=True)
    
    # attributeQuery info methods
    def isHidden(self):
        "attributeQuery -hidden"
        return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), hidden=True)
        
    def isConnectable(self):
        "attributeQuery -connectable"
        return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), connectable=True)    

    
#    def isMulti(self):
#        "attributeQuery -multi"
#        return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), multi=True)    
    
#    isArray = _factories.wrapApiMethod( api.MPlug, 'isArray' )
    isMulti = _factories.wrapApiMethod( api.MPlug, 'isArray', 'isMulti' )
#    isElement = _factories.wrapApiMethod( api.MPlug, 'isElement' )
#    isCompound = _factories.wrapApiMethod( api.MPlug, 'isCompound' )
#    
#    isKeyable = _factories.wrapApiMethod( api.MPlug, 'isKeyable'  )
#    setKeyable = _factories.wrapApiMethod( api.MPlug, 'setKeyable'  )
#    isLocked = _factories.wrapApiMethod( api.MPlug, 'isLocked'  )
#    setLocked = _factories.wrapApiMethod( api.MPlug, 'setLocked'  )
    isCaching = _factories.wrapApiMethod( api.MPlug, 'isCachingFlagSet', 'isCaching'  )
#    setCaching = _factories.wrapApiMethod( api.MPlug, 'setCaching'  )
    isInChannelBox = _factories.wrapApiMethod( api.MPlug, 'isChannelBoxFlagSet', 'isInChannelBox' )
    showInChannelBox = _factories.wrapApiMethod( api.MPlug, 'setChannelBox', 'showInChannelBox' )

    
    
    def exists(self):
        "attributeQuery -exists"
        try:
            return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), exists=True)    
        except TypeError:
            return False
            
    def longName(self):
        "attributeQuery -longName"
        return cmds.attributeQuery( self.lastPlugAttr(), node=self.node(), longName=True)
        
    def shortName(self):
        "attributeQuery -shortName"
        return cmds.attributeQuery( self.lastPlugAttr(), node=self.node(), shortName=True)
            
    def getSoftMin(self):
        """attributeQuery -softMin
            Returns None if softMin does not exist."""
        if cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), softMinExists=True):
            return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), softMin=True)[0]    
            
    def getSoftMax(self):
        """attributeQuery -softMax
            Returns None if softMax does not exist."""
        if cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), softMaxExists=True):
            return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), softMax=True)[0]
    
    def getMin(self):
        """attributeQuery -min
            Returns None if min does not exist."""
        if cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), minExists=True):
            return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), min=True)[0]
            
    def getMax(self):
        """attributeQuery -max
            Returns None if max does not exist."""
        if cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), maxExists=True):
            return cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), max=True)[0]
    
    def getSoftRange(self):
        """attributeQuery -softRange
            returns a two-element list containing softMin and softMax. if the attribute does not have
            a softMin or softMax the corresponding element in the list will be set to None."""
        softRange = []
        softRange.append( self.getSoftMin() )
        softRange.append( self.getSoftMax() )
        return softRange
    
            
    def getRange(self):
        """attributeQuery -range
            returns a two-element list containing min and max. if the attribute does not have
            a softMin or softMax the corresponding element will be set to None."""
        range = []
        range.append( self.getMin() )
        range.append( self.getMax() )
        return range
    
    def setMin(self, newMin):
        self.setRange(newMin, 'default')
        
    def setMax(self, newMax):
        self.setRange('default', newMax)

    def setMin(self, newMin):
        self.setSoftRange(newMin, 'default')
        
    def setSoftMax(self, newMax):
        self.setSoftRange('default', newMax)
                
    def setRange(self, *args):
        """provide a min and max value as a two-element tuple or list, or as two arguments to the
        method. To remove a limit, provide a None value.  for example:
        
            >>> s = polyCube()[0]
            >>> s.addAttr( 'new' )
            >>> s.new.setRange( -2, None ) #sets just the min to -2 and removes the max limit
            >>> s.new.setMax( 3 ) # sets just the max value and leaves the min at its previous default 
            >>> s.new.getRange()
            [-2.0, 3.0 ]
            
        """
        
        self._setRange('hard', *args)
        
    def setSoftRange(self, *args):
        self._setRange('soft', *args)    
        
    def _setRange(self, limitType, *args):
        
        if len(args)==2:
            newMin = args[0]
            newMax = args[1]
        
        if len(args)==1:
            try:
                newMin = args[0][0]
                newMax = args[0][1]
            except:    
                raise TypeError, "Please provide a min and max value as a two-element tuple or list, or as two arguments to the method. To ignore a limit, provide a None value."

                
        # first find out what connections are going into and out of the object
        ins = self.inputs(p=1)
        outs = self.outputs(p=1)

        # get the current value of the attr
        val = self.get()

        # break the connections if they exist
        self.disconnect()

        #now tokenize $objectAttr in order to get it's individual parts
        obj = self.node()
        attr = self.plugAttr()

        # re-create the attribute with the new min/max
        kwargs = {}
        kwargs['at'] = self.type()
        kwargs['ln'] = attr
        
        # MIN
        # if 'default' is passed a value, we retain the current value
        if newMin == 'default':
            currMin = self.getMin()
            currSoftMin = self.getSoftMin()
            if currMin is not None:
                kwargs['min'] = currMin
            elif currSoftMin is not None:
                kwargs['smn'] = currSoftMin    
                
        elif newMin is not None:
            if limitType == 'hard':
                kwargs['min'] = newMin
            else:
                kwargs['smn'] = newMin
                
        # MAX    
        # if 'default' is passed a value, we retain the current value
        if newMax == 'default':
            currMax = self.getMax()
            currSoftMax = self.getSoftMin()
            if currMax is not None:
                kwargs['max'] = currMax
            elif currSoftMax is not None:
                kwargs['smx'] = currSoftMax    
                
        elif newMax is not None:
            if limitType == 'hard':
                kwargs['max'] = newMax
            else:
                kwargs['smx'] = newMax
        
        # delete the attribute
        self.delete()                
        cmds.addAttr( obj, **kwargs )

        # set the value to be what it used to be
        self.set(val);

        # remake the connections
        for conn in ins:
            conn >> self
            
        for conn in outs:
            self >> outs


    def getChildren(self):
        """attributeQuery -listChildren"""
        return map( 
            lambda x: Attribute( self.node() + '.' + x ), 
            util.listForNone( cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), listChildren=True) )
                )


    def getSiblings(self):
        """attributeQuery -listSiblings"""
        return map( 
            lambda x: Attribute( self.node() + '.' + x ), 
            util.listForNone( cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), listSiblings=True) )
                )

        
    def getParent(self):
        """attributeQuery -listParent"""    
        
        if self.count('.') > 1:
            return Attribute('.'.join(self.split('.')[:-1]))
        try:
            return Attribute( self.node() + '.' + cmds.attributeQuery(self.lastPlugAttr(), node=self.node(), listParent=True)[0] )
        except TypeError:
            return None
    
        
'''
class NodeAttrRelay(unicode):
    
    def __getattr__(self, attr):
        if attr.startswith('_'):
            return getAttr( '%s.%s' % (self, attr[1:]) )        
        return getAttr( '%s.%s' % (self, attr) )
    
    def __setattr__(self, attr, val):
        if attr.startswith('_'):
            return setAttr( '%s.%s' % (self, attr[1:]), val )            
        return setAttr( '%s.%s' % (self, attr), val )    
'''

class DependNode( PyNode ):
    __metaclass__ = MetaMayaNodeWrapper
    #-------------------------------
    #    Name Info and Manipulation
    #-------------------------------
#    def __new__(cls,name,create=False):
#        """
#        Provides the ability to create the object when creating a class
#        
#            >>> n = pm.Transform("persp",create=True)
#            >>> n.__repr__()
#            # Result: Transform('persp1')
#        """
#        if create:
#            ntype = uncapitalize(cls.__name__)
#            name = createNode(ntype,n=name,ss=1)
#        return PyNode.__new__(cls,name)

    def __init__(self, *args, **kwargs ):
        self.apicls.__init__(self, self._apiobject.object() )
        
    def _updateName(self) :
        if api.isValidMObjectHandle(self._apiobject) :
            obj = self._apiobject.object()
            depFn = api.MFnDependencyNode(obj)
            self._name = depFn.name()
        return self._name 

    def name(self, update=True) :
        if update or self._name is None:
            return self._updateName()
        else :
            return self._name  
        
    def __apiobject__(self) :
        "get the default API object (MObject) for this node if it is valid"
        return self.__apimobject__()
    
    def __apimobject__(self) :
        "get the MObject for this node if it is valid"
        if api.isValidMObjectHandle(self._apiobject) :
            return self._apiobject.object()
    
    def __apimfn__(self):
        if self._apimfn:
            return self._apimfn
        elif self.apicls:
            obj = self.__apiobject__()
            if obj:
                try:
                    self._apimfn = self.apicls(obj)
                    return self._apimfn
                except KeyError:
                    pass

    """
    def __init__(self, *args, **kwargs) :
        if args :
            arg = args[0]
            if len(args) > 1 :
                comp = args[1]        
            if isinstance(arg, DependNode) :
                self._name = unicode(arg.name())
                self._apiobject = api.MObjectHandle(arg.object())
            elif api.isValidMObject(arg) or api.isValidMObjectHandle(arg) :
                self._apiobject = api.MObjectHandle(arg)
                self._updateName()
            elif isinstance(arg, basestring) :
                obj = api.toMObject (arg)
                if obj :
                    # actual Maya object creation
                    self._apiobject = api.MObjectHandle(obj)
                    self._updateName()
                else :
                    # non existent object
                    self._name = arg 
            else :
                raise TypeError, "don't know how to make a Pymel DependencyNode out of a %s : %r" % (type(arg), arg)  
    """
    def __repr__(self):
        return u"%s('%s')" % (self.__class__.__name__, self.name())

    def __str__(self):
        return "%s" % self.name()

    def __unicode__(self):
        return u"%s" % self.name()

    def __eq__(self, other):
        if isinstance(other,PyNode):
            return self.__apiobject__() == other.__apiobject__()
        else:
            try:
                return self.__apiobject__() == PyNode(other).__apiobject__()
            except (ValueError,TypeError): # could not cast to PyNode
                return False
       
    def __ne__(self, other):
        if isinstance(other,PyNode):
            return self.__apiobject__() != other.__apiobject__()
        else:
            try:
                return self.__apiobject__() != PyNode(other).__apiobject__()
            except (ValueError,TypeError): # could not cast to PyNode
                return False
    
    def __getattr__(self, attr):
        try :
            return super(PyNode, self).__getattr__(attr)
        except AttributeError :
            return self.attr(attr)
        
        #if attr.startswith('__') and attr.endswith('__'):
        #    return super(PyNode, self).__getattr__(attr)
            
        #return Attribute( '%s.%s' % (self, attr) )
        
        #raise AttributeError, 'attribute does not exist %s' % attr

#    def __setattr__(self, attr, val):
#        try :
#            return super(PyNode, self).__setattr__(attr, val)
#        except AttributeError :
#            return setAttr( '%s.%s' % (self, attr), val ) 

    def node(self):
        """for compatibility with Attribute class"""
        return self
    
    def attr(self, attr):
        """access to attribute of a node. returns an instance of the Attribute class for the 
        given attribute."""
        #return Attribute( '%s.%s' % (self, attr) )
        try :
            if '.' in attr or '[' in attr:
                # Compound or Multi Attribute
                # there are a couple of different ways we can proceed: 
                # Option 1: back out to api.toApiObject (via PyNode)
                # return Attribute( self.__apiobject__(), self.name() + '.' + attr )
            
                # Option 2: nameparse.
                # this avoids calling self.name(), which can be slow
                nameTokens = nameparse.getBasicPartList( 'dummy.' + attr )
                result = self.__apiobject__()
                for token in nameTokens[1:]: # skip the first, bc it's the node, which we already have
                    if isinstance( token, nameparse.MayaName ):
                        if isinstance( result, api.MPlug ):
                            result = result.child( self.apicls.attribute( self, token ) )
                        else:
                            result = self.apicls.findPlug( self, token )                              
#                                # search children for the attribute to simulate  persp.focalLength --> perspShape.focalLength
#                                except TypeError:
#                                    for i in range(fn.childCount()):
#                                        try: result = api.MFnDagNode( fn.child(i) ).findPlug( token )
#                                        except TypeError: pass
#                                        else:break
                    if isinstance( token, nameparse.NameIndex ):
                        result = result.elementByLogicalIndex( token.value )
                return Attribute( self.__apiobject__(), result )
            else:
                return Attribute( self.__apiobject__(), self.apicls.findPlug( self, attr, False ) )
            
        except RuntimeError:
            raise AttributeError, "Maya node %r has no attribute %r" % ( self, attr )
        
        # if attr.startswith('__') and attr.endswith('__'):
        #     return super(PyNode, self).__setattr__(attr, val)        
        # return setAttr( '%s.%s' % (self, attr), val )

#    def attr(self, attr):
#        """access to attribute of a node. returns an instance of the Attribute class for the 
#        given attribute."""
#        #return Attribute( '%s.%s' % (self, attr) )
#        try :
#            return Attribute( self.__apiobject__(), self.__apimfn__().findPlug( attr, False ) )
#        except RuntimeError:
#            raise AttributeError, "Maya node %r has no attribute %r" % ( self, attr )
#        
#        # if attr.startswith('__') and attr.endswith('__'):
#        #     return super(PyNode, self).__setattr__(attr, val)        
#        # return setAttr( '%s.%s' % (self, attr), val )
        
    #--------------------------
    #    Modification
    #--------------------------
#    def isLocked(self):
#        return self.__apimfn__().isLocked()
      
    def lock( self, **kwargs ):
        'lockNode -lock 1'
        #kwargs['lock'] = True
        #kwargs.pop('l',None)
        #return cmds.lockNode( self, **kwargs)
        return self.setLocked( True )
        
    def unlock( self, **kwargs ):
        'lockNode -lock 0'
        #kwargs['lock'] = False
        #kwargs.pop('l',None)
        #return cmds.lockNode( self, **kwargs)
        return self.setLocked( False )

    def cast( self, swapNode, **kwargs):
        """nodeCast"""
        return cmds.nodeCast( self, swapNode, *kwargs )
    
    #rename = rename
    def rename( self, name ):
        # TODO : ensure that name is the shortname of a node. implement ignoreShape flag
        return self.setName( name )
    
    duplicate = duplicate
    
    #--------------------------
    #    Presets
    #--------------------------
    
    def savePreset(self, presetName, custom=None, attributes=[]):
        
        kwargs = {'save':True}
        if attributes:
            kwargs['attributes'] = ' '.join(attributes)
        if custom:
            kwargs['custom'] = custom
            
        return cmds.nodePrest( presetName, **kwargs)
        
    def loadPreset(self, presetName):
        kwargs = {'load':True}
        return cmds.nodePrest( presetName, **kwargs)
        
    def deletePreset(self, presetName):
        kwargs = {'delete':True}
        return cmds.nodePrest( presetName, **kwargs)
        
    def listPresets(self):
        kwargs = {'list':True}
        return cmds.nodePrest( presetName, **kwargs)
            
    #--------------------------
    #    Info
    #--------------------------

#    def type(self, **kwargs):
#        "nodetype"
#        obj = self.object()  
#        if obj :
#            return nodeType(obj)
#        else :     
#            return self.cmds.nodeType(**kwargs)
    type = nodeType
            
    
#    def hasUniqueName(self):
#        return self.__apimfn__().hasUniqueName()   
#
#    def isDefaultNode(self):
#        return self.__apimfn__().isDefaultNode()  
         
    def referenceFile(self):
        """referenceQuery -file
        Return the reference file to which this object belongs.  None if object is not referenced"""
        try:
            return FileReference( cmds.referenceQuery( self, f=1) )
        except:
            None

    isReadOnly = _factories.wrapApiMethod( api.MPlug, 'isFromReferenceFile', 'isReadOnly' )
    isReferenced = _factories.wrapApiMethod( api.MPlug, 'isFromReferenceFile', 'isReferenced' )
    
#    def isReadOnly(self):
#       return (cmds.ls( self, ro=1) and True) or False
#
#                
#    def isReferenced(self):
#        """referenceQuery -isNodeReferenced
#        Return True or False if the node is referenced"""    
#        return cmds.referenceQuery( self, isNodeReferenced=1)
            
#    def classification(self):
#        'getClassification'
#        #return getClassification( self.type() )    
#        return self.__apimfn__().classification( self.type() )
    
    #--------------------------
    #    Connections
    #--------------------------    
    
    def inputs(self, **kwargs):
        'listConnections -source 1 -destination 0'
        kwargs['source'] = True
        kwargs.pop('s', None )
        kwargs['destination'] = False
        kwargs.pop('d', None )
        return listConnections(self, **kwargs)
    
    def outputs(self, **kwargs):
        'listConnections -source 0 -destination 1'
        kwargs['source'] = False
        kwargs.pop('s', None )
        kwargs['destination'] = True
        kwargs.pop('d', None )
        
        return listConnections(self, **kwargs)                            

    def sources(self, **kwargs):
        'listConnections -source 1 -destination 0'
        kwargs['source'] = True
        kwargs.pop('s', None )
        kwargs['destination'] = False
        kwargs.pop('d', None )
        return listConnections(self, **kwargs)
    
    def destinations(self, **kwargs):
        'listConnections -source 0 -destination 1'
        kwargs['source'] = False
        kwargs.pop('s', None )
        kwargs['destination'] = True
        kwargs.pop('d', None )
        
        return listConnections(self, **kwargs)    
        
    def shadingGroups(self):
        """list any shading groups in the future of this object - works for shading nodes, transforms, and shapes """
        return self.future(type='shadingEngine')
        
        
    #--------------------------
    #    Attributes
    #--------------------------        
    def hasAttr( self, attr):
        try : 
            self.attr(attr)
            return True
        except AttributeError:
            return False
                    
    def setAttr( self, attr, *args, **kwargs):
        return setAttr( self.attr(attr), *args, **kwargs )
            
    def getAttr( self, attr, *args, **kwargs ):
        return getAttr( self.attr(attr), *args,  **kwargs )

    def addAttr( self, attr, **kwargs):        
        return addAttr( self.attr(attr), **kwargs )
            
    def connectAttr( self, attr, *args, **kwargs ):
        return cmds.attr(attr).connect( *args, **kwargs )

    def disconnectAttr( self, source, destination=None, **kwargs ):
        if destination:
            return cmds.disconnectAttr( "%s.%s" % (self, source), destination, **kwargs )
        else:
            for destination in self.outputs( plugs=True ):
                cmds.disconnectAttr( "%s.%s" % (self, source), destination, **kwargs )
                    
    listAnimatable = _listAnimatable

    def listAttr( self, **kwargs):
        "listAttr"
        # stringify fix
        return map( lambda x: self.attr(x), util.listForNone(cmds.listAttr(self.name(), **kwargs)))

    def attrInfo( self, **kwargs):
        "attributeInfo"
        # stringify fix
        return map( lambda x: self.attr(x) , util.listForNone(cmds.attributeInfo(self.name(), **kwargs)))
            
    _numPartReg = re.compile('([0-9]+)$')
    
    def stripNum(self):
        """Return the name of the node with trailing numbers stripped off. If no trailing numbers are found
        the name will be returned unchanged."""
        try:
            return DependNode._numPartReg.split(self)[0]
        except:
            return unicode(self)
            
    def extractNum(self):
        """Return the trailing numbers of the node name. If no trailing numbers are found
        an error will be raised."""
        
        try:
            return DependNode._numPartReg.split(self)[1]
        except:
            raise "No trailing numbers to extract on object ", self

    def nextUniqueName(self):
        """Increment the trailing number of the object until a unique name is found"""
        name = self.shortName().nextName()
        while name.exists():
            name = name.nextName()
        return name
                
    def nextName(self):
        """Increment the trailing number of the object by 1"""
        try:
            groups = DependNode._numPartReg.split(self)
            num = groups[1]
            formatStr = '%s%0' + unicode(len(num)) + 'd'            
            return self.__class__(formatStr % ( groups[0], (int(num) + 1) ))
        except:
            raise "could not find trailing numbers to increment"
            
    def prevName(self):
        """Decrement the trailing number of the object by 1"""
        try:
            groups = DependNode._numPartReg.split(self)
            num = groups[1]
            formatStr = '%s%0' + unicode(len(num)) + 'd'            
            return self.__class__(formatStr % ( groups[0], (int(num) - 1) ))
        except:
            raise "could not find trailing numbers to decrement"

class Entity(DependNode):
    __metaclass__ = MetaMayaNodeWrapper
    pass

class DagNode(Entity):
    __metaclass__ = MetaMayaNodeWrapper
    
    def __init__(self, *args, **kwargs ):
        self.apicls.__init__(self, self._apiobject )
        
    def _updateName(self, long=False) :
        #if api.isValidMObjectHandle(self._apiobject) :
            #obj = self._apiobject.object()
            #dagFn = api.MFnDagNode(obj)
            #dagPath = api.MDagPath()
            #dagFn.getPath(dagPath)
        dag = self.__apimdagpath__()
        if dag:
            name = dag.partialPathName()
            if name:
                self._name = name
            if long :
                return dag.fullPathName()

        return self._name                       
            
    def name(self, update=True, long=False) :
        if update or long or self._name is None:
            return self._updateName(long)
        else :
            return self._name
    
    def __apiobject__(self) :
        "get the MDagPath for this object if it is valid"
        return self.__apimdagpath__()
 
    def __apimdagpath__(self) :
        "get the MDagPath for this object if it is valid"
        if api.isValidMDagPath(self._apiobject) :
            return self._apiobject
            
    def __apimobject__(self) :
        "get the MObject for this object if it is valid"
        return self.__apimdagpath__().node()

    def __apimfn__(self):
        if self._apimfn:
            return self._apimfn
        elif self.apicls:
            obj = self._apiobject
            if api.isValidMDagPath(obj):
                try:
                    self._apimfn = self.apicls(obj)
                    return self._apimfn
                except KeyError:
                    pass
                        
#    def __init__(self, *args, **kwargs):
#        if self._apiobject:
#            if isinstance(self._apiobject, api.MObjectHandle):
#                dagPath = api.MDagPath()
#                api.MDagPath.getAPathTo( self._apiobject.object(), dagPath )
#                self._apiobject = dagPath
#        
#            assert api.isValidMDagPath( self._apiobject )
            
    """
    def __init__(self, *args, **kwargs) :
        if args :
            arg = args[0]
            if len(args) > 1 :
                comp = args[1]
            if isinstance(arg, DagNode) :
                self._name = unicode(arg.name())
                self._apiobject = api.MObjectHandle(arg.object())
            elif api.isValidMObject(arg) or api.isValidMObjectHandle(arg) :
                objHandle = api.MObjectHandle(arg)
                obj = objHandle.object() 
                if api.isValidMDagNode(obj) :
                    self._apiobject = objHandle
                    self._updateName()
                else :
                    raise TypeError, "%r might be a dependencyNode, but not a dagNode" % arg              
            elif isinstance(arg, basestring) :
                obj = api.toMObject (arg)
                if obj :
                    # creation for existing object
                    if api.isValidMDagNode (obj):
                        self._apiobject = api.MObjectHandle(obj)
                        self._updateName()
                    else :
                        raise TypeError, "%r might be a dependencyNode, but not a dagNode" % arg 
                else :
                    # creation for inexistent object 
                    self._name = arg
            else :
                raise TypeError, "don't know how to make a DagNode out of a %s : %r" % (type(arg), arg)  
       """   

            
    #--------------------------
    #    DagNode Path Info
    #--------------------------    
    def root(self):
        'rootOf'
        return DagNode( '|' + self.longName()[1:].split('|')[0] )

#    def hasParent(self, parent ):
#        try:
#            return self.__apimfn__().hasParent( parent.__apiobject__() )
#        except AttributeError:
#            obj = api.toMObject(parent)
#            if obj:
#               return self.__apimfn__().hasParent( obj )
#          
#    def hasChild(self, child ):
#        try:
#            return self.__apimfn__().hasChild( child.__apiobject__() )
#        except AttributeError:
#            obj = api.toMObject(child)
#            if obj:
#               return self.__apimfn__().hasChild( obj )
#    
#    def isParentOf( self, parent ):
#        try:
#            return self.__apimfn__().isParentOf( parent.__apiobject__() )
#        except AttributeError:
#            obj = api.toMObject(parent)
#            if obj:
#               return self.__apimfn__().isParentOf( obj )
#    
#    def isChildOf( self, child ):
#        try:
#            return self.__apimfn__().isChildOf( child.__apiobject__() )
#        except AttributeError:
#            obj = api.toMObject(child)
#            if obj:
#               return self.__apimfn__().isChildOf( obj )

    
    def getAllInstances(self):
        d = api.MDagPathArray()
        self.__apimfn__().getAllPaths(d)
        #result = [ PyNode(d[i]) for i in range(d.length()) ]
        #print [ x.exists() for x in result ]
        result = [ PyNode( api.MDagPath(d[i])) for i in range(d.length()) ]
        return result

    def firstParent(self):
        'firstParentOf'
        try:
            return DagNode( '|'.join( self.longName().split('|')[:-1] ) )
        except TypeError:
            return DagNode( '|'.join( self.split('|')[:-1] ) )

    def numChildren(self):
        return self.__apiobject__().childCount()
    
#    def getParent(self, **kwargs):
#        # TODO : print warning regarding removal of kwargs, test speed difference
#        parent = api.MDagPath( self.__apiobject__() )
#        try:
#            parent.pop()
#            return PyNode(parent)
#        except RuntimeError:
#            pass
#
#    def getChildren(self, **kwargs):
#        # TODO : print warning regarding removal of kwargs
#        children = []
#        thisDag = self.__apiobject__()
#        for i in range( thisDag.childCount() ):
#            child = api.MDagPath( thisDag )
#            child.push( thisDag.child(i) )
#            children.append( PyNode(child) )
#        return children
             
    def getParent(self, **kwargs):
        """unlike the firstParent command which determines the parent via string formatting, this 
        command uses the listRelatives command"""
        
        kwargs['parent'] = True
        kwargs.pop('p',None)
        #if longNames:
        kwargs['fullPath'] = True
        kwargs.pop('p',None)
        
        try:
            # stringify
            res = cmds.listRelatives( self.name(), **kwargs)[0]
        except TypeError:
            return None
             
        res = Transform( res )
        if not longNames:
            return res.shortName()
        return res
                    
    def getChildren(self, **kwargs ):
        kwargs['children'] = True
        kwargs.pop('c',None)

        return listRelatives( self, **kwargs)
        
    def getSiblings(self, **kwargs ):
        #pass
        try:
            return [ x for x in self.getParent().getChildren() if x != self]
        except:
            return []
                
    def listRelatives(self, **kwargs ):
        return listRelatives( self, **kwargs)
        
    def longName(self):
        'longNameOf'
        return self.name(long=True)
            
    def shortName( self ):
        'shortNameOf'
        return self.name(long=False)

    def nodeName( self ):
        'basename'
        return self.name().split('|')[-1]

       
    #-------------------------------
    #    DagNode Path Modification
    #------------------------------- 
    
    def setParent( self, *args, **kwargs ):
        'parent'
        return self.__class__( cmds.parent( self, *args, **kwargs )[0] )
                
    #instance = instance

    #--------------------------
    #    Shading
    #--------------------------    

    def isDisplaced(self):
        """Returns whether any of this object's shading groups have a displacement shader input"""
        for sg in self.shadingGroups():
            if len( sg.attr('displacementShader').inputs() ):
                return True
        return False

    def setColor( self, color=None ):
        """This command sets the dormant wireframe color of the specified objects to an integer
        representing one of the user defined colors, or, if set to None, to the default class color"""

        kwargs = {}
        if color:
            kwargs['userDefined'] = color
        cmds.color(self, **kwargs)
        
    def makeLive( self, state=True ):
        if not state:
            cmds.makeLive(none=True)
        else:
            cmds.makeLive(self)

class Shape(DagNode):
    __metaclass__ = MetaMayaNodeWrapper
    def getTransform(self): pass    
#class Joint(Transform):
#    pass

        
class Camera(Shape):
    __metaclass__ = MetaMayaNodeWrapper
    def getFov(self):
        aperture = self.horizontalFilmAperture.get()
        fov = (0.5 * aperture) / (self.focalLength.get() * 0.03937)
        fov = 2.0 * atan (fov)
        fov = 57.29578 * fov
        return fov
        
    def setFov(self, fov):
        aperture = self.horizontalFilmAperture.get()
        focal = tan (0.00872665 * fov);
        focal = (0.5 * aperture) / (focal * 0.03937);
        self.focalLength.set(focal)
    
    def getFilmAspect(self):
        return self.horizontalFilmAperture.get()/ self.verticalFilmAperture.get()

    def applyBookmark(self, bookmark):
        kwargs = {}
        kwargs['camera'] = self
        kwargs['edit'] = True
        kwargs['setCamera'] = True
            
        cmds.cameraView( bookmark, **kwargs )
            
    def addBookmark(self, bookmark=None):
        kwargs = {}
        kwargs['camera'] = self
        kwargs['addBookmark'] = True
        if bookmark:
            kwargs['name'] = bookmark
            
        cmds.cameraView( **kwargs )
        
    def removeBookmark(self, bookmark):
        kwargs = {}
        kwargs['camera'] = self
        kwargs['removeBookmark'] = True
        kwargs['name'] = bookmark
            
        cmds.cameraView( **kwargs )
        
    def updateBookmark(self, bookmark):    
        kwargs = {}
        kwargs['camera'] = self
        kwargs['edit'] = True
        kwargs['setView'] = True
            
        cmds.cameraView( bookmark, **kwargs )
        
    def listBookmarks(self):
        return self.bookmarks.inputs()
    
    dolly = _factories.functionFactory( cmds.dolly  )
    roll = _factories.functionFactory( cmds.roll  )
    orbit = _factories.functionFactory( cmds.orbit  )
    track = _factories.functionFactory( cmds.track )
    tumble = _factories.functionFactory( cmds.tumble ) 
    
            
class Transform(DagNode):
    __metaclass__ = MetaMayaNodeWrapper
#    def __getattr__(self, attr):
#        if attr.startswith('__') and attr.endswith('__'):
#            return super(PyNode, self).__getattr__(attr)
#                        
#        at = Attribute( '%s.%s' % (self, attr) )
#        
#        # if the attribute does not exist on this node try the shape node
#        if not at.exists():
#            try:
#                childAttr = getattr( self.getShape(), attr)
#                try:
#                    if childAttr.exists():
#                        return childAttr
#                except AttributeError:
#                    return childAttr
#            except (AttributeError,TypeError):
#                pass
#                    
#        return at
#    
#    def __setattr__(self, attr,val):
#        if attr.startswith('_'):
#            attr = attr[1:]
#                        
#        at = Attribute( '%s.%s' % (self, attr) )
#        
#        # if the attribute does not exist on this node try the shape node
#        if not at.exists():
#            try:
#                childAttr = getattr( self.getShape(), attr )
#                try:
#                    if childAttr.exists():
#                        return childAttr.set(val)
#                except AttributeError:
#                    return childAttr.set(val)
#            except (AttributeError,TypeError):
#                pass
#                    
#        return at.set(val)
            
    """    
    def move( self, *args, **kwargs ):
        return move( self, *args, **kwargs )
    def scale( self, *args, **kwargs ):
        return scale( self, *args, **kwargs )
    def rotate( self, *args, **kwargs ):
        return rotate( self, *args, **kwargs )
    def align( self, *args, **kwargs):
        args = (self,) + args
        cmds.align(self, *args, **kwargs)
    """
    # NOTE : removed this via proxyClass
#    # workaround for conflict with translate method on basestring
#    def _getTranslate(self):
#        return self.__getattr__("translate")
#    def _setTranslate(self, val):
#        return self.__setattr__("translate", val)        
#    translate = property( _getTranslate , _setTranslate )
    
    def hide(self):
        self.visibility.set(0)
        
    def show(self):
        self.visibility.set(1)
                
    def getShape( self, **kwargs ):
        kwargs['shapes'] = True
        try:
            return self.getChildren( **kwargs )[0]            
        except:
            pass
                
    def ungroup( self, **kwargs ):
        return cmds.ungroup( self, **kwargs )
    '''
    @editflag('xform','scale')      
    def setScale( self, val, **kwargs ):
        cmds.xform( self, **kwargs )

    @editflag('xform','rotation')             
    def setRotation( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
        
    @editflag('xform','translation')  
    def setTranslation( self, val, **kwargs ):
        cmds.xform( self, **kwargs )

    @editflag('xform','scalePivot')  
    def setScalePivot( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
        
    @editflag('xform','rotatePivot')         
    def setRotatePivot( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
 
    @editflag('xform','pivots')         
    def setPivots( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
        
    @editflag('xform','rotateAxis')  
    def setRotateAxis( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
        
    @editflag('xform','shear')                                 
    def setShearing( self, val, **kwargs ):
        cmds.xform( self, **kwargs )
    '''
    
    @editflag('xform','rotateAxis')                                
    def setMatrix( self, val, **kwargs ):
        """xform -scale"""
        if isinstance(val, Matrix):
            val = val.toList()
    
        kwargs['matrix'] = val
        cmds.xform( self, **kwargs )

    @queryflag('xform','scale') 
    def getScaleOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )
 
    @queryflag('xform','rotation')        
    def getRotationOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )

    @queryflag('xform','translation') 
    def getTranslationOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )

    @queryflag('xform','scalePivot') 
    def getScalePivotOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )
 
    @queryflag('xform','rotatePivot')        
    def getRotatePivotOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )
 
    @queryflag('xform','pivots') 
    def getPivots( self, **kwargs ):
        res = cmds.xform( self, **kwargs )
        return ( Vector( res[:3] ), Vector( res[3:] )  )
    
    @queryflag('xform','rotateAxis') 
    def getRotateAxis( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )
        
    @queryflag('xform','shear')                          
    def getShearOld( self, **kwargs ):
        return Vector( cmds.xform( self, **kwargs ) )

    @queryflag('xform','matrix')                
    def getMatrix( self, **kwargs ): 
        return Matrix( cmds.xform( self, **kwargs ) )
           
    def getBoundingBox(self, invisible=False):
        """xform -boundingBox and xform-boundingBoxInvisible
        
        returns a tuple with two MVecs: ( bbmin, bbmax )
        """
        kwargs = {'query' : True }    
        if invisible:
            kwargs['boundingBoxInvisible'] = True
        else:
            kwargs['boundingBox'] = True
                    
        res = cmds.xform( self, **kwargs )
        return ( Vector(res[:3]), Vector(res[3:]) )
    
    def getBoundingBoxMin(self, invisible=False):
        return self.getBoundingBox(invisible)[0]
        
    def getBoundingBoxMax(self, invisible=False):
        return self.getBoundingBox(invisible)[1]    
    
    '''        
    def centerPivots(self, **kwargs):
        """xform -centerPivots"""
        kwargs['centerPivots'] = True
        cmds.xform( self, **kwargs )
        
    def zeroTransformPivots(self, **kwargs):
        """xform -zeroTransformPivots"""
        kwargs['zeroTransformPivots'] = True
        cmds.xform( self, **kwargs )        
    '''

class Joint(Transform):
    __metaclass__ = MetaMayaNodeWrapper
    connect = _factories.functionFactory( cmds.connectJoint, rename='connect')
    disconnect = _factories.functionFactory( cmds.disconnectJoint, rename='disconnect')
    insert = _factories.functionFactory( cmds.insertJoint, rename='insert')

class FluidEmitter(Transform):
    __metaclass__ = MetaMayaNodeWrapper
    fluidVoxelInfo = _factories.functionFactory( cmds.fluidVoxelInfo, rename='fluidVoxelInfo')
    loadFluid = _factories.functionFactory( cmds.loadFluid, rename='loadFluid')
    resampleFluid = _factories.functionFactory( cmds.resampleFluid, rename='resampleFluid')
    saveFluid = _factories.functionFactory( cmds.saveFluid, rename='saveFluid')
    setFluidAttr = _factories.functionFactory( cmds.setFluidAttr, rename='setFluidAttr')
    getFluidAttr = _factories.functionFactory( cmds.getFluidAttr, rename='getFluidAttr')
    
class RenderLayer(DependNode):
    def listMembers(self, fullNames=True):
        if fullNames:
            return map( PyNode, util.listForNone( cmds.editRenderLayerMembers( self, q=1, fullNames=True) ) )
        else:
            return util.listForNone( cmds.editRenderLayerMembers( self, q=1, fullNames=False) )
        
    def addMembers(self, members, noRecurse=True):
        cmds.editRenderLayerMembers( self, members, noRecurse=noRecurse )

    def removeMembers(self, members ):
        cmds.editRenderLayerMembers( self, members, remove=True )
 
    def listAdjustments(self):
        return map( PyNode, util.listForNone( cmds.editRenderLayerAdjustment( layer=self, q=1) ) )
      
    def addAdjustments(self, members):
        return cmds.editRenderLayerMembers( self, members, noRecurse=noRecurse )

    def removeAdjustments(self, members ):
        return cmds.editRenderLayerMembers( self, members, remove=True )      
    
    def setCurrent(self):
        cmds.editRenderLayerGlobals( currentRenderLayer=self)    

class DisplayLayer(DependNode):
    def listMembers(self, fullNames=True):
        if fullNames:
            return map( PyNode, util.listForNone( cmds.editDisplayLayerMembers( self, q=1, fullNames=True) ) )
        else:
            return util.listForNone( cmds.editDisplayLayerMembers( self, q=1, fullNames=False) )
        
    def addMembers(self, members, noRecurse=True):
        cmds.editDisplayLayerMembers( self, members, noRecurse=noRecurse )

    def removeMembers(self, members ):
        cmds.editDisplayLayerMembers( self, members, remove=True )
        
    def setCurrent(self):
        cmds.editDisplayLayerMembers( currentDisplayLayer=self)  
    
class Constraint(Transform):
    def setWeight( self, weight, *targetObjects ):
        inFunc = getattr( cmds, self.type() )
        if not targetObjects:
            targetObjects = self.getTargetList() 
        
        constraintObj = self.constraintParentInverseMatrix.inputs()[0]    
        args = list(targetObjects) + [constraintObj]
        return inFunc(  *args, **{'edit':True, 'weight':weight} )
        
    def getWeight( self, *targetObjects ):
        inFunc = getattr( cmds, self.type() )
        if not targetObjects:
            targetObjects = self.getTargetList() 
        
        constraintObj = self.constraintParentInverseMatrix.inputs()[0]    
        args = list(targetObjects) + [constraintObj]
        return inFunc(  *args, **{'query':True, 'weight':True} )

class GeometryShape(DagNode): pass
class DeformableShape(GeometryShape): pass
class ControlPoint(DeformableShape): pass
class SurfaceShape(ControlPoint): pass
class Mesh(SurfaceShape):
    __metaclass__ = MetaMayaNodeWrapper
    """
    Cycle through faces and select those that point up in world space
    
    >>> s = PyNode('pSphere1')
    >>> for face in s.faces:
    >>>     if face.normal.objectToWorld(s).y > 0:
    >>>         print face
    >>>         select( face , add=1)
    
    """
    class FaceArray(ComponentArray):
        def __init__(self, name):
            ComponentArray.__init__(self, name)
            self.returnClass = Mesh.Face
            
        def __len__(self):
            return cmds.polyEvaluate(self.node(), face=True)
    
    class EdgeArray(ComponentArray):
        def __init__(self, name):
            ComponentArray.__init__(self, name)
            self.returnClass = Mesh.Edge
        def __len__(self):
            return cmds.polyEvaluate(self.node(), edge=True)
    
    class VertexArray(ComponentArray):
        def __init__(self, name):
            ComponentArray.__init__(self, name)
            self.returnClass = Mesh.Vertex
            
        def __len__(self):
            return cmds.polyEvaluate(self.node(), vertex=True)
        
    class Face(Component):
        def __str__(self):
            return '%s.f[%s]' % (self._node, self._item)
    
        def getNormal(self):
            return Vector( map( float, cmds.polyInfo( self._node, fn=1 )[self._item].split()[2:] ))        
        normal = property(getNormal)
        
        def toEdges(self):
            return map( self._node.e.__getitem__, cmds.polyInfo( str(self), faceToEdge=1)[0].split()[2:] )        
        edges = property(toEdges)
        
        def toVertices(self):
            return map( self._node.vtx.__getitem__, cmds.polyInfo( str(self), faceToVertex=1)[0].split()[2:] )        
        vertices = property(toVertices)
        
    class Edge(Component):
        def __str__(self):
            return '%s.e[%s]' % (self._node, self._item)
            
        def toFaces(self):
            return map( self._node.e.__getitem__, cmds.polyInfo( str(self), edgeToFace=1)[0].split()[2:] )        
        faces = property(toFaces)
        
    class Vertex(Component):
        def __str__(self):
            return '%s.vtx[%s]' % (self._node, self._item)
            
        def toEdges(self):
            return map( self._node.e.__getitem__, cmds.polyInfo( str(self), vertexToEdge=1)[0].split()[2:] )        
        edges = property(toEdges)
        
        def toFaces(self):
            return map( self._node.e.__getitem__, cmds.polyInfo( str(self), vertexToFace=1)[0].split()[2:] )        
        faces = property(toFaces)
    
    def _getFaceArray(self):
        return Mesh.FaceArray( self + '.f' )    
    f = property(_getFaceArray)
    faces = property(_getFaceArray)
    
    def _getEdgeArray(self):
        return Mesh.EdgeArray( self + '.e' )    
    e = property(_getEdgeArray)
    edges = property(_getEdgeArray)
    
    def _getVertexArray(self):
        return Mesh.VertexArray( self + '.vtx' )    
    vtx = property(_getVertexArray)
    verts = property(_getVertexArray)
            
    def __getattr__(self, attr):
        try :
            return super(PyNode, self).__getattr__(attr)
        except AttributeError :
            at = Attribute( '%s.%s' % (self, attr) )   
            # if the attribute does not exist on this node try the history
            if not at.exists():
                try:
                    childAttr = getattr( self.inMesh.inputs()[0], attr )
                
                    try:
                        if childAttr.exists():
                            return childAttr
                    except AttributeError:
                        return childAttr
                
                except IndexError:
                    pass
                """
                try:    
                    return getattr( self.inMesh.inputs()[0], attr)
                except IndexError:
                    raise AttributeError, "Attribute does not exist: %s" % at
                """
            return at

    def __setattr__(self, attr, val):
        try :
            return super(PyNode, self).__setattr__(attr, val)
        except AttributeError :
            at = Attribute( '%s.%s' % (self, attr) )   
            # if the attribute does not exist on this node try the history
            if not at.exists():
                try:
                    childAttr = getattr( self.inMesh.inputs()[0], attr )
                
                    try:
                        if childAttr.exists():
                            return childAttr.set(val)
                    except AttributeError:
                        return childAttr.set(val)
                
                except IndexError:
                    pass
                """
                try:    
                    return getattr( self.inMesh.inputs()[0], attr)
                except IndexError:
                    raise AttributeError, "Attribute does not exist: %s" % at
                """
            return at.set(val)
                        
    vertexCount = _factories.makeCreateFlagMethod( cmds.polyEvaluate, 'vertex', 'vertexCount' )
    edgeCount = _factories.makeCreateFlagMethod( cmds.polyEvaluate, 'edge', 'edgeCount' )
    faceCount = _factories.makeCreateFlagMethod( cmds.polyEvaluate,  'face', 'faceCount' )
    uvcoordCount = _factories.makeCreateFlagMethod( cmds.polyEvaluate, 'uvcoord', 'uvcoordCount' )
    triangleCount = _factories.makeCreateFlagMethod( cmds.polyEvaluate, 'triangle', 'triangleCount' )
    #area = _factories.makeCreateFlagMethod( 'area', cmds.polyEvaluate, 'area' )
    
    #def area(self):
    #    return cmds.polyEvaluate(self, area=True)
        
    #def worldArea(self):
    #    return cmds.polyEvaluate(self, worldArea=True)
    
    '''
    def _listComponent( self, compType, num ):
        for i in range(0, num):
             yield Attribute( '%s.vtx[%s]' % (self, i) )
    
    def verts(self):
        return self._listComponent( 'vtx', self.numVerts() )
    '''
                    

class Subdiv(SurfaceShape):
    __metaclass__ = MetaMayaNodeWrapper
    def getTweakedVerts(self, **kwargs):
        return cmds.querySubdiv( action=1, **kwargs )
        
    def getSharpenedVerts(self, **kwargs):
        return cmds.querySubdiv( action=2, **kwargs )
        
    def getSharpenedEdges(self, **kwargs):
        return cmds.querySubdiv( action=3, **kwargs )
        
    def getEdges(self, **kwargs):
        return cmds.querySubdiv( action=4, **kwargs )
                
    def cleanTopology(self):
        cmds.subdCleanTopology(self)
    
class Particle(DeformableShape):
    __metaclass__ = MetaMayaNodeWrapper
    
    class PointArray(ComponentArray):
        def __init__(self, name):
            ComponentArray.__init__(self, name)
            self.returnClass = Particle.Point

        def __len__(self):
            return cmds.particle(self.node(), q=1,count=1)        
        
    class Point(Component):
        def __str__(self):
            return '%s.pt[%s]' % (self._node, self._item)
        def __getattr__(self, attr):
            return cmds.particle( self._node, q=1, attribute=attr, order=self._item)
            
    
    def _getPointArray(self):
        return Particle.PointArray( self + '.pt' )    
    pt = property(_getPointArray)
    points = property(_getPointArray)
    
    def pointCount(self):
        return cmds.particle( self, q=1,count=1)
    num = pointCount
    
class ObjectSet(Entity):
    """
    this is currently a work in progress.  my goal is to create a class for doing set operations in maya that is
    compatiable with python's powerful built-in set class.  
    
    each operand has its own method equivalent. 
    
    these will return the results of the operation as python sets containing lists of pymel node classes::
    
        s&t     s.intersection(t)
        s|t     s.union(t)
        s^t     s.symmetric_difference(t)
        s-t     s.difference(t)
    
    the following will alter the contents of the maya set::
        
        s&=t    s.intersection_update(t)
        s|=t    s.update(t)
        s^=t    s.symmetric_difference_update(t)
        s-=t    s.difference_update(t)        
    
    create some sets
    
        >>> sphere = polySphere()
        >>> cube = polyCube()
        >>> s = sets( cube )
        >>> s.update( ls( type='camera') )
        >>> t = sets( sphere )
        >>> t.add( 'perspShape' )

        >>> print s|t  # union

        >>> u = sets( s&t ) # intersection
        >>> print u.elements(), s.elements()
        >>> if u < s: print "%s is a sub-set of %s" % (u, s)
        
    place a set inside another, take1
    
        >>> # like python's built-in set, the add command expects a single element
        >>> s.add( t )

    place a set inside another, take2
    
        >>> # like python's built-in set, the update command expects a set or a list
        >>> t.update([u])

        >>> # put the sets back where they were
        >>> s.remove(t)
        >>> t.remove(u)

    now put the **contents** of a set into another set
    
        >>> t.update(u)

    mixed operation between pymel.core.ObjectSet and built-in set
        
        >>> v = set(['polyCube3', 'pSphere3'])
        >>> print s.intersection(v)
        >>> print v.intersection(s)  # not supported yet
        >>> u.clear()

        >>> delete( s )
        >>> delete( t )
        >>> delete( u )
    """
            
    def _elements(self):
        """ used internally to get a list of elements without casting to node classes"""
        return sets( self, q=True)
    #-----------------------
    # Maya Methods
    #-----------------------
    def elements(self):
        return set( map( PyNode, self._elements() ) )

    def subtract(self, set2):
        return sets( self, subtract=set2 )
    
    def flatten(self):
        return sets( flatten=self )
    
#    #-----------------------
#    # Python ObjectSet Methods
#    #-----------------------
#    def __and__(self, s):
#        return self.intersection(s)
#
#    def __iand__(self, s):
#        return self.intersection_update(s)
#                    
#    def __contains__(self, element):
#        return element in self._elements()
#
#    #def __eq__(self, s):
#    #    return s == self._elements()
#
#    #def __ne__(self, s):
#    #    return s != self._elements()
#            
#    def __or__(self, s):
#        return self.union(s)
#
#    def __ior__(self, s):
#        return self.update(s)
#                                    
#    def __len__(self, s):
#        return len(self._elements())
#
#    def __lt__(self, s):
#        return self.issubset(s)
#
#    def __gt__(self, s):
#        return self.issuperset(s)
#                    
#    def __sub__(self, s):
#        return self.difference(s)
#
#    def __isub__(self, s):
#        return self.difference_update(s)                        
#
#    def __xor__(self, s):
#        return self.symmetric_difference(s)
        
    def add(self, element):
        return sets( self, add=[element] )
    
    def clear(self):
        return sets( self, clear=True )
    
    def copy(self ):
        return sets( self, copy=True )
    
    def difference(self, elements):
        if isinstance(elements,basestring):
            elements = cmds.sets( elements, q=True)
        return list(set(self.elements()).difference(elements))
        
        '''
        if isinstance(s, ObjectSet) or isinstance(s, str):
            return sets( s, subtract=self )
        
        s = sets( s )
        res = sets( s, subtract=self )
        cmds.delete(s)
        return res'''
    
    def difference_update(self, elements ):
        return sets( self, remove=elements)
    
    def discard( self, element ):
        try:
            return self.remove(element)
        except TypeError:
            pass

    def intersection(self, elements):
        if isinstance(elements,basestring):
            elements = cmds.sets( elements, q=True)
        return set(self.elements()).intersection(elements)
    
    def intersection_update(self, elements):
        self.clear()
        sets( self, add=self.intersections(elements) )
            
    def issubset(self, set2):
        return sets( self, isMember=set2)

    def issuperset(self, set2):
        return sets( self, isMember=set2)
            
    def remove( self, element ):
        return sets( self, remove=[element])

    def symmetric_difference(self, elements):
        if isinstance(elements,basestring):
            elements = cmds.sets( elements, q=True)
        return set(self.elements()).symmetric_difference(elements)
            
    def union( self, elements ):
        if isinstance(elements,basestring):
            elements = cmds.sets( elements, q=True)
        return set(self.elements()).union(elements)
    
    def update( self, set2 ):        
        sets( self, forceElement=set2 )
        
        #if isinstance(s, str):
        #    items = ObjectSet(  )
            
        #items = self.union(items)


#def worldToObject(self, obj):
#    return self * node.DependNode(obj).worldInverseMatrix.get()
#
#def worldToCamera(self, camera=None):
#    if camera is None:
#        camera = core.mel.getCurrentCamera()
#    return self * node.DependNode(camera).worldInverseMatrix.get()
#    
#def worldToScreen(self, camera=None):
#    if camera is None:
#        camera = node.Camera(core.mel.getCurrentCamera())
#    else:
#        camera = node.Camera(camera)
#        
#    screen = self.worldToCamera(camera)
#    
#    screen.x = (screen.x/-screen.z) / tan(radians(camera.horizontalFieldOfView/2))/2.0+.5
#    screen.y = (screen.y/-screen.z) / tan(radians(camera.verticalFieldOfView/2))/2.0+.5 
#
#    xres = core.getAttr( 'defaultResolution.width' )
#    yres = core.getAttr( 'defaultResolution.height' )
#    filmApX = camera.horizontalFilmAperture.get()
#    filmApY = camera.verticalFilmAperture.get()
#
#    filmAspect = filmApX/filmApY;
#    resAspect  = xres/yres;
#    ratio = filmAspect/resAspect;
#
#    screen.y = linmap( ((ratio-1)/-2), (1+(ratio-1)/2), screen.y )
#    
#    return screen    
#
#def objectToWorld(self, object):
#    worldMatrix = node.DependNode(object).worldMatrix.get()
#    return self * worldMatrix
#
#def objectToCamera(self, object, camera=None):
#    return self.objectToWorld(object).worldToCamera( camera )
#    
#def objectToScreen(self, object, camera=None):
#    return self.objectToWorld(object).worldToScreen( camera )
#
#        
#def cameraToWorld(self, camera=None):
#    if camera is None:
#        camera = core.mel.getCurrentCamera()
#    return self * node.DependNode(camera).worldMatrix.get()


# create PyNode conversion tables


#_thisModule = __import__(__name__, globals(), locals(), ['']) # last input must included for sub-modules to be imported correctly

              
        
def _createPyNodes():
    #for cmds.nodeType in networkx.search.dfs_preorder( _factories.nodeHierarchy , 'dependNode' )[1:]:
    #print _factories.nodeHierarchy
    # see if breadth first isn't more practical ?
    
    # reset cache
    _factories.PyNodeTypesHierarchy({})
    _factories.PyNodeNamesToPyNodes({})
    
    for treeElem in _factories.nodeHierarchy.preorder():
        #print "treeElem: ", treeElem
        mayaType = treeElem.key
            
        #print "cmds.nodeType: ", cmds.nodeType
        if mayaType == 'dependNode': continue
        
        parentMayaType = treeElem.parent.key
        #print "superNodeType: ", superNodeType, type(superNodeType)
        if parentMayaType is None:
            print "could not find parent node", mayaType
            continue
        
        _factories.addPyNode( _thisModule, mayaType, parentMayaType )



# Initialize Pymel classes to API types lookup
startTime = time.time()
_createPyNodes()
elapsed = time.time() - startTime
print "Initialized Pymel PyNodes types list in %.2f sec" % elapsed


def isValidMayaType (arg):
    return api.MayaTypesToApiTypes().has_key(arg)

def isValidPyNode (arg):
    return _factories.PyNodeTypesHierarchy().has_key(arg)

def isValidPyNodeName (arg):
    return _factories.PyNodeNamesToPyNodes().has_key(arg)

def mayaTypeToPyNode( arg, default=None ):
    return _factories.PyNodeNamesToPyNodes().get( util.capitalize(arg), default )

def toPyNode( obj, default=None ):
    if isinstance( obj, int ):
        mayaType = api.ApiEnumsToMayaTypes().get( obj, None )
        return _factories.PyNodeNamesToPyNodes().get( util.capitalize(mayaType), default )
    elif isinstance( obj, basestring ):
        try:
            return _factories.PyNodeNamesToPyNodes()[ util.capitalize(obj) ]
        except KeyError:
            mayaType = api.ApiTypesToMayaTypes().get( obj, None )
            return _factories.PyNodeNamesToPyNodes().get( util.capitalize(mayaType), default )
            
def toApiTypeStr( obj, default=None ):
    if isinstance( obj, int ):
        return api.ApiEnumsToApiTypes().get( obj, default )
    elif isinstance( obj, basestring ):
        return api.MayaTypesToApiTypes().get( obj, default)
    elif isinstance( obj, PyNode ):
        mayaType = _factories.PyNodesToMayaTypes().get( obj, None )
        return api.MayaTypesToApiTypes().get( mayaType, default)
    
def toApiTypeEnum( obj, default=None ):
    if isinstance( obj, basestring ):
        try:
            return api.ApiTypesToApiEnums()[obj]
        except KeyError:
            return api.MayaTypesToApiEnums().get(obj,default)
    elif isinstance( obj, PyNode ):
        mayaType = _factories.PyNodesToMayaTypes().get( obj, None )
        return api.MayaTypesToApiEnum().get( mayaType, default)  

def toMayaType( obj, default=None ):
    if isinstance( obj, int ):
        return api.ApiEnumsToMayaTypes().get( obj, default )
    elif isinstance( obj, basestring ):
        return api.ApiTypesToMayaTypes().get( obj, default)
    elif isinstance( obj, PyNode ):
        return _factories.PyNodesToMayaTypes().get( obj, default )
    
def toApiFunctionSet( obj, default=None ):
    if isinstance( obj, basestring ):
        try:
            return api.ApiTypesToApiClasses()[ obj ]
        except KeyError:
            return api.ApiTypesToApiClasses().get( api.MayaTypesToApiTypes.get( obj, default ) ) 
    elif isinstance( obj, int ):
        try:
            return api.apiTypesToApiClasses[ api.ApiEnumsToApiTypes()[ obj ] ]
        except KeyError:
            return default


# Selection list to PyNodes
def MSelectionPyNode ( sel ):
    length = sel.length()
    dag = api.MDagPath()
    comp = api.MObject()
    obj = api.MObject()
    result = []
    for i in xrange(length) :
        selStrs = []
        sel.getSelectionStrings ( i, selStrs )    
        # print "Working on selection %i:'%s'" % (i, ', '.join(selStrs))
        try :
            sel.getDagPath(i, dag, comp)
            pynode = PyNode( dag, comp )
            result.append(pynode)
        except :
            try :
                sel.getDependNode(i, obj)
                pynode = PyNode( obj )
                result.append(pynode)                
            except :
                warnings.warn("Unable to recover selection %i:'%s'" % (i, ', '.join(selStrs)) )             
    return result      
        
        
def activeSelectionPyNode () :
    sel = api.MSelectionList()
    api.MGlobal.getActiveSelectionList ( sel )   
    return MSelectionPyNode ( sel )

def _optToDict(*args, **kwargs ):
    result = {}
    types = kwargs.get("valid", [])
    if not util.isSequence(types) :
        types = [types]
    if not basestring in types :
        types.append(basestring)
    for n in args :
        key = val = None
        if isinstance (n, basestring) :            
            if n.startswith("!") :
                key = n.lstrip('!')
                val = False          
            else :
                key = n
                val = True
            # strip all lead and end spaces
            key = key.strip()                       
        else :
            for t in types :
                if isinstance (n, t) :
                    key = n
                    val = True
        if key is not None and val is not None :
            # check for duplicates / contradictions
            if result.has_key(key) :
                if result[key] == val :
                    # already there, do nothing
                    pass
                else :
                    warnings.warn("%s=%s contradicts %s=%s, both ignored" % (key, val, key, result[key]))
                    del result[key]
            else :
                result[key] = val
        else :
            warnings.warn("'%r' has an invalid type for this keyword argument (valid types: %s)" % (n, types))
    return result                 
            


# calling the above iterators in iterators replicating the functionalities of the builtin Maya ls/listHistory/listRelatives
# TODO : special return options: below, above, childs, parents, asList, breadth, asTree, underworld, allPaths and prune
# TODO : component support
def iterNodes ( *args, **kwargs ):
    """ Iterates on nodes of the argument list, or when args is empty on nodes of the Maya scene,
        that meet the given conditions.
        The following keywords change the way the iteration is done :
            selection = False : will use current selection if no nodes are passed in the arguments list,
                or will filter argument list to keep only selected nodes
            above = 0 : for each returned dag node will also iterate on its n first ancestors
            below = 0 : for each returned dag node will also iterate on levels of its descendents
            parents = False : if True is equivalent to above = 1
            childs = False : if True is equivalent to below = 1       
            asList = False : 
            asTree = False :
            breadth = False :
            underworld = False :
            allPaths = False :
            prune = False :
        The following keywords specify conditions the iterated nodes are filtered against, conditions can be passed either as a
        list of conditions, format depending on condition type, or a dictionnary of {condition:result} with result True or False
            name = None: will filter nodes that match these names. Names can be actual node names, use wildcards * and ?, or regular expression syntax
            position = None: will filter dag nodes that have a specific position in their hierarchy :
                'root' for root nodes
                'leaf' for leaves
                'level=<int>' or 'level=[<int>:<int>]' for a specific distance from their root
            type = None: will filter nodes that are of the specified type, or a derived type.
                The types can be specified as Pymel Node types (DependNode and derived) or Maya types names
            property = None: check for specific preset properties, for compatibility with the 'ls' command :
                'visible' : object is visible (it's visibility is True and none of it's ancestor has visibility to False)
                'ghost': ghosting is on for that object 
                'templated': object is templated or one of its ancestors is
                'intermediate' : object is marked as "intermediate object"
            attribute = None: each condition is a string made of at least an attribute name and possibly a comparison operator an a value
                checks a specific attribute of the node for existence: '.visibility',
                or against a value: 'translateX >= 2.0'
            user = None: each condition must be a previously defined function taking the iterated object as argument and returning True or False
        expression = None: allows to pass the string of a Python expression that will be evaluated on each iterated node,
            and will limit the result to nodes for which the expression evaluates to 'True'. Use the variable 'node' in the
            expression to represent the currently evaluated node

        Conditions of the same type (same keyword) are combined as with a logical 'or' for positive conditions :
        iterNodes(type = ['skinCluster', 'blendShape']) will iter on all nodes of type skinCluster OR blendShape
        Conditions of the type (same keyword) are combined as with a logical 'and' for negative conditions :
        iterNodes(type = ['!transform', '!blendShape']) will iter on all nodes of type not transform AND not blendShape
        Different conditions types (different keyword) are combined as with a logical 'and' :
        iterNodes(type = 'skinCluster', name = 'bodySkin*') will iter on all nodes that have type skinCluster AND whose name
        starts with 'bodySkin'. 
        
        Examples : (TODO)
        """

    # if a list of existing PyNodes (DependNodes) arguments is provided, only these will be iterated / tested on the conditions
    # TODO : pass the Pymel "Scene" object instead to list nodes of the Maya scene (instead of an empty arg list as for Maya's ls?
    # TODO : if a Tree or Dag of PyNodes is passed instead, make it work on it as wel    
    nodes = []
    for a in args :
        if isinstance(a, DependNode) :
            if a.exists() :
                if not a in nodes :
                    nodes.append(a)
            else :
                raise ValueError, "'%r' does not exist" % a
        else :
            raise TypeError, "'%r' is not  valid PyNode (DependNode)" % a
    # check
    #print nodes
    # parse kwargs for keywords
    # use current selection for *args
    select = int(kwargs.get('selection', 0))
    # also iterate on the hierarchy below or above (parents) that node for every iterated (dag) node
    below = int(kwargs.get('below', 0))
    above = int(kwargs.get('above', 0))
    # same as below(1) or above(1)
    childs = kwargs.get('childs', False)
    parents = kwargs.get('parents', False)
    if childs and below == 0 :
        below = 1
    if parents and above == 0 :
        above = 1  
    # return a tuple of all the hierarchy nodes instead of iterating on the nodes when node is a dag node
    # and above or below has been set
    asList = kwargs.get('list', False)
    # when below has been set, use breadth order instead of preorder for iterating the nodes below
    breadth = kwargs.get('breadth', False)
    # returns a Tree of all the hierarchy nodes instead of iterating on the nodes when node is a dag node
    # and above or below has been set
    asTree = kwargs.get('tree', False) 
    # include underworld in hierarchies
    underworld = kwargs.get('underword', False)                
    # include all instances paths for dag nodes (means parents can return more than one parent when allPaths is True)
    allPaths = kwargs.get('allPaths', False)
    # prune hierarchy (above or below) iteration when conditions are not met
    prune = kwargs.get('prune', False)
    # to use all namespaces when none is specified instead of current one
    # allNamespace = kwargs.get('allNamespace', False)
    # TODO : check for incompatible flags
    
    # selection
    if (select) :
        sel = activeSelectionPyNode ()
        if not nodes :
            # use current selection
            nodes = sel
        else :
            # intersects, need to handle components
            for p in nodes :
                if p not in sel :
                    nodes.pop(p)
            
    # Add a conditions with a check for contradictory conditions
    def _addCondition(cDic, key, val):
        # check for duplicates
        if key is not None : 
            if cDic.has_key(key) and vDic[key] != val :
                # same condition with opposite value contradicts existing condition
                warnings.warn("Condition '%s' is present with mutually exclusive True and False expected result values, both ignored" % key)
                del cDic[key]
            else :
                cDic[key] = val
                return True
        return False     
                 
    # conditions on names (regular expressions, namespaces), can be passed as a dict of
    # condition:value (True or False) or a sequence of conditions, with an optional first
    # char of '!' to be tested for False instead of True. It can be an actual node name
    nameArgs = kwargs.get('name', None)
    # the resulting dictionnary of conditions on names (compiled regular expressions)
    cNames = {}
    # check
    #print "name args", nameArgs   
    if nameArgs is not None :
        # convert list to dict if necessary
        if not isinstance(nameArgs, dict):
            if not util.isSequence(nameArgs) :
                nameArgs = [nameArgs]    
            nameArgs = _optToDict(*nameArgs)
        # check
        #print nameArgs
        # for names parsing, see class definition in nodes
        curNameSpace = namespaceInfo( currentNamespace=True )    
        for i in nameArgs.items() :
            key = i[0]
            val = i[1]
            if key.startswith('(') and key.endswith(')') :
                # take it as a regular expression directly
                pass
            elif '*' in key or '?' in key :
                # it's a glob pattern, try build a re out of it and add it to names conditions
                validCharPattern = r"[a-zA-z0-9_]"
                key = key.replace("*", r"("+validCharPattern+r"*)")
                key = key.replace("?", r"("+validCharPattern+r")")
            else :
                # either a valid dag node / node name or a glob pattern
                try :
                    name = MayaObjectName(key)
                    # if it's an actual node, plug or component name
                    # TODO : if it's a long name need to substitude namespaces on all dags
                    name = name.node
                    # only returns last node namespace in the case of a long name / dag path
                    # TODO : check how ls handles that
                    nameSpace = name.node.namespace
                    #print nameSpace, name
                    if not nameSpace :
                        # if no namespace was specified use current ('*:' can still be used for 'all namespaces')
                        nameSpace = curNameSpace
                    if cmds.namespace(exists=nameSpace) :
                        # format to have distinct match groups for nameSpace and name
                        key = r"("+nameSpace+r")("+name+r")"
                    else :
                        raise ValueError, "'%s' uses inexistent nameSpace '%s'" % (key, nameSpace)
                    # namespace thing needs a fix
                    key = r"("+name+r")"                    
                except NameParseError, e :
                    # TODO : bad formed name, ignore it
                    pass
            try :
                r = re.compile(key)
            except :
                raise ValueError, "'%s' is not a valid regular expression" % key
            # check for duplicates re and add
            _addCondition(cNames, r, val)
        # check
        #print "Name keys:"
        #for r in cNames.keys() :
            #print "%s:%r" % (r.pattern, cNames[r])     
      
    # conditions on position in hierarchy (only apply to dag nodes)
    # can be passed as a dict of conditions and values
    # condition:value (True or False) or a sequence of conditions, with an optionnal first
    # char of '!' to be tested for False instead of True.
    # valid flags are 'root', 'leaf', or 'level=x' for a relative depth to start node 
    posArgs = kwargs.get('position', None)
    # check
    #print "position args", posArgs    
    cPos = {}    
    if posArgs is not None :
        # convert list to dict if necessary
        if not isinstance(posArgs, dict):
            if not util.isSequence(posArgs) :
                posArgs = [posArgs]    
            posArgs = _optToDict(*posArgs)    
        # check
        #print posArgs
        validLevelPattern = r"level\[(-?[0-9]*)(:?)(-?[0-9]*)\]"
        validLevel = re.compile(validLevelPattern)
        for i in posArgs.items() :
            key = i[0]
            val = i[1]
            if key == 'root' or key == 'leaf' :
                pass           
            elif key.startswith('level') :
                levelMatch = validLevel.match(key)
                level = None
                if levelMatch is not None :
                    if levelMatch.groups[1] :
                        # it's a range
                        lstart = lend = None
                        if levelMatch.groups[0] :
                            lstart = int(levelMatch.groups[0])
                        if levelMatch.groups[2] :
                            lend = int(levelMatch.groups[2])
                        if lstart is None and lend is None :
                            level = None
                        else :                      
                            level = IRange(lstart, lend)
                    else :
                        # it's a single value
                        if levelMatch.groups[1] :
                            level = None
                        elif levelMatch.groups[0] :
                            level = IRange(levelMatch.groups[0], levelMatch.groups[0]+1)
                        else :
                            level = None               
                if level is None :
                    raise ValueError, "Invalid level condition %s" % key
                    key = None
                else :
                    key = level     
            else :
                raise ValueError, "Unknown position condition %s" % key
            # check for duplicates and add
            _addCondition(cPos, key, val)            
            # TODO : check for intersection with included levels
        # check
        #print "Pos keys:"
        #for r in cPos.keys() :
            #print "%s:%r" % (r, cPos[r])    
                           
    # conditions on types
    # can be passed as a dict of types (Maya or Pymel type names) and values
    # condition:value (True or False) or a sequence of type names, with an optionnal first
    # char of '!' to be tested for False instead of True.
    # valid flags are 'root', 'leaf', or 'level=x' for a relative depth to start node                       
    # Note: API iterators can filter on API types, we need to postfilter for all the rest
    typeArgs = kwargs.get('type', None)
    # check
    # #print "type args", typeArgs
    # support for types that can be translated as API types and can be directly used by API iterators
    # and other types that must be post-filtered  
    cAPITypes = {}
    cAPIPostTypes = {}
    cExtTypes = {}
    cAPIFilter = []
    if typeArgs is not None :
        extendedFilter = False
        apiFilter = False
        # convert list to dict if necessary
        if not isinstance(typeArgs, dict):
            if not util.isSequence(typeArgs) :
                typeArgs = [typeArgs]
            # can pass strings or PyNode types directly
            typeArgs = _optToDict(*typeArgs, **{'valid':DependNode})    
        # check
        #print typeArgs
        for i in typeArgs.items() :
            key = i[0]
            val = i[1]
            apiType = extType = None
            if api.isValidMayaType(key) :
                # is it a valid Maya type name
                extType = key
                # can we translate it to an API type enum (int)
                apiType = api.nodeTypeToAPIType(extType)
            else :
                # or a PyNode type or type name
                if isValidPyNodeTypeName(key) :
                    key = PyNodeNamesToPyNodes().get(key, None)
                if isValidPyNodeType(key) :
                    extType = key
                    apiType = api.PyNodesToApiTypes().get(key, None)
            # if we have a valid API type, add it to cAPITypes, if type must be postfiltered, to cExtTypes
            if apiType is not None :
                if _addCondition(cAPITypes, apiType, val) :
                    if val :
                        apiFilter = True
            elif extType is not None :
                if _addCondition(cExtTypes, extType, val) :
                    if val :
                        extendedFilter = True
            else :
                raise ValueError, "Invalid/unknown type condition '%s'" % key 
        # check
        #print " API type keys: "
        #for r in cAPITypes.keys() :
            #print "%s:%r" % (r, cAPITypes[r])
        #print " Ext type keys: "   
        #for r in cExtTypes.keys() :
            #print "%s:%r" % (r, cExtTypes[r])
        # if we check for the presence (positive condition) of API types and API types only we can 
        # use the API MIteratorType for faster filtering, it's not applicable if we need to prune
        # iteration for unsatisfied conditions
        if apiFilter and not extendedFilter and not prune :
            for item in cAPITypes.items() :
                apiInt = api.apiTypeToEnum(item[0])
                if item[1] and apiInt :
                    # can only use API filter for API types enums that are tested for positive
                    cAPIFilter.append(apiInt)
                else :
                    # otherwise must postfilter
                    cAPIPostTypes[item[0]] = item[1]
        else :
            cAPIPostTypes = cAPITypes
        # check
        #print " API filter: "
        #print cAPIFilter  
        #print " API types: "
        #print cAPITypes
        #print " API post types "
        #print cAPIPostTypes
                          
    # conditions on pre-defined properties (visible, ghost, etc) for compatibility with ls
    validProperties = {'visible':1, 'ghost':2, 'templated':3, 'intermediate':4}    
    propArgs = kwargs.get('properties', None)
    # check
    #print "Property args", propArgs    
    cProp = {}    
    if propArgs is not None :
        # convert list to dict if necessary
        if not isinstance(propArgs, dict):
            if not util.isSequence(propArgs) :
                propArgs = [propArgs]    
            propArgs = _optToDict(*propArgs)    
        # check
        #print propArgs
        for i in propArgs.items() :
            key = i[0]
            val = i[1]
            if validProperties.has_key(key) :
                # key = validProperties[key]
                _addCondition(cProp, key, val)
            else :
                raise ValueError, "Unknown property condition '%s'" % key
        # check
        #print "Properties keys:"
        #for r in cProp.keys() :
            #print "%s:%r" % (r, cProp[r])      
    # conditions on attributes existence / value
    # can be passed as a dict of conditions and booleans values
    # condition:value (True or False) or a sequence of conditions,, with an optionnal first
    # char of '!' to be tested for False instead of True.
    # An attribute condition is in the forms :
    # attribute==value, attribute!=value, attribute>value, attribute<value, attribute>=value, attribute<=value, 
    # Note : can test for attribute existence with attr != None
    attrArgs = kwargs.get('attribute', None)
    # check
    #print "Attr args", attrArgs    
    cAttr = {}    
    if attrArgs is not None :
        # convert list to dict if necessary
        if not isinstance(attrArgs, dict):
            if not util.isSequence(attrArgs) :
                attrArgs = [attrArgs]    
            attrArgs = _optToDict(*attrArgs)    
        # check
        #print attrArgs
        # for valid attribute name patterns check node.Attribute  
        # valid form for conditions
        attrValuePattern = r".+"
        attrCondPattern = r"(?P<attr>"+PlugName.pattern+r")[ \t]*(?P<oper>==|!=|>|<|>=|<=)?[ \t]*(?P<value>"+attrValuePattern+r")?"
        validAttrCond = re.compile(attrCondPattern)        
        for i in attrArgs.items() :
            key = i[0]
            val = i[1]
            attCondMatch = validAttrCond.match(key.strip())
            if attCondMatch is not None :
                # eval value here or wait resolution ?
                attCond = (attCondMatch.group('attr'), attCondMatch.group('oper'), attCondMatch.group('value'))
                # handle inversions
                if val is False :
                    if attCond[1] is '==' :
                        attCond[1] = '!='
                    elif attCond[1] is '!=' :
                        attCond[1] = '=='
                    elif attCond[1] is '>' :
                        attCond[1] = '<='
                    elif attCond[1] is '<=' :
                        attCond[1] = '>'
                    elif attCond[1] is '<' :
                        attCond[1] = '>='
                    elif attCond[1] is '>=' :
                        attCond[1] = '<'                        
                    val = True
                # Note : special case where value is None, means test for attribute existence
                # only valid with != or ==
                if attCond[2] is None :
                    if attCond[1] is None :
                        val = True
                    elif attCond[1] is '==' :
                        attCond[1] = None
                        val = False  
                    elif attCond[1] is '!=' :
                        attCond[1] = None
                        val = True
                    else :
                        raise ValueError, "Value 'None' means testing for attribute existence and is only valid for operator '!=' or '==', '%s' invalid" % key
                        attCond = None
                # check for duplicates and add
                _addCondition(cAttr, attCond, val)                                               
            else :
                raise ValueError, "Unknown attribute condition '%s', must be in the form attr <op> value with <op> : !=, ==, >=, >, <= or <" % key          
        # check
        #print "Attr Keys:"
        #for r in cAttr.keys() :
            #print "%s:%r" % (r, cAttr[r])        
    # conditions on user defined boolean functions
    userArgs = kwargs.get('user', None)
    # check
    #print "userArgs", userArgs    
    cUser = {}    
    if userArgs is not None :
        # convert list to dict if necessary
        if not isinstance(userArgs, dict):
            if not util.isSequence(userArgs) :
                userArgss = [userArgs]    
            userArgs = _optToDict(*userArgs, **{'valid':function})    
        # check
        #print userArgs            
        for i in userArgs.items() :
            key = i[0]
            val = i[1]
            if isinstance(key, basestring) :
                key = globals().get(key,None)
            if key is not None :
                if inspect.isfunction(key) and len(inspect.getargspec(key)[0]) is 1 :
                    _addCondition(cUser, key, val)
                else :
                    raise ValueError, "user condition must be a function taking one argument (the node) that will be tested against True or False, %r invalid" % key
            else :
                raise ValueError, "name '%s' is not defined" % key        
        # check
        #print "User Keys:"
        #for r in cUser.keys() :
            #print "%r:%r" % (r, cUser[r])
    # condition on a user defined expression that will be evaluated on each returned PyNode,
    # that must be represented by the variable 'node' in the expression    
    userExpr = kwargs.get('exp', None)
    if userExpr is not None and not isinstance(userExpr, basestring) :
        raise ValueError, "iterNodes expression keyword takes an evaluable string Python expression"

    # post filtering function
    def _filter( pyobj, apiTypes={}, extTypes={}, names={}, pos={}, prop={}, attr={}, user={}, expr=None  ):
        result = True
        # check on types conditions
        if result and (len(apiTypes)!=0 or len(extTypes)!=0) :
            result = False
            for cond in apiTypes.items() :
                ctyp = cond[0]
                cval = cond[1]
                if pyobj.type(api=True) == ctyp :
                    result = cval
                    break
                elif not cval :
                    result = True                                      
            for cond in extTypes.items() :  
                ctyp = cond[0]
                cval = cond[1]                                    
                if isinstance(pyobj, ctyp) :
                    result = cval
                    break
                elif not cval :
                    result = True                   
        # check on names conditions
        if result and len(names)!=0 :
            result = False
            for cond in names.items() :
                creg = cond[0]
                cval = cond[1]
                # print "match %s on %s" % (creg.pattern, pyobj.name(update=False))
                if creg.match(pyobj.name(update=False)) is not None :
                    result = cval
                    break
                elif not cval :
                    result = True                                             
        # check on position (for dags) conditions
        if result and len(pos)!=0 and isinstance(pyobj, DagNode) :
            result = False
            for cond in pos.items() :
                cpos = cond[0]
                cval = cond[1]                
                if cpos == 'root' :
                    if pyobj.isRoot() :
                        result = cval
                        break
                    elif not cval :
                        result = True
                elif cpos == 'leaf' :
                    if pyobj.isLeaf() :
                        result = cval
                        break
                    elif not cval :
                        result = True                    
                elif isinstance(cpos, IRange) :
                    if pyobj.depth() in cpos :
                        result = cval
                        break       
                    elif not cval :
                        result = True                                                                
        # TODO : 'level' condition, would be faster to get the depth from the API iterator
        # check some pre-defined properties, so far existing properties all concern dag nodes
        if result and len(prop)!=0 and isinstance(pyobj, DagNode) :
            result = False
            for cond in prop.items() :
                cprop = cond[0]
                cval = cond[1]                     
                if cprop == 'visible' :
                    if pyobj.isVisible() :
                        result = cval
                        break 
                    elif not cval :
                        result = True                                  
                elif cprop == 'ghost' :
                    if pyobj.hasAttr('ghosting') and pyobj.getAttr('ghosting') :
                        result = cval
                        break 
                    elif not cval :
                        result = True                                   
                elif cprop == 'templated' :
                    if pyobj.isTemplated() :
                        result = cval
                        break 
                    elif not cval :
                        result = True      
                elif cprop == 'intermediate' :
                    if pyobj.isIntermediate() :
                        result = cval
                        break 
                    elif not cval :
                        result = True                        
        # check for attribute existence and value
        if result and len(attr)!=0 :
            result = False
            for cond in attr.items() :
                cattr = cond[0] # a tuple of (attribute, operator, value)
                cval = cond[1]  
                if pyobj.hasAttr(cattr[0]) :                
                    if cattr[1] is None :
                        result = cval
                        break                    
                    else :
                        if eval(str(pyobj.getAttr(cattr[0]))+cattr[1]+cattr[2]) :
                            result = cval
                            break  
                        elif not cval :
                            result = True
                elif not cval :
                    result = True                                                                  
        # check for used condition functions
        if result and len(user)!=0 :
            result = False
            for cond in user.items() :
                cuser = cond[0]
                cval = cond[1]                    
                if cuser(pyobj) :
                    result = cval
                    break  
                elif not cval :
                    result = True  
        # check for a user eval expression
        if result and expr is not None :
            result = eval(expr, globals(), {'node':pyobj})     
                     
        return result
            
    # Iteration :
    needLevelInfo = False
    
    # TODO : special return options
    # below, above, childs, parents, asList, breadth, asTree, underworld, allPaths and prune
    if nodes :
        # if a list of existing nodes is provided we iterate on the ones that both exist and match the used flags        
        for pyobj in nodes :
            if _filter (pyobj, cAPIPostTypes, cExtTypes, cNames, cPos, cProp, cAttr, cUser, userExpr ) :
                yield pyobj
    else :
        # else we iterate on all scene nodes that satisfy the specified flags, 
        for obj in api.MItNodes( *cAPIFilter ) :
            pyobj = PyNode( obj )
            if pyobj.exists() :
                if _filter (pyobj, cAPIPostTypes, cExtTypes, cNames, cPos, cProp, cAttr, cUser, userExpr ) :
                    yield pyobj
        

def iterConnections ( *args, **kwargs ):
    pass

def iterHierarchy ( *args, **kwargs ):
    pass




def analyzeApiClasses():
    import inspect
    for elem in api.apiTypeHierarchy.preorder():
        try:
            parent = elem.parent.key
        except:
            parent = None
        _factories.analyzeApiClass( elem.key, None )
        



_factories.createFunctions( __name__, PyNode )