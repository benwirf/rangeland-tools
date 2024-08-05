from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsFeatureSink, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterString, QgsWkbTypes,
                        QgsProcessingParameterField, QgsFields,
                        QgsProcessingParameterFeatureSink, QgsGeometry,
                        QgsProcessingParameterCrs, QgsCoordinateTransform,
                        QgsProcessingParameterFileDestination,
                        QgsVectorLayer)
import processing
import statistics
                       
class DailyMovementStats(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    PADDOCK_NAME = 'PADDOCK_NAME'
    COLLAR_ID = 'COLLAR_ID'
    DATETIME_FIELD = 'DATETIME_FIELD'
    OUTPUT = 'OUTPUT'
    OUTPUT_CRS = 'OUTPUT_CRS'
    OUTPUT_XL = 'OUTPUT_XL'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "dailymovementstats"
         
    def displayName(self):
        return "Daily movement stats"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Calculate daily distance walked statistics and write results to\
        a line layer and excel spreadsheet"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def checkParameterValues(self, parameters, context):
        crs = self.parameterAsCrs(parameters, self.OUTPUT_CRS, context)
        if crs.isGeographic():
            return False, 'Please select a projected CRS'
        return super().checkParameterValues(parameters, context)
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            "Input GPS point layer",
            [QgsProcessing.TypeVectorPoint]))
        
        self.addParameter(QgsProcessingParameterString(
            self.PADDOCK_NAME,
            'Paddock name'))

        self.addParameter(QgsProcessingParameterString(
            self.COLLAR_ID,
            'Collar ID'))
    
        self.addParameter(QgsProcessingParameterField(
            self.DATETIME_FIELD,
            'Field containing datetime attribute',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DateTime))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Daily Tracks",
            QgsProcessing.TypeVectorLine))
            
        self.addParameter(QgsProcessingParameterCrs(
            self.OUTPUT_CRS,
            'Output CRS (Projected)',
            'EPSG:9473'))
            
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_XL,
            'Output Collar Spreadsheet',
            'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))
 
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        source = self.parameterAsSource(parameters, self.INPUT, context)
        
        paddock_name = self.parameterAsString(parameters, self.PADDOCK_NAME, context)
        
        collar_id = self.parameterAsString(parameters, self.COLLAR_ID, context)
        
        datetime_fields = self.parameterAsFields(parameters, self.DATETIME_FIELD, context)
        if not datetime_fields:
            return {}
        datetime_field = datetime_fields[0]
        
        output_fields = [QgsField('Paddock', QVariant.String),# Paddock
                        QgsField('Collar_No', QVariant.String),# Collar
                        QgsField('Date', QVariant.String),# Date
                        QgsField('Total_Distance_km', QVariant.Double, len=6, prec=3),# Total distance walked
                        QgsField('Max_T_Delta_mins', QVariant.Double, len=4, prec=1),
                        QgsField('Min_Dist_m', QVariant.Double, len=6, prec=3),
                        QgsField('Max_Dist_m', QVariant.Double, len=6, prec=3),
                        QgsField('Mean_Dist_m', QVariant.Double, len=6, prec=3),
                        QgsField('Min_Speed_kph', QVariant.Double, len=5, prec=2),
                        QgsField('Max_Speed_kph', QVariant.Double, len=5, prec=2),
                        QgsField('Mean_Speed_kph', QVariant.Double, len=5, prec=2)]
        
        sink_fields = QgsFields()
        
        for fld in output_fields:
            sink_fields.append(fld)
          
        src_crs = source.sourceCrs()
        
        dest_crs = self.parameterAsCrs(parameters, self.OUTPUT_CRS, context)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               sink_fields, QgsWkbTypes.LineString, dest_crs)
        
        #Create a memory layer simply to use as input layer for exporttospreadsheet alg! WHY???????!!!
        #Even though dest_id is either an id string or a source string it doesn't work (invalid input value)!!!
        temp_lyr = QgsVectorLayer(f'LineString?crs={dest_crs.authid()}', f'Daily_Tracks_{paddock_name}_{collar_id}', 'memory')
        temp_lyr.dataProvider().addAttributes(sink_fields)
        temp_lyr.updateFields()
        ###############################################
                                               
        all_track_features = []
        
        all_dates = list(set(ft[datetime_field].date() for ft in source.getFeatures()))
        total = len(all_dates)
        for i, unique_date in enumerate(sorted(all_dates)):
            if feedback.isCanceled():
                break
            pcnt = ((i+1)/total)*100
            feedback.setProgress(round(pcnt, 1))
            date_feats = [ft for ft in source.getFeatures() if ft[datetime_field].date() == unique_date]
            if len(date_feats)<2:
                # There is only one feature for this date (calculating time gaps etc won't work)
                continue
            # Sort the features for each day period by time to ensure tracklines are constructed in the correct order
            # Otherwise distance will not be correct. This should be a redundant safeguard since fid order should also match
            # chronological order.
            date_feats_chronological = sorted(date_feats, key=lambda ft: ft[datetime_field])
            
            try:
                date_points = [ft.geometry().asMultiPoint()[0] for ft in date_feats_chronological]# Geom is MultiPointXY; PointXY is 0th element
            except TypeError:
                date_points = [ft.geometry().asPoint() for ft in date_feats_chronological]
            
            line_geom = QgsGeometry.fromPolylineXY(date_points)
            transformed_line_geom = self.transformed_geom(line_geom, src_crs, dest_crs, context.project())
            total_distance = round(transformed_line_geom.length()/1000, 3)
            ########################################################################
            # Calculate distance and speed between gps pings for each day
            day_time_gaps = []
            day_distances = []
            day_speeds = []
            ids = [f.id() for f in date_feats_chronological]
            last_id = ids[-1]
            for i, feat in enumerate(date_feats_chronological):
                if feat.id() == last_id:
                    break
                gap, dist, speed = self.calculate_distance_and_speed(feat,
                                                                    date_feats_chronological[i+1],
                                                                    datetime_field,
                                                                    src_crs,
                                                                    dest_crs,
                                                                    context.project())
                day_time_gaps.append(gap)
                day_distances.append(dist)
                day_speeds.append(speed)
            max_time_gap = round(max(day_time_gaps)/60, 1)# Divide by 60 to convert from seconds to minutes
            min_dist = round(min(day_distances), 2)
            max_dist = round(max(day_distances), 2)
            mean_dist = round(statistics.mean(day_distances), 2)
            min_speed = round(min(day_speeds), 2)
            max_speed = round(max(day_speeds), 2)
            mean_speed = round(statistics.mean(day_speeds), 2)
            ########################################################################
            y = unique_date.year()
            m = unique_date.month()
            d = unique_date.day()
            date_att = f'{y}-{m}-{d}'
            line_feat = QgsFeature(sink_fields)
            line_feat.setGeometry(transformed_line_geom)
            line_feat.setAttributes([paddock_name,
                                    collar_id,
                                    date_att,
                                    str(total_distance),
                                    max_time_gap,
                                    min_dist,
                                    max_dist,
                                    mean_dist,
                                    min_speed,
                                    max_speed,
                                    mean_speed])
            all_track_features.append(line_feat)
        #############################################################
        sink.addFeatures(all_track_features, QgsFeatureSink.FastInsert)
        #Add the features to the temp layer
        temp_lyr.dataProvider().addFeatures(all_track_features)
        ##############################################################
        if context.willLoadLayerOnCompletion(dest_id):
            details = context.layerToLoadOnCompletionDetails(dest_id)
            # If memory layer output with generic name, we will rename it
            #feedback.pushInfo(details.name)
            if details.name == 'Daily Tracks':
                details.name = f'Daily_Tracks_{paddock_name}_{collar_id}'
        results[self.OUTPUT] = dest_id
        #feedback.pushInfo(str(dest_id))
        save_to_xl_params = {'LAYERS':[temp_lyr],
                            'USE_ALIAS':False,
                            'FORMATTED_VALUES':False,
                            'OUTPUT':parameters[self.OUTPUT_XL],
                            'OVERWRITE':False}
        
        result = processing.run("native:exporttospreadsheet", save_to_xl_params, context=context, feedback=feedback, is_child_algorithm=True)        
        results[self.OUTPUT_XL] = result['OUTPUT']# Path to output spreadsheet
        
        return results
    
    def transformed_geom(self, g, in_crs, out_crs, project):
        geom = QgsGeometry.fromWkt(g.asWkt())
        xform = QgsCoordinateTransform(in_crs, out_crs, project)
        geom.transform(xform)
        return geom
        
    def calculate_distance_and_speed(self, ft1, ft2, dt_fld, in_crs, out_crs, project):
        '''
        Returns the distance and (approx) speed between 2 consecutive features
        '''
        geom1 = QgsGeometry.fromWkt(ft1.geometry().asWkt())
        geom2 = QgsGeometry.fromWkt(ft2.geometry().asWkt())
        geom1_utm = self.transformed_geom(geom1, in_crs, out_crs, project)
        geom2_utm = self.transformed_geom(geom2, in_crs, out_crs, project)
        dist = geom1_utm.distance(geom2_utm)# Meters
        ft1_dt = ft1[dt_fld]
        ft2_dt = ft2[dt_fld]
        delta_secs = ft1_dt.secsTo(ft2_dt)# Use method from QDateTime class
        speed_meters_per_second = dist/delta_secs
        speed_kmh = speed_meters_per_second*3.6
        return delta_secs, dist, speed_kmh