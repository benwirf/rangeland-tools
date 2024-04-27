from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (NULL, QgsField, QgsFields, QgsFeature, QgsFeatureSink,
                        QgsFeatureRequest, QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField,
                        QgsProcessingParameterFileDestination,
                        QgsProcessingParameterFeatureSink,
                        QgsGeometry, QgsSpatialIndex,
                        QgsCoordinateTransform, QgsWkbTypes,
                        QgsProcessingMultiStepFeedback)
                        
import processing

import os
                       
class CarryingCapacitySummary(QgsProcessingAlgorithm):
    LAND_TYPES = 'LAND_TYPES'
    OUTPUT_FIELDS = 'OUTPUT_FIELDS'
    LAND_TYPE_FIELD = 'LAND_TYPE_FIELD'
    PADDOCKS = 'PADDOCKS'
    PDK_NAME_FIELD = 'PDK_NAME_FIELD'
    WATERPOINTS = 'WATERPOINTS'
    WA_3KM_LYR = 'WA_3KM_LYR'
    WA_5KM_LYR = 'WA_5KM_LYR'
    OUTPUT = 'OUTPUT'
    XL_SUMMARY = 'XL_SUMMARY'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "carryingcapacitysummary"
         
    def displayName(self):
        return "Carrying capacity summary"
 
    def group(self):
        return "Analysis"
 
    def groupId(self):
        return "analysis"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/cc_summary_icon.png"))
 
    def shortHelpString(self):
        return "Generate spreadsheet summary of watered land type\
                areas and percentage for each paddock polygon\
                in an input paddock layer."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LAND_TYPES,
            "Land types layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterField(
            self.OUTPUT_FIELDS,
            "Fields to copy to output layer",
            parentLayerParameterName=self.LAND_TYPES,
            allowMultiple=True))
            
        self.addParameter(QgsProcessingParameterField(
            self.LAND_TYPE_FIELD,
            "Field containing unique land type name",
            parentLayerParameterName=self.LAND_TYPES,
            type=QgsProcessingParameterField.String))
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.PADDOCKS,
            "Paddock polygon layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterField(
            self.PDK_NAME_FIELD,
            "Paddock name field",
            parentLayerParameterName=self.PADDOCKS,
            type=QgsProcessingParameterField.String))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.WATERPOINTS,
            "Water points layer Note: If watered area layers are selected below, they will be used instead",
            [QgsProcessing.TypeVectorPoint], optional=True))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.WA_3KM_LYR,
            "3km watered areas",
            [QgsProcessing.TypeVectorPolygon], optional=True))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.WA_5KM_LYR,
            "5km watered areas",
            [QgsProcessing.TypeVectorPolygon], optional=True))
                        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Output layer",
            QgsProcessing.TypeVectorPolygon))
            
        self.addParameter(QgsProcessingParameterFileDestination(
            self.XL_SUMMARY,
            'Carrying capacity summary spreadsheet',
            'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))
    
    def checkParameterValues(self, parameters, context):
        wpts = self.parameterAsSource(parameters, self.WATERPOINTS, context)
        wa3 = self.parameterAsSource(parameters, self.WA_3KM_LYR, context)
        wa5 = self.parameterAsSource(parameters, self.WA_5KM_LYR, context)
        if not wpts:
            if (not wa3 or not wa5):
                return False, 'If waterpoint layer not selected\nyou must select both (3km & 5km) watered area layers'
        if (wa3 and not wa5) or (wa5 and not wa3):
            return False, 'Only one watered area layer selected;\nPlease select both or none'
        if (wpts and wa3 and wa5):
            return False, 'Please select waterpoint layer or 2 watered area layer inputs;\nAll cannot be selected at once'
        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, model_feedback):
        results = {}
        
        lt_lyr = self.parameterAsSource(parameters, self.LAND_TYPES, context)
        lt_field_names = self.parameterAsFields(parameters, self.OUTPUT_FIELDS, context)
        lt_name_fld = self.parameterAsFields(parameters, self.LAND_TYPE_FIELD, context)[0]
        pdk_lyr = self.parameterAsSource(parameters, self.PADDOCKS, context)
        pdk_name_fld = self.parameterAsFields(parameters, self.PDK_NAME_FIELD, context)[0]
        wpt_lyr = self.parameterAsSource(parameters, self.WATERPOINTS, context)
        
        wa_3km_lyr = self.parameterAsSource(parameters, self.WA_3KM_LYR, context)
        wa_5km_lyr = self.parameterAsSource(parameters, self.WA_5KM_LYR, context)

        dest_spreadsheet = parameters[self.XL_SUMMARY]
        
        # Fields with these names will be added to output layer and their values calculated
        STANDARD_ADDITIONAL_FIELD_NAMES = ['ID', 'Paddock', 'Land_Type', 'Pdk_LT_area_km2', '3km_WA_LT_area_km2', '5km_WA_LT_area_km2', 'Watered_LT_area', 'Pcnt_LT_watered',]
        
        # Remove any of the fields selected to be copied if they have the same name as any of our standard fields
        lt_fields = [fld_name for fld_name in lt_field_names if (fld_name not in STANDARD_ADDITIONAL_FIELD_NAMES and fld_name != lt_name_fld)]
        
        # Construct list of field indexes from output field names
        lt_field_indexes = [lt_lyr.fields().lookupField(fld) for fld in lt_fields]
                
        # Create a single geometry object comprising all property paddocks
        all_pdks = QgsGeometry.unaryUnion([f.geometry() for f in pdk_lyr.getFeatures()])
        
        #######################################################################
        aligned_layers = self.align_input_layers_crs(pdk_lyr, lt_lyr, wpt_lyr, context.transformContext())
        lt_lyr = aligned_layers[0]
        pdk_lyr = aligned_layers[1]
        wpt_lyr = aligned_layers[2]
        #######################################################################
        
        # Create a QgsSpatialIndex from land type layer
        land_types_index = QgsSpatialIndex(lt_lyr.getFeatures())
        
        ##########CALCULATE TOTAL OUTPUT FEATURES IN ADVANCE###################
        total_feat_count = 0
        for ft in pdk_lyr.getFeatures():
            pdk_geom = ft.geometry()
            lt_cands = land_types_index.intersects(pdk_geom.boundingBox())
            pdk_land_types = list(set([ft[lt_name_fld] for ft in lt_lyr.getFeatures(lt_cands) if ft.geometry().intersects(pdk_geom)]))
            total_feat_count += len(pdk_land_types)
        if not total_feat_count:
            return {'INFO:': 'No output features calculated'}
        #######################################################################
        ###################SET UP MULTI-STEP FEEDBACK##########################
        steps = 2
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        step = 1
        #######################################################################
        
        flds = QgsFields()
        
        flds_to_add = [QgsField('ID', QVariant.String),
                        QgsField('Paddock', QVariant.String),
                        QgsField('Land_Type', QVariant.String),
                        QgsField('Pdk_LT_area_km2', QVariant.Double, len=10, prec=5),
                        QgsField('3km_WA_LT_area_km2', QVariant.Double, len=10, prec=5),
                        QgsField('5km_WA_LT_area_km2', QVariant.Double, len=10, prec=5),
                        QgsField('Watered_LT_area', QVariant.Double, len=10, prec=5),
                        QgsField('Pcnt_LT_watered', QVariant.Double, len=10, prec=1)]
                
        for fld in flds_to_add:
            flds.append(fld)
        for fld in lt_lyr.fields():
            if fld.name() in lt_fields:
                flds.append(fld)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               flds, QgsWkbTypes.MultiPolygon, lt_lyr.sourceCrs())
                                               

        output_features = []
        ID = 1
        
        feedback.setCurrentStep(step)
        step+=1

        for pdk in pdk_lyr.getFeatures():
            if feedback.isCanceled():
                feedback.pushInfo('Algorithm was cancelled!')
                return {}
            PADDOCK_NAME = pdk[pdk_name_fld] if pdk[pdk_name_fld] != NULL else 'Un-named paddock'
            pdk_geom = pdk.geometry().makeValid()
                        
            if (wa_3km_lyr and wa_5km_lyr):
                feedback.pushInfo('Using Watered Area Layers')
                # The user has supplied 3 & 5km watered area polygon layers
                # So we get transformed watered area features which fall inside the current paddock
                # collect and set to pdk_3km_wa and pdk_5km_wa variables
                wa_3km_crs = wa_3km_lyr.sourceCrs()
                wa_5km_crs = wa_5km_lyr.sourceCrs()
                pdk_3km_wa_orig = QgsGeometry.collectGeometry([ft.geometry() for ft in wa_3km_lyr.getFeatures() if self.transformed_geom(ft.geometry(), wa_3km_crs, pdk_lyr.sourceCrs(), context.project()).intersection(pdk_geom).area() > (self.transformed_geom(ft.geometry(), wa_3km_crs, pdk_lyr.sourceCrs(), context.project()).area()/2)])
                pdk_3km_wa = self.transformed_geom(pdk_3km_wa_orig, wa_3km_crs, pdk_lyr.sourceCrs(), context.project()).intersection(pdk_geom)
                pdk_5km_wa_orig = QgsGeometry.collectGeometry([ft.geometry() for ft in wa_5km_lyr.getFeatures() if self.transformed_geom(ft.geometry(), wa_5km_crs, pdk_lyr.sourceCrs(), context.project()).intersection(pdk_geom).area() > (self.transformed_geom(ft.geometry(), wa_5km_crs, pdk_lyr.sourceCrs(), context.project()).area()/2)])
                pdk_5km_wa = self.transformed_geom(pdk_5km_wa_orig, wa_5km_crs, pdk_lyr.sourceCrs(), context.project()).intersection(pdk_geom)
            else:
                feedback.pushInfo('Using Buffered Waterpoints')
                pdk_wpts = [ft for ft in wpt_lyr.getFeatures() if ft.geometry().intersects(pdk_geom)]
                # We need to construct the watered areas by buffering the waterpoints which are within the current paddock
                buffers_3km = [ft.geometry().buffer(3000, 25) for ft in pdk_wpts]
                dissolved_3km_buffers = QgsGeometry.unaryUnion(buffers_3km)
                pdk_3km_wa = dissolved_3km_buffers.intersection(pdk_geom)
                ###########################################################CONVERT GEOMETRY COLLECTION*********************
                pdk_3km_wa.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
                buffers_5km = [ft.geometry().buffer(5000, 25) for ft in pdk_wpts]
                dissolved_5km_buffers = QgsGeometry.unaryUnion(buffers_5km)
                pdk_5km_wa = dissolved_5km_buffers.intersection(pdk_geom)
                ###########################################################CONVERT GEOMETRY COLLECTION*********************
                pdk_5km_wa.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
            
            pdk_lt_candidates = land_types_index.intersects(pdk_geom.boundingBox())
            
            pdk_lt_names = list(set([ft[lt_name_fld] for ft in lt_lyr.getFeatures(pdk_lt_candidates)]))
            
            for LAND_TYPE_NAME in sorted(pdk_lt_names):
                if feedback.isCanceled():
                    feedback.pushInfo('Algorithm was cancelled!')
                    return {}
                land_type_features = [ft for ft in lt_lyr.getFeatures(pdk_lt_candidates) if ft.geometry().intersects(pdk_geom) and ft[lt_name_fld] == LAND_TYPE_NAME]
                if not land_type_features:
                    continue
                # Copy attribute in source feature for each field in fields selected to be copied
                land_type_atts = [land_type_features[0][fld_name] for fld_name in lt_fields]

                lt_in_pdk = QgsGeometry.collectGeometry([ft.geometry().makeValid().intersection(pdk_geom) for ft in land_type_features])
                ###########################################################CONVERT GEOMETRY COLLECTION*********************
                lt_in_pdk.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
                PDK_LT_AREA = lt_in_pdk.area()
                ############################################################
                pdk_3km_wa_lt = QgsGeometry.collectGeometry([ft.geometry().makeValid().intersection(pdk_3km_wa) for ft in land_type_features])
                ###########################################################CONVERT GEOMETRY COLLECTION*********************
                pdk_3km_wa_lt.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
                PDK_3KM_WA_LT_AREA = pdk_3km_wa_lt.area()
                pdk_5km_wa_lt = QgsGeometry.collectGeometry([ft.geometry().makeValid().intersection(pdk_5km_wa) for ft in land_type_features])
                ###########################################################CONVERT GEOMETRY COLLECTION*********************
                pdk_5km_wa_lt.convertGeometryCollectionToSubclass(QgsWkbTypes.PolygonGeometry)
                PDK_5KM_WA_LT_AREA = pdk_5km_wa_lt.area()
                ############################################################
                # We use 50% of the area between 3 and 5km from water so...
                # subtract 3km wa from 5km wa to get 3-5km wa as a band, divide it by 2 then add it back to the 3km wa
                WATERED_LT_AREA = ((PDK_5KM_WA_LT_AREA-PDK_3KM_WA_LT_AREA)/2)+PDK_3KM_WA_LT_AREA
                PCNT_LT_WATERED = (WATERED_LT_AREA/PDK_LT_AREA)*100
                
                output_attributes = [ID,
                                    PADDOCK_NAME,
                                    LAND_TYPE_NAME,
                                    round(PDK_LT_AREA/1000000, 5),
                                    round(PDK_3KM_WA_LT_AREA/1000000, 5),
                                    round(PDK_5KM_WA_LT_AREA/1000000, 5),
                                    round(WATERED_LT_AREA/1000000, 5),
                                    round(PCNT_LT_WATERED, 1)]
                
                for att in land_type_atts:
                    output_attributes.append(att)
                
                output_feat = QgsFeature(flds)
                output_feat.setGeometry(lt_in_pdk)
                output_feat.setAttributes(output_attributes)
                
                if lt_in_pdk.wkbType() == QgsWkbTypes.MultiPolygon:
                    output_features.append(output_feat)
                else:
                    feedback.reportError(f'1 feature with id:{output_feat.id()} cannot be added\
                                            to output layer due to non-matching geometry type')
                    feedback.pushInfo(repr(lt_in_pdk))
                ID+=1
                # Calculate percentage at each iteration & set feedback progress
                pcnt = ((ID-1)/total_feat_count)*100
                feedback.setProgress(pcnt)
                
        step+=1
        
        sink.addFeatures(output_features)
        
        results[self.OUTPUT] = dest_id

        save_2_xlsx_params = {'LAYERS':[context.getMapLayer(dest_id)],
            'USE_ALIAS':False,
            'FORMATTED_VALUES':False,
            'OUTPUT':dest_spreadsheet,
            'OVERWRITE':True}
        
        feedback.setCurrentStep(step)
        step+=1
        
        results['summary_spreadsheet'] = processing.run("native:exporttospreadsheet", save_2_xlsx_params, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        return results
    
    def transformed_geom(self, geom, src_crs, dest_crs, project):
        # Copy geometry
        g = QgsGeometry().fromWkt(geom.asWkt())
        xform = QgsCoordinateTransform(src_crs, dest_crs, project)
        g.transform(xform)
        return g
        
    def align_input_layers_crs(self, paddock_layer, land_type_layer, waterpoint_layer, transform_context):
        if not waterpoint_layer:
            # User has supplied 3km & 5km watered area polygon layers
            if not paddock_layer.sourceCrs().isGeographic():
                if land_type_layer.sourceCrs() != paddock_layer.sourceCrs():
                    ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest().setDestinationCrs(paddock_layer.sourceCrs(), transform_context))
                else:
                    ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest())
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest())
                return (ltyp_lyr, pad_lyr, None)
            if not land_type_layer.sourceCrs().isGeographic():
                if paddock_layer.sourceCrs() != land_type_layer.sourceCrs():
                    pad_lyr = paddock_layer.materialize(QgsFeatureRequest().setDestinationCrs(land_type_layer.sourceCrs(), transform_context))
                else:
                    pad_lyr = paddock_layer.materialize(QgsFeatureRequest())
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest())
                return (ltyp_lyr, pad_lyr, None)
            if (paddock_layer.sourceCrs().isGeographic()) and (land_type_layer.sourceCrs().isGeographic()):
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), transform_context))
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), transform_context))
                return (ltyp_lyr, pad_lyr, None)
            #----------------------------------------
        # User has not supplied polygon watered areas and is using a waterpoint point layer
        if not paddock_layer.sourceCrs().isGeographic():
            if waterpoint_layer.sourceCrs() != paddock_layer.sourceCrs():
                wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest().setDestinationCrs(paddock_layer.sourceCrs(), transform_context))
            else:
                wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest())
            if land_type_layer.sourceCrs() != paddock_layer.sourceCrs():
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest().setDestinationCrs(paddock_layer.sourceCrs(), transform_context))
            else:
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest())
            pad_lyr = paddock_layer.materialize(QgsFeatureRequest())
            return (ltyp_lyr, pad_lyr, wp_lyr)
        if not waterpoint_layer.sourceCrs().isGeographic():
            if paddock_layer.sourceCrs() != waterpoint_layer.sourceCrs():
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest().setDestinationCrs(waterpoint_layer.sourceCrs(), transform_context))
            else:
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest())
            if land_type_layer.sourceCrs() != waterpoint_layer.sourceCrs():
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest().setDestinationCrs(waterpoint_layer.sourceCrs(), transform_context))
            else:
                ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest())
            wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest())
            return (ltyp_lyr, pad_lyr, wp_lyr)
        if not land_type_layer.sourceCrs().isGeographic():
            if paddock_layer.sourceCrs() != land_type_layer.sourceCrs():
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest().setDestinationCrs(land_type_layer.sourceCrs(), transform_context))
            else:
                pad_lyr = paddock_layer.materialize(QgsFeatureRequest())
            if waterpoint_layer.sourceCrs() != land_type_layer.sourceCrs():
                wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest().setDestinationCrs(land_type_layer.sourceCrs(), transform_context))
            else:
                wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest())
            ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest())
            return (ltyp_lyr, pad_lyr, wp_lyr)
        if (paddock_layer.sourceCrs().isGeographic()) and (waterpoint_layer.sourceCrs().isGeographic()) and (land_type_layer.sourceCrs().isGeographic()):
            pad_lyr = paddock_layer.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), transform_context))
            wp_lyr = waterpoint_layer.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), transform_context))
            ltyp_lyr = land_type_layer.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('epsg:9473'), transform_context))
            return (ltyp_lyr, pad_lyr, wp_lyr)