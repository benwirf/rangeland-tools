from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterString, QgsWkbTypes,
                        QgsProcessingParameterField, QgsFields,
                        QgsProcessingParameterFeatureSink, QgsGeometry,
                        QgsProcessingParameterCrs, QgsCoordinateTransform,
                        QgsSpatialIndex)

                       
class AddLandTypeAttribute(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    SOURCE_FIELDS = 'SOURCE_FIELDS'
    LAND_TYPES = 'LAND_TYPES'
    LAND_TYPE_FIELD = 'LAND_TYPE_FIELD'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "addlandtypeattribute"
         
    def displayName(self):
        return "Add land type"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Add an attribute containing the land type in which the point\
        is located for each point in a gps collar layer"
         
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            "Input GPS point layer",
            [QgsProcessing.TypeVectorPoint]))
            
        self.addParameter(QgsProcessingParameterField(
            self.SOURCE_FIELDS,
            'Fields to include in output layer',
            parentLayerParameterName=self.INPUT,
            allowMultiple=True,
            defaultToAllFields=True))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LAND_TYPES,
            "Land types layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterField(
            self.LAND_TYPE_FIELD,
            'Field containing land type',
            parentLayerParameterName=self.LAND_TYPES,
            type=QgsProcessingParameterField.String))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Points with land type attibute added",
            QgsProcessing.TypeVectorPoint))
            
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        source = self.parameterAsSource(parameters, self.INPUT, context)
        
        source_fields = self.parameterAsFields(parameters, self.SOURCE_FIELDS, context)
        
        lt_lyr = self.parameterAsSource(parameters, self.LAND_TYPES, context)
        
        lt_fld = self.parameterAsFields(parameters, self.LAND_TYPE_FIELD, context)[0]
        
        src_crs = source.sourceCrs()
        
        lt_crs = lt_lyr.sourceCrs()
        
        output_fields = ([QgsField('Dist to nearest water m', len=8, prec=3),
                        QgsField('Dist to nearest water km', len=8, prec=5),
                        QgsField('Water Type', QVariant.String),
                        QgsField('Water Name', QVariant.String)])
        
        sink_fields = QgsFields()
        
        for fld in source.fields():
            if fld.name() in source_fields:
                sink_fields.append(fld)
                
        sink_fields.append(QgsField('Land Type'))

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               sink_fields, source.wkbType(), source.sourceCrs())
        #############################################################
        lt_sp_idx = QgsSpatialIndex(lt_lyr)
        all_land_types = {ft.id(): ft for ft in lt_lyr.getFeatures()}
        geom_engines = {}
        for ft in lt_lyr.getFeatures():
            geom_engine = QgsGeometry.createGeometryEngine(ft.geometry().constGet())
            geom_engine.prepareGeometry()
            geom_engines[ft.id()] = geom_engine
        #############################################################
        output_feats = []
        feature_count = source.featureCount()
        for i, ft in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            pcnt = ((i+1)/feature_count)*100
            feedback.setProgress(round(pcnt, 1))
            if src_crs != lt_crs:
                geom = self.transformed_geom(ft.geometry(), src_crs, lt_crs, context.project())
            else:
                geom = ft.geometry()
            #pnt = geom.asMultiPoint()[0]
            candidate_lt_ids = lt_sp_idx.intersects(geom.boundingBox())
            #feedback.pushInfo(repr(candidate_lt_ids))
            land_type = 'NULL'
            if candidate_lt_ids:
                for id in candidate_lt_ids:
                    candidate_ft = all_land_types[id]
                    ge = geom_engines[id]
                    if ge.contains(geom.constGet()):
                        land_type = candidate_ft[lt_fld]
            atts = [ft[fld_name] for fld_name in source_fields]
            atts.append(land_type)
            feat = QgsFeature(sink_fields)
            feat.setGeometry(ft.geometry())
            feat.setAttributes(atts)
            output_feats.append(feat)
        sink.addFeatures(output_feats, QgsFeatureSink.FastInsert)
        
        if context.willLoadLayerOnCompletion(dest_id):
            details = context.layerToLoadOnCompletionDetails(dest_id)
            # If memory layer output with generic name, we will rename it
            #feedback.pushInfo(details.name)
            if details.name == "Points with land type attibute added":
                details.name = f'Land_type_added'
        
        results['OUTPUT'] = dest_id
        return results
        

    def transformed_geom(self, geom, src_crs, tgt_crs, project):
        g = QgsGeometry.fromWkt(geom.asWkt())
        xform = QgsCoordinateTransform(src_crs, tgt_crs, project)
        g.transform(xform)
        return g