import json
import sys
import os
import copy
import numpy as np
from math import sqrt
import pandas as pd
from pyproj import CRS
from PIL import Image
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import shapely.wkt
from plyfile import PlyData
from sklearn.decomposition import PCA

reduce_factors=[1]

reduce_factor = 1

class MeshUtils:

    @staticmethod
    def getMeshBBOX(mesh):
        vertex_data = mesh['vertex'].data
        vertices = np.zeros([vertex_data.shape[0], 3], dtype=np.float32)
        #print("Vertex data shape: "+str(vertex_data))
        bbox={"minX":9999,"minY":9999,"maxX":0,"maxY":0}
        for i in range(vertices.shape[0]):
            #print(vertex_data[i])
            x=vertex_data[i][0]
            y=vertex_data[i][1]
            if x<bbox["minX"]:
                bbox["minX"]=x
            if x>bbox["maxX"]:
                bbox["maxX"]=x
            if y<bbox["minY"]:
                bbox["minY"]=y
            if y>bbox["maxY"]:
                bbox["maxY"]=y
        return bbox

    @staticmethod
    def rescale(X, A, B, C, D, force_float=False):
        retval = ((float(X - A) / (B - A)) * (D - C)) + C
        if not force_float and all(map(lambda x: type(x) == int, [X, A, B, C, D])):
            return int(round(retval))
        return retval

    @staticmethod
    def transform2Dto3DCoordinateSystem(bbox2D,bbox3D,coordinates,side):
        for point in coordinates:
            #print(point)
            point[0] = MeshUtils.rescale(point[0], bbox2D["minX"], bbox2D["maxX"], bbox3D["minX"], bbox3D["maxX"], True)
            point[1] = MeshUtils.rescale(point[1], bbox2D["minY"], bbox2D["maxY"], bbox3D["minY"], bbox3D["maxY"], True)
            point.append(0)
        return copy.deepcopy(coordinates)

    @staticmethod
    def getPointsinBBOX(mesh,bboxes):
        vresult=[]
        pboxes=[]
        try:
            for bbox in bboxes:
                pboxes.append(Polygon(bbox))
                vresult.append([])
            for coordinate in mesh.elements[0]:
                temppoint=Point(coordinate[0],coordinate[1])
                i=0
                for bbox in pboxes:
                    #print("BBOX: "+str(bbox))
                    if bbox.contains(temppoint):
                        vresult[i].append(coordinate)
                    i+=1
                #print(temppoint)
        except Exception as e:
            print(e)
        return vresult

    @staticmethod
    def createZValue(side,pointsinside,meshbbox):
        print("Points inside: "+str(len(pointsinside)))
        filteredpoints=[]
        if side=="front":
            for point in pointsinside:
                if point[2]>0:
                    filteredpoints.append(point)
        elif side=="back":
            for point in pointsinside:
                if point[2]<0:
                    filteredpoints.append(point)    
        print("Points inside filtered: "+str(len(filteredpoints)))                    
        zValues = []
        maxZ = []
        minZ = []
        for point in filteredpoints:
            zValues.append(point[2])
            maxZ = max(zValues)
            minZ = min(zValues)
        print(minZ)
        print(maxZ)
        #print(zValues)
        return {"minZ":minZ,"maxZ":maxZ,"zValues":zValues}

class MeshExportUtils:
    
    def exportPly(filename,mesh,faces=True):
        plyfile = open(filename, 'w')
        plyfile.write('ply\n'
                   'format ascii 1.0\n' +
                   'element vertex ' + str(len(mesh.coordinates)) + '\n'
                   'property float x\n'
                   'property float y\n'
                   'property float z\n'
                   'property uchar red\n'
                   'property uchar green\n'
                   'property uchar blue\n'
                   'element face ' + str(len(mesh.faces)) + '\n'
                   'property list uchar int vertex_indices\n'
                   'end_header\n')
        for coordinate in mesh.coordinates:
            plyfile.write(str(coordinate).replace('[', '').replace(']', '').replace(',', '') + ' 0 255 245 '  + '\n')
        if faces:
            for coordinate in mesh.faces:
                plyfile.write('3 ' + str(coordinate).replace('[', '').replace(']', '').replace(',', '').replace('.0', '') + '\n')
        plyfile.close()
        
    def exportSpiderGL(filename,mesh):
        spiderglexport={"vertices":[],"colors":[]}
        for coordinate in mesh.coordinates:
            spiderglexport["vertices"].append(coordinate[0])
            spiderglexport["vertices"].append(coordinate[1])
            spiderglexport["vertices"].append(coordinate[2])
            spiderglexport["colors"].append(0.0)
            spiderglexport["colors"].append(0.0)
            spiderglexport["colors"].append(1.0)
        

class AnnotationProcessor:
    
    @staticmethod
    def create3DBBOXFromMinMaxZIndex(bbox2d,minZ,maxZ):
        result=[]
        for point in bbox2d:
            point[2]=minZ
        for i in range(0,len(bbox2d)):
            bbox2d.append([bbox2d[i][0], bbox2d[i][1]*-1,maxZ])
        print(bbox2d)
        return bbox2d
    
    @staticmethod
    def getImageBBOX(imagepath):
        im = np.array(Image.open(imagepath))
        return {"minX":0,"maxX":im.shape[0],"minY":0,"maxY":im.shape[1]}

    @staticmethod
    def extractPolygonfromSVG(svgpolygon):
        svgpolygon=svgpolygon.replace("<svg><polygon points=\"","").replace("\"></polygon></svg>","")
        result=[]
        for xypair in svgpolygon.split(" "):
            spl=xypair.split(",")
            try:
                result.append([float(str(spl[0]).replace("\"","")),float(str(spl[1]).replace("\"",""))])
            except Exception as e:
                print(e)
        return result
    
    @staticmethod
    def process2DAnnotations(annojson):
        charannos=[]
        wedgeannos=[]
        for anno in annojson:
            annotype=None
            annopolygon=None
            if "body" in annojson[anno]:
                for bodyitem in annojson[anno]["body"]:
                    print(bodyitem)
                    if "purpose" in bodyitem and bodyitem["purpose"]=="tagging" and "value" in bodyitem and bodyitem["value"]=="Character":
                        annotype="Character"
                    if "purpose" in bodyitem and bodyitem["purpose"]=="tagging" and "value" in bodyitem and bodyitem["value"]=="Wedge":
                        annotype="Wedge"
                    if "type" in bodyitem and bodyitem["type"]=="SpecificResource":
                        annotype=bodyitem["source"]["label"]
            if "target" in annojson[anno]:
                if "selector" in annojson[anno]["target"] and annojson[anno]["target"]["selector"]["type"]=="SvgSelector":
                    annopolygon=AnnotationProcessor.extractPolygonfromSVG(annojson[anno]["target"]["selector"]["value"])
            if annotype!=None and annopolygon!=None:
                if annotype=="Character":
                    charannos.append({"polygon":annopolygon,"anno":annojson[anno],"id":anno})
                if annotype=="Wedge":
                    wedgeannos.append({"polygon":annopolygon,"anno":annojson[anno],"id":anno})
        return {"charannos":charannos,"wedgeannos":{}}
    
    @staticmethod
    def create3DAnnotationWithPCA(anno,anno3d,enrichedcoords,pcamean,meshsource,pca,match_target,ret_t,ret_R,s):
        anno["target"]["selector"]["type"]="WKTSelector"
        annovalue=str(anno3d)
        anno["target"]["selector"]["value"]=annovalue
        anno["target"]["selector"]["pcaValue"]=str(Polygon(PCAUtils.coordinatesToPCASystem(enrichedcoords,pcamean)))
        anno["target"]["source"]=meshsource
        anno["target"]["selector"]["computingReference"]=[]
        anno["target"]["selector"]["coordinateSystem"]=PCAUtils.csToWKT()
        compref=anno["target"]["selector"]["computingReference"]
        compref.append({"type":"PCA","value":str(pca[2][0])+" "+str(pca[2][1])+" "+str(pca[2][2])+" "+str(pca[2][3]),"transformationmatrix":str(match_target),"wktTransformation":str(PCAUtils.pcaToWKT(ret_t,ret_R,s)),"stable":PCAUtils.isPCAStable(pca)})
        return anno


class PCAUtils:
    
    match_target=None
    
    pca=None
    
    ret_t=None
    
    ret_R=None
    
    s=None
    
    pcamean=[]
    
    def rigid_transform_3D(self,A, B, scale):
        assert len(A) == len(B)

        N = A.shape[0];  # total points

        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)
        print(centroid_A)
        print(centroid_B)

        # center the points
        AA = A - np.tile(centroid_A, (N, 1))
        BB = B - np.tile(centroid_B, (N, 1))

        print(AA)
        print(BB)
        print(np.transpose(BB))
        # dot is matrix multiplication for array
        if scale:
            H = np.dot(np.transpose(BB),AA)/ N
        else:
            H = np.dot(np.transpose(BB),AA)

        U, S, Vt = np.linalg.svd(H)

        R = Vt.T * U.T

        # special reflection case
        if np.linalg.det(R) < 0:
            print("Reflection detected")
            Vt[2, :] *= -1
            R = Vt.T * U.T

        if scale:
            varA = np.var(A, axis=0).sum()
            c = 1 / (1 / varA * np.sum(S))  # scale factor
            t = -R * (centroid_B.T * c) + centroid_A.T
        else:
            c = 1
            t = -R * centroid_B.T + centroid_A.T
        print(R)
        print(t)
        print(c)
        return c, R, t

    @staticmethod
    def isPCAStable(pca):
        if pca[3][0]==pca[3][1] and pca[3][0]==pca[3][2] and pca[3][1]==pca[3][2]:
            return False
        return True
    
    @staticmethod
    def coordinatesToPCASystem(coordlist,pcamean):
        print("Convert PCA: "+str(pcamean))
        for coord in coordlist:
            coord[0]=coord[0]+pcamean[0]
            coord[1]=coord[1]+pcamean[1]
            coord[2]=coord[2]+pcamean[2]
        return coordlist    
    
    def do_PCA(self,mesh): 
        pca = PCA()
        pca.fit(mesh)
        PCA(copy=True, n_components=3, whiten=False)
        print("Fake Annotation: [ 1 1 1 ]")
        #f.write("Vector "+meshname+"\n")
        counter=1
        resultmatrix=[0,1,2,3]
        length=[]
        for variance, vector in zip(pca.explained_variance_, pca.components_):
            v = vector * 3 * np.sqrt(variance)
            #f.write("["+str(pca.mean_)+","+str(pca.mean_+v)+"] Length: "+str(np.linalg.norm(pca.mean_-(pca.mean_+v)))+"\n")
            print("PCA Vector: "+str("["+str(pca.mean_)+","+str(pca.mean_+v)+"] Length: "+str(np.linalg.norm(pca.mean_-(pca.mean_+v)))+"]"))
            length.append(str(np.linalg.norm(pca.mean_-(pca.mean_+v))))
            resultmatrix[0]=pca.mean_
            resultmatrix[counter]=pca.mean_+v
            counter+=1
        print("Resultmatrix "+str(resultmatrix))
        print("PCA Vector: "+str("["+str(pca.mean_)+","+str(pca.mean_+v)+"] Length: "+str(np.linalg.norm(pca.mean_-(pca.mean_+v)))+"]"))
        self.pcamean=[pca.mean_[0],pca.mean_[1],pca.mean_[2]]
        print("Fake Annotation Translated: [ "+str(1+pca.mean_[0])+" "+str(1+pca.mean_[1])+" "+str(1+pca.mean_[2])+" ]")
        print("Fake Annotation Translated: [ "+str(1+pca.mean_[0])+" "+str(1+pca.mean_[1])+" "+str(1+pca.mean_[2])+" ]")
        reducedMesh = pca.transform(mesh)
        self.pca = [reducedMesh,pca,resultmatrix,length]
        print(self.pca)
        p0_pca_A = self.pca[2][0]
        p1_pca_A = self.pca[2][1]
        p2_pca_A = self.pca[2][2]
        p3_pca_A = self.pca[2][3]
        # pca-Koordinaten
        p0_pca_B= np.array([0,0,0])
        p1_pca_B= np.subtract(p1_pca_A, p0_pca_A)
        p2_pca_B= np.subtract(p2_pca_A, p0_pca_A)
        p3_pca_B= np.subtract(p3_pca_A, p0_pca_A)
        # Matrizen
        print("PCA Coordinates: "+str())
        A = np.matrix([p0_pca_A , p1_pca_A, p2_pca_A, p3_pca_A])
        B = np.matrix([p0_pca_B , p1_pca_B, p2_pca_B, p3_pca_B])
        #print(A)
        #print(B)

        self.s, self.ret_R, self.ret_t=self.rigid_transform_3D(A, B,False)

        n = B.shape[0]  	    

        ## Find the error
        B2 = (self.ret_R * B.T) + np.tile(self.ret_t, (1, n))
        B2 = B2.T
        err = A - B2
        err = np.multiply(err, err)
        err = np.sum(err)
        rmse = sqrt(err / n);

        self.match_target = np.zeros((4,4))
        self.match_target[:3,:3] = self.ret_R
        self.match_target[0,3] = self.ret_t[0]
        self.match_target[1,3] = self.ret_t[1]
        self.match_target[2,3] = self.ret_t[2]
        self.match_target[3,3] = 1
        return self.match_target

    @staticmethod
    def csToWKT():
        wktString=""
        wktString+="CS[\"cartesian\",3],"
        wktString+="""AXIS["X", "geocentricX", ORDER[1],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Y", "geocentricY", ORDER[2],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Z", "geocentricZ", ORDER[3],
            LENGTHUNIT["millimetre",1]
        ]]"""
        return wktString  

    @staticmethod
    def cstoJSON():
        resjson={}
        
        

    @staticmethod
    def csToRDF(ttlstring,indid):
        ttlstring.add("<"+str(indid)+"> <http://www.opengis.net/ont/geosparql#inSRS> <http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.opengis.net/ont/crs/CartesianCoordinateSystem> .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> <http://www.w3.org/2000/01/rdf-schema#label> \"Cartesian coordinate system with 3 axis in millimetre units\"@en .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> <http://www.opengis.net/ont/crs/axis> <http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.opengis.net/ont/crs/CoordinateSystemAxis> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.w3.org/2000/01/rdf-schema#label> \"Cartesian coordinate system with 3 axis in millimetre units: Axis 1\"@en .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.opengis.net/ont/crs/abbreviation> \"X\" .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.opengis.net/ont/crs/axisDirection> <http://www.opengis.net/ont/crs/geocentricX> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.opengis.net/ont/crs/axisOrder> \"1\"^^xsd:int .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.opengis.net/ont/crs/unit> <http://www.ontology-of-units-of-measure.org/resource/om-2/millimetre> .\n")         
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> <http://www.opengis.net/ont/crs/axis> <http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.opengis.net/ont/crs/CoordinateSystemAxis> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.w3.org/2000/01/rdf-schema#label> \"Cartesian coordinate system with 3 axis in millimetre units: Axis 2\"@en .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.opengis.net/ont/crs/abbreviation> \"Y\" .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.opengis.net/ont/crs/axisDirection> <http://www.opengis.net/ont/crs/geocentricY> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.opengis.net/ont/crs/axisOrder> \"2\"^^xsd:int .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis2> <http://www.opengis.net/ont/crs/unit> <http://www.ontology-of-units-of-measure.org/resource/om-2/millimetre> .\n")  
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm> <http://www.opengis.net/ont/crs/axis> <http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> .\n") 
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.opengis.net/ont/crs/CoordinateSystemAxis> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> <http://www.w3.org/2000/01/rdf-schema#label> \"Cartesian coordinate system with 3 axis in millimetre units: Axis 3\"@en .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> <http://www.opengis.net/ont/crs/abbreviation> \"Z\" .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis1> <http://www.opengis.net/ont/crs/axisDirection> <http://www.opengis.net/ont/crs/geocentricZ> .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> <http://www.opengis.net/ont/crs/axisOrder> \"3\"^^xsd:int .\n")
        ttlstring.add("<http://www.opengis.net/ont/geosparql/crs/cs/cartesian_ax3_mm_axis3> <http://www.opengis.net/ont/crs/unit> <http://www.ontology-of-units-of-measure.org/resource/om-2/millimetre> .\n")        
        

    @staticmethod
    def pcaToRDF(translationvector,rotationmatrix,scaling,ttlstring,indid):
        ttlstring.add("<"+str(indid)+"> <http://www.opengis.net/ont/geosparql#inSRS> <"+str(indid)+"_crs_pca> .\n")
        ttlstring.add("<"+str(indid)+"_crs_pca> .\n")         

    @staticmethod
    def pcaToWKT(translationvector, rotationmatrix, scaling):
        wktTransformation="COORDINATEOPERATION[\"Object To PCA\",SOURCECRS[CS[\"cartesian\", 3],"
        wktTransformation+="""  METHOD["Geocentric translations", ID["EPSG", 1031]],
        PARAMETER["X-axis translation",  """+str(translationvector[0])+""", LENGTHUNIT["metre", 1]],
        PARAMETER["Y-axis translation",  """+str(translationvector[1])+""", LENGTHUNIT["metre", 1]],
        PARAMETER["Z-axis translation",  """+str(translationvector[2])+""", LENGTHUNIT["metre", 1]],
        AREA["Object extent"],
        BBOX[-43.7, 112.85, -9.87, 153.68]]"""
        """    
        COORDINATEOPERATION["Object To PCA",
      SOURCECRS[CS["cartesian", 3],
        AXIS["X", "geocentricX", ORDER[1],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Y", "geocentricY", ORDER[2],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Z", "geocentricZ", ORDER[3],
            LENGTHUNIT["millimetre",1]
        ]],
      TARGETCRS[CS["cartesian", 3],
        AXIS["X", "geocentricX", ORDER[1],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Y", "geocentricY", ORDER[2],
            LENGTHUNIT["millimetre",1]
        ],
        AXIS["Z", "geocentricZ", ORDER[3],
            LENGTHUNIT["millimetre",1]
        ]],
      METHOD["Geocentric translations", ID["EPSG", 1031]],
      PARAMETER["X-axis translation", -128.5, LENGTHUNIT["millimetre", 1]],
      PARAMETER["Y-axis translation",  -53.0, LENGTHUNIT["millimetre", 1]],
      PARAMETER["Z-axis translation",  153.4, LENGTHUNIT["millimetre", 1]]
      OPERATIONACCURACY[5],
      """    
        return wktTransformation




def findZCoordinate():
    print("Find Z coordinates for points")

if len(sys.argv)>1:
    annotationfile=sys.argv[1]
    
    
    
origtabletside="front"
tabletnames=["HS1174","HT073195","O147","TCH92"]
tabletsides=["front","back","left","right","bottom","top"]
tabletname="HS1174"
material="3D rendering"
creatormap={"O147":"https://orcid.org/0000-0001-6690-9098"}
creator="https://orcid.org/0000-0002-9499-5840"
namespace="https://situx.github.io/cuneiformontology/examples/"+str(tabletname).lower()+"/imgannotations/"
namespaceitems="https://situx.github.io/cuneiformontology/examples/"+str(tabletname).lower()+"/"
filename="../examples/"+str(tabletname)+"/ttl/"+str(tabletname)+"_"+str(origtabletside)+".png.json"
withlines=False
withcharoccs=False
withglyphs=False


for tabname in tabletnames:
    print(tabname)
    for side in tabletsides:
        annotationfile="../examples/"+str(tabname)+"/ttl/"+str(tabname)+"_"+str(side)+".png.json"
        if os.path.exists("../examples/"+str(tabname)+"/mesh/"+str(tabname)+"_"+str(side)+"_mesh.ply"):
            meshfile="../examples/"+str(tabname)+"/mesh/"+str(tabname)+"_"+str(side)+"_mesh.ply"
        else:
            meshfile="../examples/"+str(tabname)+"/mesh/"+str(tabname)+"_mesh.ply"
        if os.path.exists("../examples/"+str(tabname)+"/images/sides/"+str(tabname)+"_A_color_"+str(side)+".png"):
            imagefile="../examples/"+str(tabname)+"/images/sides/"+str(tabname)+"_A_color_"+str(side)+".png"
        else:
            imagefile="../examples/"+str(tabname)+"/images/sides/"+str(tabname)+"_"+str(side)+".png" 
        print(annotationfile+" "+str(os.path.exists(annotationfile))+" - "+meshfile+" "+str(os.path.exists(meshfile))+"  - "+imagefile+" "+str(os.path.exists(imagefile)))
        if not os.path.exists(meshfile) or not os.path.exists(imagefile) or not os.path.exists(annotationfile):
            continue
        print("Loading Mesh "+str(meshfile))
        mesh = PlyData.read(meshfile)
        meshframe = pd.DataFrame({
        'x':mesh['vertex']['x'][::reduce_factor],
        'y':mesh['vertex']['y'][::reduce_factor],
        'z':mesh['vertex']['z'][::reduce_factor]
        })
        with open(annotationfile,"r",encoding="utf-8") as json_file:
            annotations = json.load(json_file)   
        processed2DAnnotations=AnnotationProcessor.process2DAnnotations(annotations)
        print("Calculating BBOX of "+str(meshfile))
        #print("2D Annotations: "+str(processed2DAnnotations))
        meshbbox=MeshUtils.getMeshBBOX(mesh)
        #print(processed2DAnnotations)
        imgbbox=AnnotationProcessor.getImageBBOX(imagefile)
        pcautil=PCAUtils()
        pcautil.do_PCA(meshframe)
        annoresjson={}
        chartransannos=[]
        for anno in processed2DAnnotations["charannos"]:
            #print(anno["polygon"])
            chartransannos.append(MeshUtils.transform2Dto3DCoordinateSystem(imgbbox,meshbbox,anno["polygon"],"front"))
        wedgetransannos=[]
        for anno in processed2DAnnotations["charannos"]:
            #print(anno["polygon"])
            wedgetransannos.append(MeshUtils.transform2Dto3DCoordinateSystem(imgbbox,meshbbox,anno["polygon"],"front"))
        print("Getting BBOXes from 3D Mesh....")
        charpointsinbboxes=MeshUtils.getPointsinBBOX(mesh,chartransannos)
        wedgepointsinbboxes=MeshUtils.getPointsinBBOX(mesh,wedgetransannos)
        print("Charannos: "+str(len(charpointsinbboxes)))
        print("Wedgeannos: "+str(len(wedgepointsinbboxes)))
        charpboxres=[]
        for pbox in charpointsinbboxes:
            res=MeshUtils.createZValue(side,pbox,"")
            charpboxres.append(res)
        wedgepboxres=[]
        for pbox in wedgepointsinbboxes:
            try:
                res=MeshUtils.createZValue(side,pbox,"")
                wedgepboxres.append(res)
            except Exception as e:
                print(e)
        i=0
        for transanno in chartransannos:
            try:
                print("Create 3D BBOX From Min Max Z Index")
                print(transanno)
                enrichedcoords=AnnotationProcessor.create3DBBOXFromMinMaxZIndex(transanno,charpboxres[i]["minZ"],charpboxres[i]["maxZ"])
                #print(enrichedcoords)
                enrichedanno=Polygon(enrichedcoords)
                #print(enrichedanno)
                webanno3d=AnnotationProcessor.create3DAnnotationWithPCA(processed2DAnnotations["charannos"][i]["anno"],enrichedanno,enrichedcoords,pcautil.pcamean,meshfile,pcautil.pca,pcautil.match_target,pcautil.ret_t,pcautil.ret_R,pcautil.s)
                #print(webanno3d)
                annoresjson[processed2DAnnotations["charannos"][i]["id"]]=webanno3d
            except Exception as e:
                print(e)
            i+=1
        for transanno in wedgetransannos:
            try:
                print("Create 3D BBOX From Min Max Z Index")
                print(transanno)
                enrichedcoords=AnnotationProcessor.create3DBBOXFromMinMaxZIndex(transanno,wedgepboxres[i]["minZ"],wedgepboxres[i]["maxZ"])
                #print(enrichedcoords)
                enrichedanno=Polygon(enrichedcoords)
                #print(enrichedanno)
                webanno3d=AnnotationProcessor.create3DAnnotationWithPCA(processed2DAnnotations["wedgeannos"][i]["anno"],enrichedanno,enrichedcoords,pcautil.pcamean,meshfile,pcautil.pca,pcautil.match_target,pcautil.ret_t,pcautil.ret_R,pcautil.s)
                #print(webanno3d)
                annoresjson[processed2DAnnotations["wedgeannos"][i]["id"]]=webanno3d
            except Exception as e:
                print(e)
            i+=1
        print("Saving new annotation file: "+str(annotationfile.replace(".json","_3D.json")))
        #print(annoresjson)
        with open(annotationfile.replace(".json","_3D.json"), 'w') as f:
            print("writing annotation file....")
            f.write(json.dumps(annoresjson, indent=2,sort_keys=True))
            f.close()
