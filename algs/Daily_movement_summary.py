from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterMultipleLayers,
                        QgsProcessingParameterField, QgsFields,
                        QgsProcessingParameterFileDestination,
                        QgsVectorLayer)
from datetime import datetime
import processing
import statistics
                       
class DailyMovementSummary(QgsProcessingAlgorithm):
    INPUT_LAYERS = 'INPUT_LAYERS'
    PADDOCK_NAME_FIELD = 'PADDOCK_NAME'
    COLLAR_ID_FIELD = 'COLLAR_ID'
    DATE_FIELD = 'DATETIME_FIELD'
    OUTPUT_XL = 'OUTPUT_XL'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "dailymovementsummary"
         
    def displayName(self):
        return "Daily movement summary"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Calculate summary of daily movement statistics\
        for multiple collars and write results to an excel spreadsheet"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.INPUT_LAYERS,
            "Input layers",
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterField(
            self.PADDOCK_NAME_FIELD,
            'Field containing paddock name',
            parentLayerParameterName=self.INPUT_LAYERS,
            type=QgsProcessingParameterField.String))
        
        self.addParameter(QgsProcessingParameterField(
            self.COLLAR_ID_FIELD,
            'Field containing collar ID',
            parentLayerParameterName=self.INPUT_LAYERS,
            type=QgsProcessingParameterField.String))
    
        self.addParameter(QgsProcessingParameterField(
            self.DATE_FIELD,
            'Field containing date attribute',
            parentLayerParameterName=self.INPUT_LAYERS,
            type=QgsProcessingParameterField.String))
        
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_XL,
            'Output Summary Spreadsheet',
            'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))
 
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        source_layers = self.parameterAsLayerList(parameters, self.INPUT_LAYERS, context)
        
        paddock_field = self.parameterAsFields(parameters, self.PADDOCK_NAME_FIELD, context)[0]
        
        collar_id_field = self.parameterAsFields(parameters, self.COLLAR_ID_FIELD, context)[0]
        
        date_field = self.parameterAsFields(parameters, self.DATE_FIELD, context)[0]
        
        temp_lyr = QgsVectorLayer('None', f'{next(source_layers[0].getFeatures())[paddock_field]}_Summary', 'memory')
        
        temp_fld_list = [QgsField('Paddock', QVariant.String),
                    QgsField('Collar', QVariant.String),
                    QgsField('Start Date', QVariant.String),
                    QgsField('End Date', QVariant.String),
                    QgsField('Duration', QVariant.String),
                    QgsField('Max Daily Total (km)', QVariant.Double, len=5, prec=2),
                    QgsField('Max On', QVariant.String),
                    QgsField('Min Daily Total (km)', QVariant.Double, len=5, prec=2),
                    QgsField('Min On', QVariant.String),
                    QgsField('Mean Daily Total (km)', QVariant.Double, len=5, prec=2)]
        
        temp_flds = QgsFields()
        for fld in temp_fld_list:
            temp_flds.append(fld)
        temp_lyr.dataProvider().addAttributes(temp_flds)
        temp_lyr.updateFields()
        
        temp_feats = []
        
        for lyr in source_layers:
            feats = [ft for ft in lyr.getFeatures()]
            pdk_name = feats[0][paddock_field]
            collar_id = feats[0][collar_id_field]
            start_date = feats[0][date_field]
            # String format is 2023-05-10
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = feats[-1][date_field]
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            t_delta = str(end_dt-start_dt)
            t_delta_days = t_delta.split(',')[0]
            daily_distances = [ft['Total_distance_km'] for ft in feats[:-1]]#Slice off last features (partial days of walking)
            max_dist = max(daily_distances)
            max_dist_dates = [ft['Date'] for ft in feats if ft['Total_distance_km'] == max_dist]
            max_dist_dates_att = ','.join(max_dist_dates)
            min_dist = min(daily_distances)
            min_dist_dates = [ft['Date'] for ft in feats if ft['Total_distance_km'] == min_dist]
            min_dist_dates_att = ', '.join(min_dist_dates)
            mean_dist = statistics.mean(daily_distances)
            temp_feat = QgsFeature(temp_lyr.fields())
            atts = [pdk_name,
                    f'_{collar_id.zfill(4)}',
                    start_date,
                    end_date,
                    t_delta_days,
                    round(max_dist, 2),
                    max_dist_dates_att,
                    round(min_dist, 2),
                    min_dist_dates_att,
                    round(mean_dist, 2)]
            temp_feat.setAttributes(atts)
            temp_feats.append(temp_feat)
            
        temp_lyr.dataProvider().addFeatures(temp_feats)
        
        save_to_xlsx_params = {'LAYERS':[temp_lyr],
                                'USE_ALIAS':False,
                                'FORMATTED_VALUES':False,
                                'OUTPUT':parameters[self.OUTPUT_XL],
                                'OVERWRITE':False}
        
        result = processing.run("native:exporttospreadsheet", save_to_xlsx_params, context=context, feedback=feedback, is_child_algorithm=True)
        results[self.OUTPUT_XL] = result['OUTPUT']# Path to output spreadsheet
        
        return results