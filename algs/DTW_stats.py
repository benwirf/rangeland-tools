from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtCore import QCoreApplication, QVariant, QDateTime, Qt
from qgis.PyQt.QtWidgets import (QWidget, QLabel, QDateTimeEdit,
                                    QVBoxLayout, QHBoxLayout)
from qgis.core import (QgsField, QgsFeature, QgsFeatureRequest,
                        QgsProcessing, QgsProcessingAlgorithm,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterString, QgsWkbTypes,
                        QgsFields,
                        QgsProcessingParameterFileDestination,
                        QgsVectorLayer, QgsMapLayerProxyModel,
                        QgsFieldProxyModel)
from qgis.gui import (QgsMapLayerComboBox, QgsFieldComboBox)
import processing
import statistics
                       
class DistanceToWaterStats(QgsProcessingAlgorithm):
    INPUT_PARAMS = 'INPUT_PARAMS'
    PADDOCK_NAME = 'PADDOCK_NAME'
    COLLAR_ID = 'COLLAR_ID'
    OUTPUT_XL = 'OUTPUT_XL'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "distancetowaterstats"
         
    def displayName(self):
        return "Distance to water stats"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
 
    def shortHelpString(self):
        return "Calculate daily distance to water statistics and write results\
        to an excel spreadsheet.\
        Input layer is a gps collar point layer which needs to contain both\
        a QDateTime field and a distance to water field.\
        The analysis can be performed for the entire date range based on the\
        input layer, or a partial date range can be specified using the datetime\
        edit widgets provided."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def checkParameterValues(self, parameters, context):
        # TODO: Add a check for a valid datetime field
        custom_params_list = self.parameterAsMatrix(parameters, self.INPUT_PARAMS, context)
        start_datetime = custom_params_list[2]
        end_datetime = custom_params_list[3]
        if end_datetime < start_datetime:
            return False, 'Invalid datetime range. End datetime is earlier than start datetime.'
        return super().checkParameterValues(parameters, context)
   
    def initAlgorithm(self, config=None):
        
        custom_input_params = QgsProcessingParameterMatrix(self.INPUT_PARAMS, 'Input parameters')
        custom_input_params.setMetadata({'widget_wrapper': {'class': CustomInputParameterWidgetWrapper}})
        self.addParameter(custom_input_params)
        
        self.addParameter(QgsProcessingParameterString(
            self.PADDOCK_NAME,
            'Paddock name'))

        self.addParameter(QgsProcessingParameterString(
            self.COLLAR_ID,
            'Collar ID'))
            
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_XL,
            'Output Collar Spreadsheet',
            'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))
 
    def processAlgorithm(self, parameters, context, feedback):
        results = {}
        
        custom_params_list = self.parameterAsMatrix(parameters, self.INPUT_PARAMS, context)
        
        gps_collar_lyr = custom_params_list[0]
        datetime_fld = custom_params_list[1]
        start_datetime = custom_params_list[2]
        end_datetime = custom_params_list[3]
        dist_to_water_fld = custom_params_list[4]
        
        paddock_name = self.parameterAsString(parameters, self.PADDOCK_NAME, context)
        
        collar_id = self.parameterAsString(parameters, self.COLLAR_ID, context)
        
        output_fields = [QgsField('Paddock', QVariant.String),# Paddock
                        QgsField('Collar_No', QVariant.String),# Collar
                        QgsField('Date', QVariant.String),# Date
                        QgsField('Max_T_Delta_mins', QVariant.Double, len=4, prec=1),
                        QgsField('Min_DTW_m', QVariant.Double, len=6, prec=3),
                        QgsField('Max_DTW_m', QVariant.Double, len=6, prec=3),
                        QgsField('Mean_DTW_m', QVariant.Double, len=6, prec=3)]
        
        sink_fields = QgsFields()
        
        for fld in output_fields:
            sink_fields.append(fld)
        
        #Create a memory layer to use as input layer for exporttospreadsheet alg
        temp_lyr = QgsVectorLayer('None', f'Daily_DTW_Stats_{paddock_name}_{collar_id}', 'memory')
        temp_lyr.dataProvider().addAttributes(sink_fields)
        temp_lyr.updateFields()
        ###############################################
        temp_feats = []
        
        total_ft_count = gps_collar_lyr.featureCount()
        
        feedback.pushInfo(f'Total GPS features: {total_ft_count}')
        
        start_date_string = start_datetime.toString('yyyy-MM-ddThh:mm:ss')
        end_date_string = end_datetime.toString('yyyy-MM-ddThh:mm:ss')
        
        exp = f""""{datetime_fld}" >= '{start_date_string}' and "{datetime_fld}" <= '{end_date_string}'"""
        
        #feedback.pushInfo(exp)
        
        it = gps_collar_lyr.getFeatures(exp)
        
        gps_collar_feats = [gps_ft for gps_ft in it]
        
        feedback.pushInfo(f'Total GPS features filtered by date: {len(gps_collar_feats)}')
        
        all_dates = list(set(ft[datetime_fld].date() for ft in gps_collar_feats))
        total = len(all_dates)
        feedback.pushInfo(f'Total dates: {total}')
        for i, unique_date in enumerate(sorted(all_dates)):
            if feedback.isCanceled():
                break
            pcnt = ((i+1)/total)*100
            feedback.setProgress(round(pcnt, 1))
            date_feats = [ft for ft in gps_collar_feats if ft[datetime_fld].date() == unique_date]
            if len(date_feats)<2:
                # There is only one feature for this date (calculating time gaps etc won't work)
                continue
            # Sort the features for each day period by time to ensure consecutive feature pairs are constructed in the correct order
            # Otherwise time delta gaps will not be correct. This should be a redundant safeguard since fid order should also match
            # chronological order.
            date_feats_chronological = sorted(date_feats, key=lambda ft: ft[datetime_fld])
            ########################################################################
            day_time_gaps = []
            day_distances_to_water = []
            ids = [f.id() for f in date_feats_chronological]
            last_id = ids[-1]
            for j, feat in enumerate(date_feats_chronological):
                if feat.id() == last_id:
                    break
                gap, dtw  = self.gap_and_dtw(feat,
                                        date_feats_chronological[j+1],
                                        datetime_fld,
                                        dist_to_water_fld)
                day_time_gaps.append(gap)
                day_distances_to_water.append(dtw)

            max_time_gap = round(max(day_time_gaps)/60, 1)# Divide by 60 to convert from seconds to minutes
            min_dtw = round(min(day_distances_to_water), 2)
            max_dtw = round(max(day_distances_to_water), 2)
            mean_dtw = round(statistics.mean(day_distances_to_water), 2)

            ########################################################################
            y = unique_date.year()
            m = unique_date.month()
            d = unique_date.day()
            date_att = f'{y}-{m}-{d}'
            day_feat = QgsFeature(sink_fields)
            day_feat.setAttributes([paddock_name,
                                    collar_id,
                                    date_att,
                                    max_time_gap,
                                    min_dtw,
                                    max_dtw,
                                    mean_dtw])
            temp_feats.append(day_feat)
        #############################################################
        temp_lyr.dataProvider().addFeatures(temp_feats)
        ##############################################################
        save_to_xl_params = {'LAYERS':[temp_lyr],
                            'USE_ALIAS':False,
                            'FORMATTED_VALUES':False,
                            'OUTPUT':parameters[self.OUTPUT_XL],
                            'OVERWRITE':False}
        
        result = processing.run("native:exporttospreadsheet", save_to_xl_params, context=context, feedback=feedback, is_child_algorithm=True)
        results[self.OUTPUT_XL] = result['OUTPUT']# Path to output spreadsheet

        return results
        '''
        return {'Layer': gps_collar_lyr,
                'DateTime Field': datetime_fld,
                'Start DateTime': start_datetime,
                'End DateTime': end_datetime,
                'DTW Field': dist_to_water_fld,
                'Overwrite Output Spreadsheet': overwrite_xlsx}
        '''
        
    def gap_and_dtw(self, ft1, ft2, dt_fld, dtw_fld):
        '''
        Returns the distance to water for each feature
        and the time gap between each pair of consecutive features
        '''
        ft1_dt = ft1[dt_fld]
        ft2_dt = ft2[dt_fld]
        delta_secs = ft1_dt.secsTo(ft2_dt)# Use method from QDateTime class
        dtw = ft1[dtw_fld]
        return delta_secs, dtw
        
#####################CUSTOM WIDGET WRAPPER####################
class CustomInputParameterWidgetWrapper(WidgetWrapper):
    def createWidget(self):
        self.cpw = CustomInputWidget()
        return self.cpw
        
    def value(self):
        input_params = [
            self.cpw.get_layer(),
            self.cpw.get_datetime_field(),
            self.cpw.get_start_datetime(),
            self.cpw.get_end_datetime(),
            self.cpw.get_dtw_field()
        ]
        return input_params
        
#####################CUSTOM WIDGET CLASS####################
class CustomInputWidget(QWidget):
    def __init__(self):
        super(CustomInputWidget, self).__init__()
        
        self.lyr_lbl = QLabel('Input GPS point layer', self)
        self.lyr_cb = QgsMapLayerComboBox(self)
        self.lyr_cb.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.lyr_cb.layerChanged.connect(self.layer_changed)
        
        self.gps_lyr = self.lyr_cb.currentLayer()
        
        self.dt_fld_lbl = QLabel('Field containing datetime attribute', self)
        self.dt_fld_cb = QgsFieldComboBox(self)
        self.dt_fld_cb.setFilters(QgsFieldProxyModel.DateTime)
        self.dt_fld_cb.setLayer(self.lyr_cb.currentLayer())
        self.dt_fld_cb.fieldChanged.connect(self.set_widget_date_ranges)
        
        self.dtr_lbl = QLabel('Set Date/Time range for analysis', self)
        
        self.start_dt_lbl = QLabel('Start Date-Time:', self)
        self.start_dt_edit = QDateTimeEdit(self)
        self.start_dt_edit.setMinimumWidth(140)
        self.start_dt_edit.setCalendarPopup(True)
                
        self.end_dt_lbl = QLabel('End Date-Time:', self)
        self.end_dt_edit = QDateTimeEdit(self)
        self.end_dt_edit.setMinimumWidth(140)
        self.end_dt_edit.setCalendarPopup(True)

        self.dtw_fld_lbl = QLabel('Field containing distance to water attribute', self)
        self.dtw_fld_cb = QgsFieldComboBox(self)
        self.dtw_fld_cb.setFilters(QgsFieldProxyModel.Double)
        self.dtw_fld_cb.setAllowEmptyFieldName(True)
        self.dtw_fld_cb.setLayer(self.gps_lyr)
        
        if self.gps_lyr:
            self.set_widget_date_ranges()
        
        self.main_layout = QVBoxLayout(self)
        self.date_layout = QHBoxLayout(self)
        self.date_layout.addWidget(self.start_dt_lbl, False, Qt.AlignLeft)
        self.date_layout.addWidget(self.start_dt_edit, False, Qt.AlignLeft)
        self.date_layout.addStretch()
        self.date_layout.addWidget(self.end_dt_lbl, False, Qt.AlignLeft)
        self.date_layout.addWidget(self.end_dt_edit, False, Qt.AlignLeft)
        self.date_layout.addStretch()
        self.main_layout.addWidget(self.lyr_lbl)
        self.main_layout.addWidget(self.lyr_cb)
        self.main_layout.addWidget(self.dt_fld_lbl)
        self.main_layout.addWidget(self.dt_fld_cb)
        self.main_layout.addWidget(self.dtr_lbl)
        self.main_layout.addLayout(self.date_layout)
        self.main_layout.addWidget(self.dtw_fld_lbl)
        self.main_layout.addWidget(self.dtw_fld_cb)
                
    def layer_changed(self, lyr):
        if not lyr:
            return
        self.dt_fld_cb.setLayer(lyr)
        self.dtw_fld_cb.setLayer(lyr)
        self.gps_lyr = lyr
        self.set_widget_date_ranges()
        
    def set_widget_date_ranges(self):
        gps_fts = [ft for ft in self.gps_lyr.getFeatures()]
        dt_fld = self.dt_fld_cb.currentField()
        dt_fld_idx = self.gps_lyr.fields().lookupField(dt_fld)
        dt_fld_obj = self.gps_lyr.fields()[dt_fld_idx]
        if not dt_fld or not gps_fts:
            self.start_dt_edit.setMinimumDateTime(QDateTime.currentDateTime())
            self.start_dt_edit.setMaximumDateTime(QDateTime.currentDateTime())
            self.start_dt_edit.setStyleSheet('color: red')
            self.end_dt_edit.setMinimumDateTime(QDateTime.currentDateTime())
            self.end_dt_edit.setMaximumDateTime(QDateTime.currentDateTime())
            self.end_dt_edit.setStyleSheet('color: red')
            return
        self.start_dt_edit.setStyleSheet('color: black')
        self.end_dt_edit.setStyleSheet('color: black')
        first_feat = gps_fts[0]
        last_feat = gps_fts[-1]
        first_dt = first_feat[dt_fld]
        last_dt = last_feat[dt_fld]

        start_y = first_dt.date().year()
        start_m = first_dt.date().month()
        start_d = first_dt.date().day()
        
        end_y = last_dt.date().year()
        end_m = last_dt.date().month()
        end_d = last_dt.date().day()
        
        min_start_dt = QDateTime(start_y, start_m, start_d, 0, 0, 0)
        self.start_dt_edit.setMinimumDateTime(min_start_dt)
        max_start_dt = QDateTime(end_y, end_m, end_d, 0, 0, 0)
        self.start_dt_edit.setMaximumDateTime(max_start_dt)
        self.start_dt_edit.setDateTime(min_start_dt)
        
        min_end_dt = QDateTime(start_y, start_m, start_d, 23, 59, 0)
        self.end_dt_edit.setMinimumDateTime(min_end_dt)
        max_end_dt = QDateTime(end_y, end_m, end_d, 23, 59, 0)
        self.end_dt_edit.setMaximumDateTime(max_end_dt)
        self.end_dt_edit.setDateTime(max_end_dt)
    
    def get_layer(self):
        return self.gps_lyr # QgsVectorLayer object
        
    def get_datetime_field(self):
        return self.dt_fld_cb.currentField()# Field name string
        
    def get_start_datetime(self):
        return self.start_dt_edit.dateTime()
        
    def get_end_datetime(self):
        return self.end_dt_edit.dateTime()
        
    def get_dtw_field(self):
        return self.dtw_fld_cb.currentField()# Field name string