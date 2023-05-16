from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink,
                        QgsFields, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterEnum,
                        QgsProcessingParameterFeatureSink,
                        QgsCoordinateReferenceSystem, QgsWkbTypes,
                        QgsCoordinateTransform, QgsGeometry,
                        QgsProcessingParameterField,
                        QgsProcessingParameterDefinition,
                        QgsDistanceArea, QgsUnitTypes)
                        
import os
                       
class PaddockWateredAreas(QgsProcessingAlgorithm):
    PADDOCKS = 'PADDOCKS'
    WATER_POINTS = 'WATER_POINTS'
    WA_BUFFER_DIST = 'WA_BUFFER_DIST'
    TARGET_FIELDS = 'TARGET_FIELDS'
    AREA_METHOD = 'AREA_METHOD'
    WATERED_AREA = 'WATERED_AREA'
    
    wa_distances = ['3km', '5km']
    area_methods = ['Ellipsoidal', 'Planar']
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "paddockwateredareas"
         
    def displayName(self):
        return "Paddock watered areas"
 
    def group(self):
        return "Analysis"
 
    def groupId(self):
        return "analysis"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/wa_icon.png"))
 
    def shortHelpString(self):
        return "Extract watered area per paddock.<br>Either 3km or 5km watered area\
        buffer can be selected.<br>The output polygon layer will take fields from\
        the input paddocks layer. A subset of fields to copy can be selected.\
        By default all fields are selected.<br>The output layer will also contain\
        two additional fields showing the watered area in hecatares and square\
        kilometers. The method (ellipsoidal or planar) used to calculate the\
        area values can also be selected."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.PADDOCKS,
            "Paddock polygon layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.WATER_POINTS,
            "Water points layer",
            [QgsProcessing.TypeVectorPoint]))
        
        self.addParameter(QgsProcessingParameterEnum(
            self.WA_BUFFER_DIST,
            "Watered area buffer distance",
            self.wa_distances, defaultValue=0))
            
        self.parameterDefinition(self.WA_BUFFER_DIST).setMetadata({
            'widget_wrapper': {
                'useCheckBoxes': True,
                'columns': 2}})
        
        self.addParameter(QgsProcessingParameterField(
            self.TARGET_FIELDS,
            "Fields to add to output layer",
            parentLayerParameterName=self.PADDOCKS,
            allowMultiple=True,
            defaultToAllFields=True))
            
        self.addParameter(QgsProcessingParameterEnum(
            self.AREA_METHOD,
            "Area calculation method",
            self.area_methods, defaultValue=0))
            
        self.parameterDefinition(self.AREA_METHOD).setMetadata({
            'widget_wrapper': {
                'useCheckBoxes': True,
                'columns': 2}})
                
        self.parameterDefinition(self.AREA_METHOD).setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.WATERED_AREA,
            "Output watered area",
            QgsProcessing.TypeVectorPolygon))
 
    def processAlgorithm(self, parameters, context, feedback):
        source_paddocks = self.parameterAsSource(parameters, self.PADDOCKS, context)
        
        for ft in source_paddocks.getFeatures():
            if not ft.geometry().isGeosValid():
                raise QgsProcessingException(f"Feature in layer: {source_paddocks.sourceName()} with id: {ft.id()} has invalid geometry")
                return {}
        
        source_waterpoints = self.parameterAsSource(parameters, self.WATER_POINTS, context)
        
        param_wa_buffer_dist = self.parameterAsEnum(parameters, self.WA_BUFFER_DIST, context)
        
        if param_wa_buffer_dist == 0:
            wa_buffer_dist = 3000
        elif param_wa_buffer_dist == 1:
            wa_buffer_dist = 5000
                    
        source_crs = source_waterpoints.sourceCrs()
        
        if source_crs.isGeographic():
            # use GDA2020/Australian Albers as destination crs for transformations
            dest_crs = QgsCoordinateReferenceSystem('epsg:9473')
            # transform waterpoints to projected crs
            waterpoint_geoms = [self.transformedGeom(f.geometry(), source_crs, dest_crs, context.transformContext()) for f in source_waterpoints.getFeatures()]
        else:
            # source crs is already projected (and we will transform paddock geoms to match this)
            dest_crs = source_crs
            # simply store feature geometries
            waterpoint_geoms = [f.geometry() for f in source_waterpoints.getFeatures()]
        
        selected_fields = self.parameterAsFields(parameters, self.TARGET_FIELDS, context)
        
        target_fields = [fld for fld in source_paddocks.fields() if fld.name() in selected_fields]
        
        dest_fields = QgsFields()
        
        for f in target_fields:
            dest_fields.append(f)
        
        for f in [QgsField("No. WtrPts", QVariant.Int),
                QgsField(f"{self.wa_distances[param_wa_buffer_dist]}_WA_ha", QVariant.Double, prec=3),
                QgsField(f"{self.wa_distances[param_wa_buffer_dist]}_WA_km2", QVariant.Double, prec=5)]:
            dest_fields.append(f)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.WATERED_AREA, context,
                                               dest_fields, QgsWkbTypes.Polygon, dest_crs)
                                               
        area_method = self.parameterAsEnum(parameters, self.AREA_METHOD, context)
        
        # Define QgsDistanceArea object and set crs & ellipsoid to that used by output layer crs
        da = QgsDistanceArea()
        da.setSourceCrs(dest_crs, context.transformContext())
        da.setEllipsoid(dest_crs.ellipsoidAcronym())
        
        for ft in source_paddocks.getFeatures():
            if not ft.geometry().isGeosValid():
                geom = ft.geometry().makeValid()
            else:
                geom = ft.geometry()
            # here we transform paddock geometry to match water points
            paddock_geom = self.transformedGeom(geom,
                            source_paddocks.sourceCrs(),
                            dest_crs, context.transformContext())
                            
            pdk_wpts = [pt for pt in waterpoint_geoms if pt.intersects(paddock_geom)]
            
            if not pdk_wpts:
                continue
            
            buffers = [p.buffer(wa_buffer_dist, 25) for p in pdk_wpts]
                                               
            dissolved_buffer = QgsGeometry.unaryUnion(buffers)
            
            clipped_buffer = dissolved_buffer.intersection(paddock_geom)
            
            clipped_buffer.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
            
            feedback.pushDebugInfo(repr(clipped_buffer))
            
            feat = QgsFeature(dest_fields)
            feat.setGeometry(clipped_buffer)
            src_atts = [ft[i] for i in selected_fields]
            src_atts.append(len(pdk_wpts))
            
            if area_method == 0:# ellipsoidal
                area_m2 = da.measureArea(feat.geometry())
                feedback.pushDebugInfo(repr(area_m2))
                area_ha = round(da.convertAreaMeasurement(area_m2, QgsUnitTypes.AreaHectares), 3)
                area_km2 = round(da.convertAreaMeasurement(area_m2, QgsUnitTypes.AreaSquareKilometers), 5)
            elif area_method == 1:
                area_ha = round(feat.geometry().area()/10000, 3)
                area_km2 = round(feat.geometry().area()/1000000, 5)
            src_atts.append(area_ha)
            src_atts.append(area_km2)
            feat.setAttributes(src_atts)
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            
            if context.willLoadLayerOnCompletion(dest_id):
                details = context.layerToLoadOnCompletionDetails(dest_id)
                if context.getMapLayer(dest_id).name() == 'Output watered area':
                    details.name = f'{self.wa_distances[param_wa_buffer_dist]}_watered_area'
                    details.forceName = True

        return {self.WATERED_AREA: dest_id}
        
    def transformedGeom(self, g, src_crs, target_crs, transform_context):
        if src_crs != target_crs:
            xform = QgsCoordinateTransform(src_crs, target_crs, transform_context)
            g.transform(xform)
        return g