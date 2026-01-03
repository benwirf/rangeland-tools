from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtWidgets import (QWidget, QTableWidget, QTableWidgetItem,
                                QComboBox, QLabel, QVBoxLayout)
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsField, QgsFeature, QgsProcessing, QgsFeature,
                        QgsProcessingAlgorithm, QgsProcessingParameterFile,
                        QgsProcessingParameterVectorLayer, QgsVectorLayer,
                        QgsProcessingParameterMatrix,
                        QgsProcessingParameterFileDestination,
                        QgsProcessingMultiStepFeedback)
                        
from processing.gui.wrappers import WidgetWrapper
from osgeo import gdalnumeric
import processing
import os
                       
class TotalGrowthSummary(QgsProcessingAlgorithm):
    INPUT_FOLDER = 'INPUT_FOLDER'
    DISTRICT_LAYER = 'DISTRICT_LAYER'
    CUSTOM_PARAMS = 'CUSTOM_PARAMS'
    OUTPUT_XLSX = 'OUTPUT_XSLX'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "Total_growth_summary"
         
    def displayName(self):
        return "Total growth summary"
 
    def group(self):
        return "Feed Outlook"
 
    def groupId(self):
        return "Feed_outlook"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/growth_icon.png"))
 
    def shortHelpString(self):
        return "Stack monthly growth rasters for current financial year \
        and count pixels in 4 classes for each pastoral district.\
        Notes: Valid raster values are >=0; Water is -2"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(self.INPUT_FOLDER, 'Financial Year growth rasters (folder)', behavior=QgsProcessingParameterFile.Folder))
        self.addParameter(QgsProcessingParameterVectorLayer(self.DISTRICT_LAYER, 'Pastoral Districts', [QgsProcessing.TypeVectorAnyGeometry]))
        
        custom_params = QgsProcessingParameterMatrix(self.CUSTOM_PARAMS, '')
        custom_params.setMetadata({'widget_wrapper': {'class': CustomParametersWidgetWrapper}})
        self.addParameter(custom_params)
        
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_XLSX, 'Total growth summary spreadsheet', 'Microsoft Excel (*.xlsx);;Open Document Spreadsheet (*.ods)'))

    def checkParameterValues(self, parameters, context):
        scale_vals, regions = self.parameterAsMatrix(parameters, self.CUSTOM_PARAMS, context)
        custom_value_list = scale_vals['Custom Scale']
        if 'Custom' in regions.values() and custom_value_list == [0, 0, 0, 0]:
            return False, 'A custom scale with invalid values is set for one or more districts.'
        return super().checkParameterValues(parameters, context)
 
    def processAlgorithm(self, parameters, context, model_feedback):
        
        results = {}
        outputs = {}
        
        monthly_growth_folder = self.parameterAsString(parameters, self.INPUT_FOLDER, context)
        districts = self.parameterAsVectorLayer(parameters, self.DISTRICT_LAYER, context)
        destination_spreadsheet = parameters[self.OUTPUT_XLSX]
        ####################################################################
        '''
        scale_vals is a dictionary like: {'Northern Scale': [0, 1000, 2000, 3000], 'Southern Scale': [0, 250, 500, 1000]}
        district regions is a dictionary like:
        {'Darwin': 'Northern', 'Katherine': 'Northern', 'V.R.D.': 'Northern', 'Victoria River': 'Northern', 'Sturt Plateau': 'Northern', 'Roper': 'Northern', 'Gulf': 'Northern',
        'Barkly': 'Southern', 'Tennant Creek': 'Southern', 'Northern Alice Springs': 'Southern', 'Plenty': 'Southern', 'Southern Alice Springs': 'Southern'}
        '''
        scale_vals, regions = self.parameterAsMatrix(parameters, self.CUSTOM_PARAMS, context)
        northern_value_list = scale_vals['Northern Scale']
        southern_value_list = scale_vals['Southern Scale']
        custom_value_list = scale_vals['Custom Scale']
        #return {'scale_vals':scale_vals, 'regions':regions, 'northern_value_list':northern_value_list, 'southern_value_list':southern_value_list, 'custom_value_list':custom_value_list}
        #####################################################################
        '''...From old version
        regions = {'Barkly': 'northern',# Changed from southern to northern March 2024
            'Darwin': 'northern',
            'Gulf': 'northern',
            'Katherine': 'northern',
            'Northern Alice Springs': 'southern',
            'Plenty': 'southern',
            'Roper': 'northern',
            'Southern Alice Springs': 'southern',
            'Sturt Plateau': 'northern',
            'Tennant Creek': 'southern',
            'V.R.D.': 'northern',
            'Victoria River': 'northern'}
        '''
        ###Create temporary copy of district layer#########################
        temp_districts = QgsVectorLayer(f'polygon?&crs={districts.crs().authid()}', 'Temp_Districts', 'memory')
        temp_districts.dataProvider().addAttributes(districts.fields())
        temp_districts.updateFields()
        for f in districts.getFeatures():
            feat = QgsFeature()
            feat.setGeometry(f.geometry())
            feat.setAttributes(f.attributes())
            temp_districts.dataProvider().addFeatures([feat])
        ####################################################################
        
        input_rasters = []

        for file in os.scandir(monthly_growth_folder):
            if file.name.split('.')[-1] == 'img':
                raster_path = os.path.join(monthly_growth_folder, file.name)
                input_rasters.append(raster_path)
                
        steps = 13
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        step = 1
        
        cell_sum_params = {
                        'INPUT': input_rasters,
                        'STATISTIC':0,
                        'IGNORE_NODATA':True,
                        'REFERENCE_LAYER':input_rasters[0],
                        'OUTPUT_NODATA_VALUE':-999,
                        'OUTPUT':'TEMPORARY_OUTPUT'
                        }
        
        feedback.setCurrentStep(step)
        step+=1
        outputs['total_growth_raster'] = processing.run('native:cellstatistics', cell_sum_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['total_growth_raster'] = outputs['total_growth_raster']['OUTPUT']
        
        district_names = [f['DISTRICT'] for f in temp_districts.getFeatures()]
        
        total_growth_temp = QgsVectorLayer('Point', 'Total Growth Summary', 'memory')
        total_growth_temp.dataProvider().addAttributes([
            QgsField('District', QVariant.String),
            QgsField('Low_count', QVariant.Int),
            QgsField('Low_moderate_count', QVariant.Int),
            QgsField('Moderate_count', QVariant.Int),
            QgsField('High_count', QVariant.Int),
            QgsField('Low_percent', QVariant.Double),
            QgsField('Low_moderate_percent', QVariant.Double),
            QgsField('Moderate_percent', QVariant.Double),
            QgsField('High_percent', QVariant.Double),
            QgsField('Check_Sum', QVariant.Int)
        ])
        total_growth_temp.updateFields()
        
        for district_name in district_names:
            
            temp_districts.setSubsetString(f""""DISTRICT" LIKE '{district_name}'""")
            
            mask_params = {'INPUT':results['total_growth_raster'],
                'MASK':temp_districts,
                'SOURCE_CRS':None,
                'TARGET_CRS':None,
                'NODATA':-999,
                'ALPHA_BAND':False,
                'CROP_TO_CUTLINE':True,
                'KEEP_RESOLUTION':False,
                'SET_RESOLUTION':False,
                'X_RESOLUTION':None,
                'Y_RESOLUTION':None,
                'MULTITHREADING':False,
                'OPTIONS':'',
                'DATA_TYPE':0,
                'EXTRA':'',
                'OUTPUT':'TEMPORARY_OUTPUT'}
            
            feedback.setCurrentStep(step)
            step+=1
            outputs[f'clipped_to_{district_name}'] = processing.run("gdal:cliprasterbymasklayer", mask_params, context=context, feedback=feedback, is_child_algorithm=True)
            results[f'clipped_to_{district_name}'] = outputs[f'clipped_to_{district_name}']['OUTPUT']
            
            raster1 = gdalnumeric.LoadFile(results[f'clipped_to_{district_name}'])
            region = regions[district_name]
            count_results = self.total_growth_counts(raster1, region, northern_value_list, southern_value_list, custom_value_list)
            feat = QgsFeature()
            feat.setAttributes([
                    district_name,
                    int(count_results[0]),
                    int(count_results[1]),
                    int(count_results[2]),
                    int(count_results[3]),
                    float(count_results[4]),
                    float(count_results[5]),
                    float(count_results[6]),
                    float(count_results[7]),
                    int(count_results[8])
                ])
            total_growth_temp.dataProvider().addFeatures([feat])
        
        save_2_xlsx_params = {'LAYERS':[total_growth_temp],
            'USE_ALIAS':False,
            'FORMATTED_VALUES':False,
            'OUTPUT':destination_spreadsheet,
            'OVERWRITE':True}

        feedback.setCurrentStep(step)
        step+=1
        outputs['summary_spreadsheet'] = processing.run("native:exporttospreadsheet", save_2_xlsx_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['summary_spreadsheet'] = outputs['summary_spreadsheet']['OUTPUT']

        return results

##############################################################################
        
    def total_growth_counts(self, raster, region, northern_scale_vals, southern_scale_vals, custom_scale_vals):
        if region == 'Northern':
            # Northern Districts
            northern_val_bottom = northern_scale_vals[0] #zero
            northern_val_low = northern_scale_vals[1] # e.g. 1000
            northern_val_mod = northern_scale_vals[2] # e.g. 2000
            northern_val_high = northern_scale_vals[3] # e.g. 3000
            
            low_count = ((raster >= northern_val_bottom)&(raster <= northern_val_low)).sum()
            low_moderate_count = ((raster > northern_val_low)&(raster <= northern_val_mod)).sum()
            moderate_count = ((raster > northern_val_mod)&(raster <= northern_val_high)).sum()
            high_count = (raster > northern_val_high).sum()
            #no_data_count = (raster == -999).sum()

        elif region == 'Southern':
            # Southern Districts
            southern_val_bottom = southern_scale_vals[0] #zero
            southern_val_low = southern_scale_vals[1] # e.g. 250
            southern_val_mod = southern_scale_vals[2] # e.g. 500
            southern_val_high = southern_scale_vals[3] # e.g. 1000
            
            low_count = ((raster >= southern_val_bottom)&(raster <= southern_val_low)).sum()
            low_moderate_count = ((raster > southern_val_low)&(raster <= southern_val_mod)).sum()
            moderate_count = ((raster > southern_val_mod)&(raster <= southern_val_high)).sum()
            high_count = (raster > southern_val_high).sum()
            #no_data_count = (raster == -999).sum()
            
        elif region == 'Custom':
            # Custom scale
            custom_val_bottom = custom_scale_vals[0] #zero
            custom_val_low = custom_scale_vals[1] # e.g. 250
            custom_val_mod = custom_scale_vals[2] # e.g. 500
            custom_val_high = custom_scale_vals[3] # e.g. 1000
            
            low_count = ((raster >= custom_val_bottom)&(raster <= custom_val_low)).sum()
            low_moderate_count = ((raster > custom_val_low)&(raster <= custom_val_mod)).sum()
            moderate_count = ((raster > custom_val_mod)&(raster <= custom_val_high)).sum()
            high_count = (raster > custom_val_high).sum()
            #no_data_count = (raster == -999).sum()

        #total_pixel_count = sum([low_count, low_moderate_count, moderate_count, high_count, no_data_count])
        total_pixel_count = sum([low_count, low_moderate_count, moderate_count, high_count])

        low_percent = low_count/total_pixel_count*100
        low_moderate_percent = low_moderate_count/total_pixel_count*100
        moderate_percent = moderate_count/total_pixel_count*100
        high_percent = high_count/total_pixel_count*100
        
        check_sum = sum([low_percent, low_moderate_percent, moderate_percent, high_percent])
        
        return [low_count,
                low_moderate_count,
                moderate_count, 
                high_count,
                low_percent,
                low_moderate_percent,
                moderate_percent,
                high_percent,
                check_sum]

#############CUSTOM WIDGET WRAPPER##########################
class CustomParametersWidgetWrapper(WidgetWrapper):

    def createWidget(self):
        self.cpw = CustomDistrictScaleWidget()
        return self.cpw
        
    def value(self):
        scale_value_map = self.cpw.get_scale_cat_vals()
        district_region_map = self.cpw.get_district_regions()
        return [scale_value_map, district_region_map]

######################CUSTOM WIDGET#################################
                
class CustomDistrictScaleWidget(QWidget):
    def __init__(self):
        super(CustomDistrictScaleWidget, self).__init__()
        
        self.scale_lbl = QLabel('Regional scale categories (edit table cells to use different values):', self)
        
        self.scale_map = {'Northern Scale': ['<1000', '1000-2000', '2000-3000', '>3000'],
                            'Southern Scale': ['<250', '250-500', '500-1000', '>1000'],
                            'Custom Scale': ['<', '-', '-', '>']}
        
        self.scale_tbl = QTableWidget(self)
        self.scale_tbl.setColumnCount(5)
        self.scale_tbl.setRowCount(len(self.scale_map))
        self.scale_tbl.setHorizontalHeaderLabels(['Region Scale', 'Low', 'Low/moderate', 'Moderate', 'High'])
        for i in range(self.scale_tbl.rowCount()):
            row_items = [QTableWidgetItem(list(self.scale_map.keys())[i]),
                        QTableWidgetItem(self.scale_map.get(list(self.scale_map.keys())[i])[0]),
                        QTableWidgetItem(self.scale_map.get(list(self.scale_map.keys())[i])[1]),
                        QTableWidgetItem(self.scale_map.get(list(self.scale_map.keys())[i])[2]),
                        QTableWidgetItem(self.scale_map.get(list(self.scale_map.keys())[i])[3]),]
            for j in range(self.scale_tbl.columnCount()):
                self.scale_tbl.setItem(i, j, row_items[j])
        self.scale_tbl.resizeColumnsToContents()
        
        self.district_lbl = QLabel('District regions:', self)
        
        self.district_regions = ['Darwin', 'Katherine', 'V.R.D.', 'Sturt Plateau', 'Roper', 'Gulf',
                                'Barkly', 'Tennant Creek', 'Northern Alice Springs', 'Plenty', 'Southern Alice Springs']
        
        self.district_tbl = QTableWidget(self)
        self.district_tbl.setColumnCount(2)
        self.district_tbl.setRowCount(len(self.district_regions))
        self.district_tbl.setHorizontalHeaderLabels(['District', 'Regional Scale'])
        for i in range(self.district_tbl.rowCount()):
            cell_item = QTableWidgetItem(self.district_regions[i])
            cell_widget = QComboBox(self)
            cell_widget.addItems(['Northern', 'Southern', 'Custom'])
            if i < 6:
                cell_widget.setCurrentIndex(0)
                cell_widget.setStyleSheet('Color: green')
            else:
                cell_widget.setCurrentIndex(1)
                cell_widget.setStyleSheet('Color: orange')
            cell_widget.currentTextChanged.connect(self.region_changed)
            self.district_tbl.setItem(i, 0, cell_item)
            self.district_tbl.setCellWidget(i, 1, cell_widget)
        self.district_tbl.resizeColumnsToContents()
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.scale_lbl)
        self.layout.addWidget(self.scale_tbl)
        self.layout.addWidget(self.district_lbl)
        self.layout.addWidget(self.district_tbl)
        # self.setMinimumWidth(800)
        tbl_width = sum([self.scale_tbl.columnWidth(n) for n in range(self.scale_tbl.columnCount())])
        self.setMinimumWidth(tbl_width+50)
        
        scale_lbl_height = self.scale_lbl.height()
        scale_tbl_height = sum([self.scale_tbl.rowHeight(n) for n in range(self.scale_tbl.rowCount())])
        self.scale_tbl.setMaximumHeight(scale_tbl_height+25)
        district_lbl_height = self.district_lbl.height()
        district_tbl_height = sum([self.district_tbl.rowHeight(n) for n in range(self.district_tbl.rowCount())])
        total_height = sum([scale_lbl_height, scale_tbl_height, district_lbl_height, district_tbl_height])
        self.setMinimumHeight(total_height+50)
        
    def region_changed(self):
        for i in range(self.district_tbl.rowCount()):
            cb = self.district_tbl.cellWidget(i, 1)
            if cb.currentText() == 'Northern':
                cb.setStyleSheet('Color: green')
            elif cb.currentText() == 'Southern':
                cb.setStyleSheet('Color: orange')
            elif cb.currentText() == 'Custom':
                cb.setStyleSheet('Color: blue')
                
    def get_scale_cat_vals(self)->dict:
        '''Here we get the cutoff values for the 4 bins, parsed from the
        custom widget scale table'''
        region_scales = {}
        for r in range(self.scale_tbl.rowCount()):
            cell_3 = self.scale_tbl.item(r, 2)
            low_val = cell_3.text().split('-')[0]
            if low_val == '':
                low_val = '0'
            mod_val = cell_3.text().split('-')[1]
            if mod_val == '':
                mod_val = '0'
            cell_4 = self.scale_tbl.item(r, 4)
            high_val = cell_4.text().split('>')[1]
            if high_val == '':
                high_val = '0'
            region_scales[list(self.scale_map.keys())[r]] = [0, int(low_val), int(mod_val), int(high_val)]
        return region_scales
        
    def get_district_regions(self)->dict:
        '''Here we return a dictionary of each district and its associated
        region from the custon widget district table'''
        district_regions = {}
        for r in range(self.district_tbl.rowCount()):
            pastoral_district = self.district_tbl.item(r, 0).text()
            region = self.district_tbl.cellWidget(r, 1).currentText()
            district_regions[pastoral_district] = region
            if pastoral_district == 'V.R.D.':
                district_regions['Victoria River'] = region
        return district_regions