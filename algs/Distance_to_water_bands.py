from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (NULL,
                        QgsField,
                        QgsFields,
                        QgsFeature,
                        QgsFeatureSink,
                        QgsFeatureRequest,
                        QgsGeometry,
                        QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField,
                        QgsProcessingParameterNumber,
                        QgsProcessingParameterFeatureSink,
                        QgsCoordinateReferenceSystem,
                        QgsStyle,
                        QgsProcessingLayerPostProcessorInterface,
                        QgsSymbol,
                        QgsSymbolLayer,
                        QgsProperty,
                        QgsRendererCategory,
                        QgsCategorizedSymbolRenderer)
                        
import os
                       
class DistanceToWaterBands(QgsProcessingAlgorithm):
    PADDOCKS = 'PADDOCKS'
    PDK_NAME_FLD = 'PDK_NAME_FLD'
    WATERPOINTS = 'WATERPOINTS'
    BAND_WIDTH = 'BAND_WIDTH'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "distancetowaterbands"
         
    def displayName(self):
        return "Distance to water bands"
 
    def group(self):
        return "Analysis"
 
    def groupId(self):
        return "analysis"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/dtw_icon.png"))
 
    def shortHelpString(self):
        return "Create dissolved buffer rings of a specified width\
                around all points in an input waterpoint layer\
                within each paddock polygon of an input paddock layer."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.PADDOCKS,
            "Paddock polygon layer",
            [QgsProcessing.TypeVectorPolygon]))
        
        self.addParameter(QgsProcessingParameterField(
            self.PDK_NAME_FLD,
            "Paddock name field",
            parentLayerParameterName=self.PADDOCKS,
            type=QgsProcessingParameterField.String))
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.WATERPOINTS,
            "Water points layer",
            [QgsProcessing.TypeVectorPoint]))
            
        self.addParameter(QgsProcessingParameterNumber(
            self.BAND_WIDTH,
            "Band width (meters)",
            defaultValue=500))
            
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Watered_bands",
            QgsProcessing.TypeVectorPolygon))
 
    def processAlgorithm(self, parameters, context, feedback):
        pdk_lyr = self.parameterAsSource(parameters, self.PADDOCKS, context)
        
        pdk_name_flds = self.parameterAsFields(parameters, self.PDK_NAME_FLD, context)# Returns a list
        
        name_fld = pdk_name_flds[0]# Field name string
        
        wpt_lyr = self.parameterAsSource(parameters, self.WATERPOINTS, context)
        
        band_width = self.parameterAsInt(parameters, self.BAND_WIDTH, context)
        
        if (not pdk_lyr.sourceCrs().isGeographic()) and (wpt_lyr.sourceCrs() != pdk_lyr.sourceCrs()):
            wpt_lyr = wpt_lyr.materialize(QgsFeatureRequest().setDestinationCrs(pdk_lyr.sourceCrs(), context.transformContext()))
        if (not wpt_lyr.sourceCrs().isGeographic()) and (wpt_lyr.sourceCrs() != pdk_lyr.sourceCrs()):
            pdk_lyr = pdk_lyr.materialize(QgsFeatureRequest().setDestinationCrs(wpt_lyr.sourceCrs(), context.transformContext()))
        if (pdk_lyr.sourceCrs().isGeographic()) and (wpt_lyr.sourceCrs().isGeographic()):
            pdk_lyr = pdk_lyr.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), context.transformContext()))
            wpt_lyr = wpt_lyr.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), context.transformContext()))
            
        flds = QgsFields()

        flds_to_add = [QgsField('Pdk Name', QVariant.String),
                        QgsField('PdkArea Ha', QVariant.Double, len=10, prec=2),
                        QgsField('DTW Band', QVariant.String),
                        QgsField('Outer dist', QVariant.Int),
                        QgsField('Area Ha', QVariant.Double, len=10, prec=2),
                        QgsField('Percent', QVariant.Double, len=10, prec=7),
                        QgsField('Max_DTW', QVariant.Int)]
                        
        for fld in flds_to_add:
            flds.append(fld)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               flds, pdk_lyr.wkbType(), pdk_lyr.sourceCrs())
        
        #####################################################
        pdk_max_dtws = {}

        unnamed_pdk_count = 0
        
        feats = []

        for pdk in pdk_lyr.getFeatures():
            pdk_name = pdk[name_fld]
            if pdk_name == NULL or pdk_name == '':
                pdk_name = f'Unnamed Paddock {unnamed_pdk_count+1}'
                unnamed_pdk_count+=1
            pdk_area = round(pdk.geometry().area()/10000, 2)# Hectares
            # get all waterpoints which fall inside the current paddock
            waterpoint_geoms = [wp.geometry() for wp in wpt_lyr.getFeatures() if wp.geometry().within(pdk.geometry())]
            if waterpoint_geoms:
                buffer_distance = band_width
                band_count = 0
                band_intersects = True
                # dissolved buffer of all paddock waterpoints
                # this will be the first 'band' (just a buffer around waterpoint)
                first_buffer = QgsGeometry.unaryUnion([geom.buffer(buffer_distance, 25) for geom in waterpoint_geoms])
                # print(f'Band count: {band_count}')
                if band_count == 0:
                    clipped_to_pdk = first_buffer.intersection(pdk.geometry())
                    area_ha = round(clipped_to_pdk.area()/10000, 2)
                    pcnt = round((clipped_to_pdk.area()/pdk.geometry().area())*100, 7)
                    feat = QgsFeature(flds)
                    feat.setGeometry(clipped_to_pdk)
                    feat.setAttributes([pdk_name, pdk_area, f'0-{buffer_distance}m', buffer_distance, area_ha, pcnt])
                    feats.append(feat)
                    buffer_distance+=band_width
                    band_count+=1
                # these will be 'band buffers' composed of difference between current & previous buffer
                # break the loop if the last buffer does not intersect the paddock
                while band_intersects and band_count < 500:
                    # print(f'Band count: {band_count}')
                    outer_ring = QgsGeometry.unaryUnion([geom.buffer(buffer_distance, 25) for geom in waterpoint_geoms])
                    inner_ring = QgsGeometry.unaryUnion([geom.buffer(buffer_distance-band_width, 25) for geom in waterpoint_geoms])
                    dtw_band = outer_ring.difference(inner_ring)
                    if dtw_band.intersects(pdk.geometry()):
                        clipped_to_pdk = dtw_band.intersection(pdk.geometry())
                        area_ha = round(clipped_to_pdk.area()/10000, 2)
                        pcnt = round((clipped_to_pdk.area()/pdk.geometry().area())*100, 7)
                        feat = QgsFeature(flds)
                        feat.setGeometry(clipped_to_pdk)
                        feat.setAttributes([pdk_name,
                                            pdk_area,
                                            f'{buffer_distance-band_width}-{buffer_distance}m',
                                            buffer_distance,
                                            area_ha,
                                            pcnt])
                        feats.append(feat)
                        buffer_distance+=band_width
                        band_count+=1
                    else:
                        band_intersects = False
                pdk_max_dist_to_water = band_count*band_width
                pdk_max_dtws[pdk_name] = pdk_max_dist_to_water
        
        for ft in feats:
            max_dtw = pdk_max_dtws[ft['Pdk Name']]
            atts = ft.attributes()
            atts.append(max_dtw)
            ft.setAttributes(atts)
            sink.addFeature(ft, QgsFeatureSink.FastInsert)
        
        post_processor = self.postProcessorClassFactory(dest_id)
        if context.willLoadLayerOnCompletion(dest_id):
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(post_processor)
        return {'OUTPUT': dest_id}
        
    def postProcessorClassFactory(self, name):
        
        def postProcessLayer(cls_inst, layer, context, feedback):
            default_style = QgsStyle.defaultStyle()
            color_ramp = default_style.colorRamp('Spectral') #Spectral color ramp
            color_ramp.invert()
            field_index = layer.fields().lookupField('Outer dist')
            unique_values = sorted(list(layer.uniqueValues(field_index)))
            categories = []
            for value in unique_values:
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                sym_lyr = symbol.symbolLayer(0).clone()
                prop = QgsProperty()
                prop.setExpressionString("darker(@symbol_color, 150)")
                sym_lyr.setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeColor, prop)
                symbol.changeSymbolLayer(0, sym_lyr)
                category = QgsRendererCategory(value, symbol, str(value))
                categories.append(category)
            renderer = QgsCategorizedSymbolRenderer('Outer dist', categories)
            renderer.updateColorRamp(color_ramp)
            layer.setRenderer(renderer)
            
            feedback.pushInfo(f'{layer.name()} post processed')
            
        def create(cls):
            cls.instance = cls()
            return cls.instance
            
        proc = type(f'{name}_processor', (QgsProcessingLayerPostProcessorInterface,), {'postProcessLayer': postProcessLayer,
                                                                                        'create': create})
        proc_inst = proc.create(proc)
        return proc_inst