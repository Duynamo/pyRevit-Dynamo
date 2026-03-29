"""Copyright by: vudinhduybm@gmail.com"""
#region ___import all Library
import select
from sqlite3 import connect
import clr
import sys 
import System   
import math
import collections
from math import cos, e,sin,tan,radians

clr.AddReference("ProtoGeometry")
from Autodesk.DesignScript.Geometry import *

clr.AddReference("RevitAPI") 
import Autodesk
from Autodesk.Revit.DB import* 
from Autodesk.Revit.DB.Structure import*

clr.AddReference("RevitAPIUI") 
from Autodesk.Revit.UI import*
from Autodesk.Revit.UI.Selection import ISelectionFilter
clr.AddReference("System") 
from System.Collections.Generic import List

clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# clr.AddReference("System.Windows.Forms")
# clr.AddReference("System.Drawing")
# clr.AddReference("System.Windows.Forms.DataVisualization")

#endregion

#region ___Current doc/app/ui
doc = DocumentManager.Instance.CurrentDBDocument
uiapp = DocumentManager.Instance.CurrentUIApplication
app = uiapp.Application
uidoc = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument
view = doc.ActiveView
#endregion


#region ___someFunctions
def uwList(input):
    result = input if isinstance(input, list) else [input]
    return UnwrapElement(input)
def flatten(nestedList):
    flatList = []
    for item in nestedList:
        if isinstance(item, list):
            flatList.extend(flatten(item))
        else:
            flatList.append(item)
    return flatList
#endregion
def PlaneFromThreePoints(A,B,C):
    vector_AB=B.Subtract(A)
    Vector_AC=C.Subtract(A)
    normal=vector_AB.CrossProduct(Vector_AC)
    normal=normal.Normalize()
    D=-normal.DotProduct(A)  
    A=normal.X
    B=normal.Y
    C=normal.Z
    return A,B,C,D
def solve_cosine_law(A,B,C,AC):

    
    """
    A,B,C is angle by degree
    length is opposite to B angle (AC)

    let D be projection of A on CB
    then AD othorgonal to DC and DB
    """
    sin_ACD=math.sin(C)
    AD=AC*sin_ACD

    sin_ABC=math.sin(math.pi-B)
    AB=AD/sin_ABC
    return AB
def solveThreeEquations(planeEquation,angleEquation,distanceEquation):
    """
    planeEquation: Ax+By+Cz+D=0
    angleEquation: Ax+By+Cz=cos(angle)
    distanceEquation: (x-a)**2+(y-b)**2+(z-c)**2=d**2
    """
    x,y,z=1.0,1.0,1.0
    xtol=10e-6
    max_loop=100
    for _ in range(max_loop):
        x_prev,y_prev,z_prev=x,y,z
        x=(planeEquation[1]*y+planeEquation[2]*z+planeEquation[3])/planeEquation[0]
        y=(angleEquation[3]-angleEquation[0]*x-angleEquation[2]*z)/(angleEquation[1])
        z=math.sqrt(distanceEquation[3]**2-(x-distanceEquation[0])**2-(y-distanceEquation[1])**2)+distanceEquation[2]
        fz=(x-distanceEquation[0])**2+(y-distanceEquation[1])**2+(z-distanceEquation[2])**2-distanceEquation[3]**2
        dfz_dz=2*(z-2)

        if dfz_dz==0:
            break
        z=z-fz/dfz_dz
        if abs(x-x_prev) < xtol and abs(y-y_prev)<xtol and abs(z-z_prev)<xtol:
            break

    return x,y,z
#region global variable
pipe1=None
pipe2=None
delete_list=[]
data=[]
connector_created=[]

#pipe's properties variables
system_id=None
type_id=None
level_id=None
diameter=None
A,B,C,D=None,None,None,None

#endregion

def distance(a,b):
    return math.sqrt((a.X-b.X)**2+(a.Y-b.Y)**2+(a.Z-b.Z)**2)
pipes_list=Autodesk.Revit.DB.FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipingSystem).ToElements()
types=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipeCurves).WhereElementIsElementType().ToElements()
level_ids=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()
piping_system_types=Autodesk.Revit.DB.FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipingSystem).ToElements()

def verify():
    global A,B,C,D
    if distance(A.Origin,C.Origin) < distance(B.Origin,C.Origin):
        temp=A
        A=B
        B=temp
    if distance(B.Origin,D.Origin) < distance(B.Origin,C.Origin):
        temp=C
        C=D
        D=C

    return 0
def select_pipes():
    global pipe1, pipe2
    pipe1=uidoc.Selection.PickObject(Autodesk.Revit.UI.Selection.ObjectType.Element , "s")
    pipe1=doc.GetElement(pipe1)
    pipe2=uidoc.Selection.PickObject(Autodesk.Revit.UI.Selection.ObjectType.Element , "s")
    pipe2=doc.GetElement(pipe2)
    return 0
def get_pipes_param(pipe1,pipe2):
    global system_id, type_id, level_id, diameter, A, B, C, D
    system_id=pipe1.MEPSystem.GetTypeId()
    type_id=pipe1.GetTypeId()
    level_id=pipe1.LevelId
    diameter=pipe1.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM).AsDouble()
    try:
        connectors1=pipe1.MEPModel.ConnectorManager.Connectors
        connectors2=pipe2.MEPModel.ConnectorManager.Connectors
    except:
        connectors1=pipe1.ConnectorManager.Connectors
        connectors2=pipe2.ConnectorManager.Connectors
    min_distance=10e6
    connectors=[]
    temp=[None,None]
    for con in connectors1:
        for con1 in connectors2:
            if distance(con.Origin,con1.Origin) <= min_distance :
                temp[0]=con
                temp[1]=con1
                min_distance=distance(con.Origin,con1.Origin)
    for con in connectors1:
        if con not in temp:
            connectors.append(con)
    connectors.append(temp[0])
    connectors.append(temp[1])
    for con in connectors2:
        if con not in temp:
            connectors.append(con)
    A=connectors[0]
    B=connectors[1]
    C=connectors[2]
    D=connectors[3]
    verify()
    return 0
def orthogonalVec(A,B,C):
    """
    get vector lie on plane (ABC) and orthogonal to vectorAB
    """
    A,B,C=A.Origin,B.Origin,C.Origin
    planeEquation=PlaneFromThreePoints(A,B,C)
    planeVector=XYZ(planeEquation[0],planeEquation[1],planeEquation[2])
    vector_AB=B.Subtract(A)
    orthogonal=planeVector.CrossProduct(vector_AB)
    orthogonal=orthogonal.Normalize().Multiply(3.0)
    B1=B.Add(orthogonal)
    B2=B.Add(orthogonal.Negate())
    return B1 if B1.DistanceTo(C)<B2.DistanceTo(C) else B2
def create_connectors(con,con1):
    t=Transaction(doc,"create elbow")
    t.Start()
    connector=None
    error=""
    try:
       connector= DocumentManager.Instance.CurrentDBDocument.Create.NewElbowFitting(con,con1)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    return error if error is not  "" else connector
def create_temp_pipe(A,B):
    error=""
    connect=None
    
    t=Transaction(doc,"rotate")
    t.Start()
    try:
        pipe3=Autodesk.Revit.DB.Plumbing.Pipe.Create(doc,
													system_id,
													type_id,
                                                    # types[2].Id,
													level_id,
													B,
													A)
        param=pipe3.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        param.Set(diameter)
        connector3=pipe3.ConnectorManager.Connectors
        connect=None
        min_distance=10e6
        for con in connector3:
            if con.Origin.DistanceTo(B)<min_distance:
                connect=con
                min_distance=con.Origin.DistanceTo(B)
        delete_list.append(pipe3.Id)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    if error is not "":
        data.append(error)
    return error if error is not "" else connect
def create_false_pipe(A,B):
    error=""
    connect=None
    pipe3=None
    t=Transaction(doc,"rotate")
    t.Start()
    try:
        pipe3=Autodesk.Revit.DB.Plumbing.Pipe.Create(doc,
													system_id,
													type_id,
                                                    # types[2].Id,
													level_id,
													B,
													A)
        param=pipe3.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        param.Set(diameter)
        delete_list.append(pipe3.Id)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    if error is not "":
        data.append(error)
    return error if error is not "" else pipe3
def create_new_pipe(A,B):
    error=""
    t=Transaction(doc,"new_pipe")
    t.Start()
    new_p=None
    try:
        new_p=Autodesk.Revit.DB.Plumbing.Pipe.Create(doc,
													system_id,
													type_id,
                                                    # types[2].Id,
													level_id,
													B,
													A)
        # diameter=pipe1.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM).AsDouble()
        param=new_p.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        param.Set(diameter)
        # delete_list.append(new_p.Id)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    return new_p
def move(element,des):
    """
    move element to destination
    """
    root=element.Location.Point
    vec=des.Subtract(root).Negate()
    t=Transaction(doc,"move")
    t.Start()
    error=""
    try:
        element.Location.Move(vec)
    except:
        error=e
    finally:
        t.Commit()
    if error is not "":
        data.append(error)
    return error if error is "" else "moved"
def delete():
    """
    delete unuse element in delete_list
    """
    t=Transaction(doc,"delete")
    t.Start()
    error=""
    try:
        for i in delete_list:
            doc.Delete(i)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    return error

def get_vector_by_angle(A,B,C,angle):
    if distance(A,C) < distance(B,C):
        temp=A
        A=B
        B=temp
    """
    lie on plane (A,B,C) and form with AB by angle and closest to C
    angle in deg
    """
    angle=math.radians(angle)
    # A,B,C=A.Origin,B.Origin,C.Origin
    planeEquation=PlaneFromThreePoints(A,B,C)
    normal=XYZ(planeEquation[0],planeEquation[1],planeEquation[2]).Normalize()
    vector_AB=B.Subtract(A).Normalize() if distance(B,C) < distance(A,C) else A.Subtract(B).Normalize()
    vector_plane=normal.CrossProduct(vector_AB)
    vector1=vector_AB.Multiply(math.cos(angle)).Add(vector_plane.Multiply(math.sin(angle))).Normalize().Multiply(3.0)
    
    vector2=vector1.Negate()
    b1=B.Add(vector1)
    b2=B.Add(vector2)
    return b1 if distance(b1,C) < distance(b2,C) else b2

def disconnect_connectors(A,B):
    error=""
    t=Transaction(doc,"disconnect")
    t.Start()
    try:
        A.DisconnectFrom(B)
    except Exception as e:
        error=e
    finally:
        t.Commit()
    return error 
def create_independent_connector(A,B,C,D,angle):
    error=""
    v=get_vector_by_angle(A.Origin,B.Origin,C.Origin,angle)
    connect=create_temp_pipe(v,B.Origin)
    connector=create_connectors(B,connect)
    move(connector,B.Origin)
    for con in connector.MEPModel.ConnectorManager.Connectors:
        if con.IsConnectedTo(B):
            error=disconnect_connectors(con,B)
    return error if error is not "" else connector 
def create_pipe_angle(C,connector,angle):
    """
    create pipe from 2 points from the connector with angle
    """
    error=""
    connector2=None
    try:
        connect=[]
        for con in connector.MEPModel.ConnectorManager.Connectors:
            connect.append(con)
        v=get_vector_by_angle(connect[0].Origin,connect[1].Origin,C.Origin,angle)
        vector1=v.Subtract(connect[0].Origin).Normalize().Multiply(0.5)
        point=connect[0] if distance(C.Origin,connect[0].Origin) < distance(C.Origin,connect[1].Origin) else connect[1]
        vector2=vector1.Negate().Normalize().Multiply(0.5)
        vector=vector1 if distance(point.Origin.Add(vector1),C.Origin) < distance(point.Origin.Add(vector2),C.Origin) else vector2
        pipe=create_false_pipe(v.Add(vector),point.Origin.Add(vector))
        connector2=pipe.ConnectorManager.Connectors
        # for con in connector2:
        #     move(con,connect[1].Origin)
        dis=10e6
        first,second=None,None
        for con1 in connect:
            for con2 in connector2:
                if distance(con1.Origin,con2.Origin)<dis:
                    first=con1
                    second=con2
                    dis=distance(con1.Origin,con2.Origin)
        connector3=create_connectors(second,first)
    except Exception as e:
        error=e
    return error if error != "" else connector3
def get_new_angle(connector,pipe,angle):
    """
    get angle that new pipe create with 2 connectors of previous fitting
    """
    # connector=uidoc.Selection.PickObject(Autodesk.Revit.UI.Selection.ObjectType.Element , "s")
    # pipe=uidoc.Selection.PickObject(Autodesk.Revit.UI.Selection.ObjectType.Element , "s")
    # connector=doc.GetElement(connector)
    # pipe=doc.GetElement(pipe)
    # angle=90
    pipe=doc.GetElement(pipe)
    new_angle=angle
    cons=[]
    pipes=[]
    for con in connector.MEPModel.ConnectorManager.Connectors:
        cons.append(con.Origin)
    vector_con=cons[0].Subtract(cons[1]).Normalize()
    for con in pipe.ConnectorManager.Connectors:
        pipes.append(con.Origin)
    """
    verify pipes and cons value

    that pipes[0] = cons[1]
    """
    for pipe in pipes:
        for con in cons:
            if pipe.X==con.X and pipe.Y==con.Y and pipe.Z==con.Z:
                if pipes.index(pipe)==0:
                    temp=pipes[0]
                    pipes[0]=pipes[1]
                    pipes[1]=temp
                if cons.index(con)==1:
                    temp=cons[0]
                    cons[0]=cons[1]
                    cons[1]=temp
                break
    vector_pipe=pipes[0].Subtract(pipes[1]).Normalize()
    # new_angle=vector_con.AngleTo(vector_pipe)
    new_angle=math.acos(vector_con.DotProduct(vector_pipe))
    new_angle=math.degrees(new_angle)
    angle=180-angle
    # new_angle=180-angle-new_angle
    result=180-angle-new_angle 
    if result <0:
        new_angle=180-new_angle
        result=180-angle-new_angle 
    return result
def replace_pipes():
    connect1,connect2=None,None
    data.append(connector_created)
    for con in connector_created[0].MEPModel.ConnectorManager.UnusedConnectors:
        connect1=con
    for con in connector_created[-1].MEPModel.ConnectorManager.UnusedConnectors:
        connect2=con
    t=Transaction(doc,"rotate")
    t.Start()
    try:
        pipe3=Autodesk.Revit.DB.Plumbing.Pipe.Create(doc,
                                                    system_id,
                                                    type_id,
                                                    level_id,
													connect1.Origin,
													A.Origin)
        param=pipe3.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        param.Set(diameter)
        for con in pipe3.ConnectorManager.Connectors:
            if con.Origin.X == connect1.Origin.X and con.Origin.Y == connect1.Origin.Y and con.Origin.Z == connect1.Origin.Z:
                try:
                    con.ConnectTo(connect1)
                except:
                    pass
        pipe4=Autodesk.Revit.DB.Plumbing.Pipe.Create(doc,
                                                    system_id,
                                                    type_id,
                                                    level_id,
													connect2.Origin,
													D.Origin)
        param=pipe4.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        for con in pipe4.ConnectorManager.Connectors:
            if con.Origin.X == connect2.Origin.X and con.Origin.Y == connect2.Origin.Y and con.Origin.Z == connect2.Origin.Z:
                try:
                    con.ConnectTo(connect2)
                except:
                    pass
        param.Set(diameter)
    except Exception as e:
        error=e
        data.append(error)
    finally:
        t.Commit()
    return 0
#region flip connector
def check_connected(root,connector):
    """
    if 2 connector is connected, disconnect them
    """
    error=""
    connect1,connect2=None,None
    try:
        
        for con1 in root.MEPModel.ConnectorManager.Connectors:
            for con2 in connector.MEPModel.ConnectorManager.Connectors:
       
                if con1.Origin.X==con2.Origin.X and con1.Origin.Y==con2.Origin.Y and con1.Origin.Z==con2.Origin.Z:

                    connect1=con1
                    connect2=con2
                    t=Transaction(doc,"disconnect")
                    t.Start()
                    try:
                        con1.DisconnectFrom(con2)
                    except:
                        pass
                    t.Commit()
    except Exception as e:
        error=e
    return root,connector,connect1,connect2

def rotate_connector(root,connector):
    cons=[]
    connectors_params=[]
    FL="Flange Thickness"
    HL="HL"
    AN="Angle"
    pipe_angle=0
    params=connector.Parameters
    for param in params:
        if param.Definition.Name==FL:
            connectors_params.append(param.AsDouble())
        if param.Definition.Name==HL:
            connectors_params.append(param.AsDouble())
        if param.Definition.Name==AN:
            pipe_angle=param.AsDouble()
            pipe_angle=math.degrees(pipe_angle)
    c=check_connected(root,connector)
    con1,con2=c[2],c[3]
    cons=[]
    try:
        connectors=connector.MEPModel.ConnectorManager.Connectors
    except Exception as e:
        connectors=connector.ConnectorManager.Connectors
    for con in connectors:
        cons.append(con)
    if cons[0].Id == 2:
        temp=cons[0]
        cons[0]=cons[1]
        cons[1]=temp
    origin0=cons[0].Origin
    origin1=cons[1].Origin
    first_point=cons[0].Origin
    second_point=cons[1].Origin
    location_point=connector.Location.Point
    
    t=Transaction(doc,"rotate")
    t.Start()
    error=""
    try:
        plane_equation=PlaneFromThreePoints(first_point,second_point,location_point)
        normal_vector=XYZ(*plane_equation[:3])
     
        y_axis=first_point.Subtract(location_point).Normalize()
        z_axis=normal_vector
        x_axis=y_axis.CrossProduct(normal_vector).Normalize()
        x_axis=second_point.Subtract(location_point).Normalize()
        vector_endpoint=first_point.Subtract(location_point).Normalize().Multiply(sum(connectors_params))
        #rotate by x_axis by degree
        x_line=Autodesk.Revit.DB.Line.CreateBound(location_point,location_point.Add(x_axis))
        # rotated=connector.Location.Rotate(x_line,math.radians(180))
        geoplane=Plane.CreateByThreePoints(first_point,second_point,location_point)
        sketchPlane=SketchPlane.Create(doc,geoplane)
        #rotate by y_axis by degree
        y_line=Autodesk.Revit.DB.Line.CreateBound(location_point,location_point.Add(y_axis))
        
        # #big fit
        
        if con2.Id == con1.Id:
            rotated=connector.Location.Rotate(y_line,math.radians(180))
            #rotate by z_axis by 
            z_line=Autodesk.Revit.DB.Line.CreateBound(location_point,location_point.Add(z_axis))
            
            rotated=connector.Location.Rotate(z_line,math.radians(180-pipe_angle))
            if con2.Id==2:
                root_con=location_point.Subtract(origin1)
                move=connector.Location.Move(root_con.Subtract(location_point.Subtract(cons[0].Origin)).Negate())
            else:
            # #small fit
                root_con=location_point.Subtract(origin0)
                move=connector.Location.Move(root_con.Subtract(location_point.Subtract(cons[1].Origin)).Negate())   
        for con1 in root.MEPModel.ConnectorManager.Connectors:
            for con2 in connector.MEPModel.ConnectorManager.Connectors:
                if con1.Origin.X==con2.Origin.X and con1.Origin.Y==con2.Origin.Y and con1.Origin.Z==con2.Origin.Z:
                    try:
                        con1.ConnectTo(con2)
                    except Exception as e:
                        pass
        else:
            pass  
        
    except Exception as e:
        error=e
    finally :
        t.Commit()
    return connector
#endregion
def create_connector_set(A,B,C,D,angle_list):
    error=""
    global connector_created
    try:
        first_con=create_independent_connector(A,B,C,D,angle_list[0])
        temp_con=first_con
        connector=first_con
        connector_created.append(connector)
        temp_point=[]
        for i in range(1,len(angle_list)):
            for con in temp_con.MEPModel.ConnectorManager.Connectors:
                temp_point.append(con)
            angle=get_new_angle(temp_con,delete_list[i-1],angle_list[i])
            connector=create_pipe_angle(C,temp_con,angle)
            data.append(connector)
            connector=rotate_connector(temp_con,connector)
            connector_created.append(connector)
            temp_con=connector
        move_param=find_move_vector(connector,A.Origin,B.Origin,C.Origin,D.Origin)
        move_vector=A.Origin.Subtract(B.Origin).Normalize()
        destination=connector.Location.Point.Add(move_vector.Multiply(move_param))
        delete()
        e=move(connector,destination)
        # create_connectors(connect,C)
        
    except Exception as e:
        error=e
    t=Transaction(doc,"delete")
    t.Start()
    doc.Delete(pipe1.Id)
    doc.Delete(pipe2.Id)
    t.Commit()
    replace_pipes()
    return error
def find_move_vector(connector,A,B,C,D):
    closest=connector.Location.Point
    vector_AB=B.Subtract(A)
    vector_CD=D.Subtract(C)
    vector_AC=C.Subtract(closest)
    AC=distance(C,closest)

    BAC=vector_AB.AngleTo(vector_AC)
    ABC=vector_CD.AngleTo(vector_AB)
    BCA=vector_AC.AngleTo(vector_CD)
    temp=solve_cosine_law(BAC,ABC,BCA,AC)
    return temp

def get_pipe_data():
    error=""
    global pipe2,pipe1
    angle_list=[90,22.5]
    select_pipes()
    get_pipes_param(pipe1,pipe2)
    t=Transaction(doc,"erase p2")
    t.Start()
    doc.Delete(pipe2.Id)
    doc.Delete(pipe1.Id)
    t.Commit()
    C_location=D.Origin.Add(C.Origin).Multiply(0.5)
    B_location=A.Origin.Add(B.Origin).Multiply(0.5)
    pipe2=create_new_pipe(C_location,D.Origin)
    pipe1=create_new_pipe(B_location,A.Origin)
    get_pipes_param(pipe1,pipe2)
    
    connectors=None
    connectors=create_connector_set(A,B,C,D,angle_list)
    return error,connectors

OUT=get_pipe_data(),data
