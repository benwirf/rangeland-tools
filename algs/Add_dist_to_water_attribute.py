from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterString, QgsWkbTypes,
                        QgsProcessingParameterField, QgsFields,
                        QgsProcessingParameterFeatureSink, QgsGeometry,
                        QgsProcessingParameterCrs, QgsCoordinateTransform,
                        QgsSpatialIndex)
import processing
                       
class AddDistanceToWaterAttribute(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    SOURCE_FIELDS = 'SOURCE_FIELDS'
    WATERPOINTS = 'WATERPOINTS'
    WP_TYPE_FIELD = 'WP_TYPE_FIELD'
    WP_NAME_FIELD = 'WP_NAME_FIELD'
    TARGET_CRS = 'TARGET_CRS'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "adddist2water"
         
    def displayName(self):
        return "Add distance to water"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Add an attribute containing distance to nearest water for\
        each point in gps collar layer"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def checkParameterValues(self, parameters, context):
        crs = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        if crs.isGeographic():
            return False, 'Please select a projected CRS'
        return super().checkParameterValues(parameters, context)
   
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
            self.WATERPOINTS,
            "Waterpoint layer",
            [QgsProcessing.TypeVectorPoint]))
            
        self.addParameter(QgsProcessingParameterField(
            self.WP_TYPE_FIELD,
            'Field containing waterpoint type',
            parentLayerParameterName=self.WATERPOINTS,
            type=QgsProcessingParameterField.String,
            optional=True))
        
        self.addParameter(QgsProcessingParameterField(
            self.WP_NAME_FIELD,
            'Field to use for waterpoint name/ID',
            parentLayerParameterName=self.WATERPOINTS))
        
        self.addParameter(QgsProcessingParameterCrs(
            self.TARGET_CRS,
            'CRS to use for distance calculation (Projected)',
            'EPSG:9473'))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Points with distance to water attibute added",
            QgsProcessing.TypeVectorPoint))
            
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        source = self.parameterAsSource(parameters, self.INPUT, context)
        
        source_fields = self.parameterAsFields(parameters, self.SOURCE_FIELDS, context)
        
        wpt_lyr = self.parameterAsSource(parameters, self.WATERPOINTS, context)
        
        wpt_type_flds = self.parameterAsFields(parameters, self.WP_TYPE_FIELD, context)
        
        if wpt_type_flds:
            wpt_type_fld = wpt_type_flds[0]
        else:
            wpt_type_fld = None
        
        wpt_name_fld = self.parameterAsFields(parameters, self.WP_NAME_FIELD, context)[0]
        
        src_crs = source.sourceCrs()
        
        dest_crs = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        
        output_fields = ([QgsField('Dist to nearest water m', QVariant.Double, len=8, prec=3),
                        QgsField('Dist to nearest water km', QVariant.Double, len=8, prec=5),
                        QgsField('Water Type', QVariant.String),
                        QgsField('Water Name', QVariant.String)])
        
        sink_fields = QgsFields()
        
        for fld in source.fields():
            if fld.name() in source_fields:
                sink_fields.append(fld)
        for fld in output_fields:
            if fld.name() == 'Water Type':
                if wpt_type_fld is None:
                    continue
            sink_fields.append(fld)

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               sink_fields, source.wkbType(), source.sourceCrs())
        #############################################################
        if wpt_lyr.sourceCrs() != dest_crs:
            wpt_vlayer = wpt_lyr.materialize(QgsFeatureRequest().setDestinationCrs(dest_crs, context.transformContext()))
        else:
            wpt_vlayer = wpt_lyr.materialize(QgsFeatureRequest())
                        
        fix_geom_params = {'INPUT': wpt_vlayer,
                            'METHOD':1,
                            'OUTPUT':'TEMPORARY_OUTPUT'}
        wpt_vlayer_fixed_id = processing.run("native:fixgeometries",
                                            fix_geom_params,
                                            is_child_algorithm=True,
                                            feedback=feedback,
                                            context=context)['OUTPUT']
        wpt_vlayer_fixed = context.getMapLayer(wpt_vlayer_fixed_id)
        wpt_sp_idx = QgsSpatialIndex(wpt_vlayer_fixed)
        
        output_feats = []
        feature_count = source.featureCount()
        for i, ft in enumerate(source.getFeatures()):
#            if i == 10:
#                break
            if feedback.isCanceled():
                break
            pcnt = ((i+1)/feature_count)*100
            feedback.setProgress(round(pcnt, 1))
            if src_crs != dest_crs:
                geom = self.transformed_geom(ft.geometry(), src_crs, dest_crs, context.project())
            else:
                geom = ft.geometry()
            try:
                pnt = geom.asMultiPoint()[0]
            except TypeError:
                pnt = geom.asPoint()
            nwp_id = wpt_sp_idx.nearestNeighbor(pnt)[0]
            nwp_ft = wpt_vlayer.getFeature(nwp_id)
            atts = [ft[fld_name] for fld_name in source_fields]
#            feedback.pushInfo(repr([fld.name() for fld in sink_fields]))
#            feedback.pushInfo(repr(atts))
            dist_to_nearest_water = geom.distance(nwp_ft.geometry())# meters
            atts.append(round(dist_to_nearest_water, 3))
            dist_to_nearest_water_km = dist_to_nearest_water/1000
            atts.append(round(dist_to_nearest_water_km, 5))
            if wpt_type_fld is not None:
                #feedback.pushInfo(repr(nwp_ft))
                try:
                    nearest_wp_type = nwp_ft[wpt_type_fld]
                except KeyError:
                    nearest_wp_type = 'Not Found'
                atts.append(str(nearest_wp_type))
            try:
                nearest_wp_name = nwp_ft[wpt_name_fld]
            except KeyError:
                nearest_wp_name = 'Not Found'
            atts.append(str(nearest_wp_name))
            feat = QgsFeature(sink_fields)
            feat.setGeometry(ft.geometry())
            feat.setAttributes(atts)
            output_feats.append(feat)
        sink.addFeatures(output_feats, QgsFeatureSink.FastInsert)
        
        if context.willLoadLayerOnCompletion(dest_id):
            details = context.layerToLoadOnCompletionDetails(dest_id)
            # If memory layer output with generic name, we will rename it
            #feedback.pushInfo(details.name)
            if details.name == "Points with distance to water attibute added":
                details.name = f'Distance_2_water'
        
        results['OUTPUT'] = dest_id
        return results
        

    def transformed_geom(self, geom, src_crs, tgt_crs, project):
        g = QgsGeometry.fromWkt(geom.asWkt())
        xform = QgsCoordinateTransform(src_crs, tgt_crs, project)
        g.transform(xform)
        return g
        
        