from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsFeature, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsVectorLayer, QgsField, QgsFields,
                        QgsCoordinateReferenceSystem,
                        QgsGeometry,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField,
                        QgsProcessingParameterString,
                        QgsProcessingParameterFileDestination,
                        QgsProcessingMultiStepFeedback)
                        
import processing
                       
class TimePerWateredBand(QgsProcessingAlgorithm):
    PADDOCK = 'PADDOCK'
    COLLAR = 'COLLAR'
    GPS_LAYER = 'GPS_LAYER'
    DATETIME_FIELD = 'DATETIME_FIELD'
    DTW_FIELD = 'DTW_FIELD'
    DTW_LAYER = 'DTW_LAYER'
    WATERED_BAND_FIELD = 'WATERED_BAND_FIELD'
    OUTPUT_XLSX = 'OUTPUT_XLSX'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "timeperwateredband"

    def displayName(self):
        return "Time per watered band"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Calculate time spent in each band (e.g. 1000-1500m) of a Watered Bands\
                layer. Input layers are a GPS collar point layer with a datetime\
                field and a distance to water field. Output is written to an\
                Excel spreadsheet. Results are calculated for each date in the\
                input collar point layer and written as a separate row in the spreadsheet.\
                A final row is written which contains results for all dates in the\
                collar period."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.PADDOCK, 'Paddock Name'))
        
        self.addParameter(QgsProcessingParameterString(self.COLLAR, 'Collar ID'))
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.GPS_LAYER,
            "GPS collar point layer",
            [QgsProcessing.TypeVectorPoint]))
            
        self.addParameter(QgsProcessingParameterField(
            self.DATETIME_FIELD,
            'Field containing QDateTime attribute',
            defaultValue='q_datetime',
            parentLayerParameterName=self.GPS_LAYER,
            type=QgsProcessingParameterField.DateTime))
            
        self.addParameter(QgsProcessingParameterField(
            self.DTW_FIELD,
            'Field containing distance to water attribute',
            defaultValue='Dist to nearest water m',
            parentLayerParameterName=self.GPS_LAYER,
            type=QgsProcessingParameterField.Numeric))
            
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.DTW_LAYER,
            "Watered bands layer",
            [QgsProcessing.TypeVectorPolygon]))
            
        self.addParameter(QgsProcessingParameterField(
            self.WATERED_BAND_FIELD,
            'Field containing distance to water attribute',
            defaultValue='DTW Band',
            parentLayerParameterName=self.DTW_LAYER,
            type=QgsProcessingParameterField.String))
            
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_XLSX,
            'Output Collar Spreadsheet',
            'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))
 
    def processAlgorithm(self, parameters, context, model_feedback):
        
        feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        
        paddock = self.parameterAsString(parameters, self.PADDOCK, context)
        
        collar_id = self.parameterAsString(parameters, self.COLLAR, context)
        
        collar_lyr = self.parameterAsSource(parameters, self.GPS_LAYER, context)
        
        datetime_fields = self.parameterAsFields(parameters, self.DATETIME_FIELD, context)
        if not datetime_fields:
            return {}
        datetime_field = datetime_fields[0]
        
        dtw_fields = self.parameterAsFields(parameters, self.DTW_FIELD, context)
        if not dtw_fields:
            return {}
        dtw_field = dtw_fields[0]
        
        band_lyr = self.parameterAsSource(parameters, self.DTW_LAYER, context)
        
        watered_band_fields = self.parameterAsFields(parameters, self.WATERED_BAND_FIELD, context)
        if not watered_band_fields:
            return {}
        watered_band_field = watered_band_fields[0]
        
        feedback.setCurrentStep(1)
        feedback.pushInfo('Preparing data')
        
        aligned_layers = self.align_input_layers_crs(collar_lyr, band_lyr, context.transformContext())
        gps_lyr = aligned_layers[0]
        feedback.pushInfo(f'GPS Layer CRS: {gps_lyr.crs()}')
        dtw_band_lyr = aligned_layers[1]
        feedback.pushInfo(f'DTW Layer CRS: {dtw_band_lyr.crs()}')
        
        output_path = self.parameterAsString(parameters, self.OUTPUT_XLSX, context)
        
        all_bands = sorted(dtw_band_lyr.uniqueValues(dtw_band_lyr.fields().lookupField(watered_band_field)))
        
        all_dates = list(set([v.date() for v in gps_lyr.uniqueValues(gps_lyr.fields().lookupField(datetime_field))]))
            
        temp_lyr = QgsVectorLayer('None', '', 'memory')
        temp_flds = QgsFields()
        temp_flds.append(QgsField('Paddock', QVariant.String))
        temp_flds.append(QgsField('Collar ID', QVariant.String))
        temp_flds.append(QgsField('Date', QVariant.String))
        temp_flds.append(QgsField('Total Time (hrs)', QVariant.Double))
        for i, band in enumerate(all_bands):
            pcnt = ((i+1)/len(all_bands))*100
            feedback.setProgress(pcnt)
            temp_flds.append(QgsField(band, QVariant.Double))
        temp_flds.append(QgsField('Check Sum', QVariant.Double))
        temp_lyr.dataProvider().addAttributes(temp_flds)
        temp_lyr.updateFields()
        output_feats = []

        feedback.setCurrentStep(2)
        feedback.pushInfo('Calculating date info')
        
        #Incrementally sum daily time ranges (will be written to last row of spreadsheet)
        all_t_ranges = 0
        
        all_dtw_band_times = {ft[watered_band_field]: 0 for ft in dtw_band_lyr.getFeatures()}
        
        total = len(all_dates)
        for idx, date in enumerate(sorted(all_dates)):############################SORTED DATE LIST
            if feedback.isCanceled():
                return {}
            pcnt = ((idx+1)/total)*100
            feedback.setProgress(pcnt)
            date_fts = [ft for ft in gps_lyr.getFeatures() if ft[datetime_field].date() == date]
            date_feats_chronological = sorted(date_fts, key=lambda ft: ft[datetime_field])

            t1 = date_feats_chronological[0][datetime_field]
            tn = date_feats_chronological[-1][datetime_field]
            t_range_secs = t1.secsTo(tn)
            all_t_ranges += t_range_secs
            t_range = t_range_secs/3600# (Hrs) Write to Total time field

            dtw_band_times = {}

            for feat in dtw_band_lyr.getFeatures():
                dtw_band_times[feat[watered_band_field]] = 0
                            
            min_idx = 0
            max_idx = len(date_feats_chronological)-1

            for i in range(min_idx, max_idx):
                if feedback.isCanceled():
                    return {}
                ft = date_feats_chronological[i]
                next_ft = date_feats_chronological[i+1]
                current_band = self.get_dtw_band_key(dtw_band_times, ft[dtw_field])
                next_band = self.get_dtw_band_key(dtw_band_times, next_ft[dtw_field])
                if current_band == next_band:
                    delta_t_mins = (ft[datetime_field].secsTo(next_ft[datetime_field]))/60
                    dtw_band_times[current_band]+=delta_t_mins
                    all_dtw_band_times[current_band]+=delta_t_mins
                elif current_band != next_band:
                    # Get dtw band feature which contains the current gps ft,
                    # construct a line between current and next ft,
                    # difference the line geom with dtw band polygon geom, to get % in each band,
                    # then calculate approximate time in each different band based on
                    # time delta between the two consecutive points.
                    current_pt = ft.geometry().asPoint() # QgsPointXY
                    next_pt = next_ft.geometry().asPoint() # QgsPointXY
                    current_dtw_band_ft = [ft for ft in dtw_band_lyr.getFeatures() if ft[watered_band_field] == current_band][0]
                    current_band_geom = current_dtw_band_ft.geometry()
                    next_dtw_band_ft = [ft for ft in dtw_band_lyr.getFeatures() if ft[watered_band_field] == next_band][0]
                    next_band_geom = next_dtw_band_ft.geometry()
                    line_geom = QgsGeometry.fromPolylineXY([current_pt, next_pt])
                    if (not line_geom.intersects(current_band_geom)) and (not line_geom.intersects(next_band_geom)):
                        feedback.pushWarning(f'GPS features {ft.id()} & {next_ft.id()} are not within a watered band in the supplied layer')####
                    line_in_current_band = line_geom.intersection(current_band_geom)
                    current_factor = line_in_current_band.length()/line_geom.length()

                    delta_t_mins = (ft[datetime_field].secsTo(next_ft[datetime_field]))/60
                    time_in_current_band = delta_t_mins*current_factor
                    time_in_next_band = delta_t_mins-time_in_current_band

                    dtw_band_times[current_band]+=time_in_current_band
                    dtw_band_times[next_band]+=time_in_next_band

                    all_dtw_band_times[current_band]+=time_in_current_band
                    all_dtw_band_times[next_band]+=time_in_next_band
                    
            # For each date, create a feature and write attributes
            feat = QgsFeature(temp_lyr.fields())
            atts = [paddock,
                    collar_id,
                    date.toString('d/M/yyyy'),
                    round(t_range, 4)]
            checksum = 0
            for k, v in dtw_band_times.items():
                atts.append(round(v/60, 2))
                checksum+=v/60
            atts.append(round(checksum, 4))
            feat.setAttributes(atts)
            output_feats.append(feat)
        #######################################################
        # Add final feature with totals for all dates in collar period
        # Retrieve from all_dtw_band_times
        # Also calc checksum for all features
        total_feat = QgsFeature(temp_lyr.fields())
        total_atts = [paddock,
                collar_id,
                'All Dates',
                round(all_t_ranges/3600, 4)]
        total_checksum = 0
        for k, v in all_dtw_band_times.items():
            total_atts.append(round(v/60, 2))
            total_checksum+=v/60
        total_atts.append(round(total_checksum, 4))
        total_feat.setAttributes(total_atts)
        output_feats.append(total_feat)
        #######################################################
        temp_lyr.dataProvider().addFeatures(output_feats)
        
        #------------------------------------------------------------------#
        feedback.setCurrentStep(3)
        feedback.pushInfo('Saving to spreadsheet')
        save_2_xlsx_params = {'LAYERS':[temp_lyr],
                                'USE_ALIAS':False,
                                'FORMATTED_VALUES':False,
                                'OUTPUT':output_path,
                                'OVERWRITE':True}
        processing.run("native:exporttospreadsheet", save_2_xlsx_params, context=context, feedback=feedback, is_child_algorithm=True)
                                
        return {self.OUTPUT_XLSX: output_path}
        
    def align_input_layers_crs(self, gps_collar_lyr, watered_band_lyr, transform_context):
        if not watered_band_lyr.sourceCrs().isGeographic() and gps_collar_lyr.sourceCrs() == watered_band_lyr.sourceCrs():
            # Both layers are projected and matching- just return copies of input layers
            gps_layer = gps_collar_lyr.materialize(QgsFeatureRequest())
            dtw_layer = watered_band_lyr.materialize(QgsFeatureRequest())
            return [gps_layer, dtw_layer]
            
        elif watered_band_lyr.sourceCrs().isGeographic() and gps_collar_lyr.sourceCrs().isGeographic():
            # Both layers are geographic so we reproject both to EPSG:9473
            gps_layer = gps_collar_lyr.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:9473'), transform_context))
            dtw_layer = watered_band_lyr.materialize(QgsFeatureRequest().setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:9473'), transform_context))
            return [gps_layer, dtw_layer]
                
        if gps_collar_lyr.sourceCrs() != watered_band_lyr.sourceCrs():
            # We need to do some reprojection
            if not watered_band_lyr.sourceCrs().isGeographic():
                # Transform gps layer to match
                gps_layer = gps_collar_lyr.materialize(QgsFeatureRequest().setDestinationCrs(watered_band_lyr.sourceCrs(), transform_context))
                dtw_layer = watered_band_lyr.materialize(QgsFeatureRequest())
                return [gps_layer, dtw_layer]
            if not gps_collar_lyr.sourceCrs().isGeographic():
                # Transform dtw layer to match
                gps_layer = watered_band_lyr.materialize(QgsFeatureRequest().setDestinationCrs(gps_collar_lyr.crs(), transform_context))
                dtw_layer = gps_collar_lyr.materialize(QgsFeatureRequest())
                return [gps_layer, dtw_layer]
            
    def get_dtw_band_key(self, in_dict, dtw):
        for k in in_dict.keys():
            inner_dist = int(k.split('-')[0])
            outer_dist = int(k.split('-')[1][:-1])
            if inner_dist < dtw < outer_dist:
                return k