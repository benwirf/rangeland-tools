
from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtCore import (QCoreApplication, QVariant, Qt, QSize)
from qgis.PyQt.QtGui import (QIcon, QFont)
from qgis.PyQt.QtWidgets import (QWidget, QLabel, QCheckBox, QTableWidget, QDialog,
                                QTableWidgetItem, QVBoxLayout, QHBoxLayout, QPushButton,
                                QSpinBox, QGridLayout)

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterString,
                    QgsProcessingParameterVectorLayer, QgsProcessingParameterEnum,
                    QgsProcessingParameterBoolean, QgsProcessingParameterFolderDestination,
                    QgsProcessingParameterFile, QgsProcessingMultiStepFeedback, QgsMessageLog,
                    QgsProcessingParameterMatrix, QgsMapLayerProxyModel)
                    
from qgis.gui import (QgsMapLayerComboBox, QgsFieldComboBox)
                    
import processing
import os
import datetime
import matplotlib.pyplot as plt
import numpy as np
#from scipy.interpolate import make_interp_spline

                  
class PastureGrowthGraphs(QgsProcessingAlgorithm):
    INDIR = 'INDIR'
    FY = 'FY'
    CUSTOM_PARAMS = 'CUSTOM_PARAMS'
    SMOOTH = 'SMOOTH'
    OUTPUT_GRAPHS = 'OUTPUT_GRAPHS'
    
    msg_log = QgsMessageLog()
        
    financial_yrs = []
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "Pasture_growth_graphs"
         
    def displayName(self):
        return "Pasture growth graphs"
 
    def group(self):
        return "Feed Outlook"
 
    def groupId(self):
        return "Feed_outlook"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/graph_icon.png"))
 
    def shortHelpString(self):
        return f"Creates graphs for stacked, median monthly growth for each pastoral district by Financial Year\
        <br><br><img src='file:///{os.path.dirname(os.path.abspath(__file__))}/../images/district_graph.png' width='250'>\
        <br><br>The Monthly Growth Source Directory input parameter must contain folders named by financial year e.g.\
        2023-2024 FY such as 'R:/LID-BigData/SPATIAL DATA/PROJECTS/Northern Territory/Feed Outlook/MONTHLY GROWTH'\
        These folders should contain AussieGrass monthly growth rasters e.g. 202310.01months.growth.tot.nt.img.\
        For part financial years, the graph will plot data for whichever months are present in the current FY folder.\
        If the custom Y-Axis properties table is not used, the upper tick on the Y-Axis will be 750 for southern districts\
        with a step of 250 and 2500 for northern districts with a step of 500. Alternatively, if the Set Custom Y-Axis Properties\
        checkbox is checked, the table will be enabled, allowing full customisation of upper tick and step values\
        for each district."
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
        
    def checkParameterValues(self, parameters, context):
        growth_folder_path = self.parameterAsString(parameters, self.INDIR, context)
        fy_enum = self.parameterAsEnum(parameters, 'FY', context) # Returns index of selected option
        fy = self.financial_yrs[fy_enum] # Get string of selected option by index
        fy_path = os.path.join(growth_folder_path, fy)
        if not os.path.exists(fy_path):
            return False, 'Financial year growth folder could not be found in the specified directory'
            
        custom_param_array = self.parameterAsMatrix(parameters, self.CUSTOM_PARAMS, context)
        
        districts = ['Darwin', 'Katherine', 'Victoria River', 'V.R.D.', 'Sturt Plateau', 'Roper', 'Gulf', 'Barkly', 'Tennant Creek', 'Northern Alice Springs', 'Plenty', 'Southern Alice Springs']
        
        district_layer = custom_param_array[0]
        if district_layer.featureCount() != 11:
            return False, 'Input pastoral district layer does not contain 11 district features'
        
        district_name_field = custom_param_array[1]
        for ft in district_layer.getFeatures():
            if not ft[district_name_field] in districts:
                break
                return False, 'Selected district name field contains unexpected values. Please Check!'
        
        use_custom_y_axis_values = custom_param_array[2]
        custom_y_axis_values = custom_param_array[3]# A dictionary {'Darwin': [2500, 500]} etc
        if use_custom_y_axis_values:
            for district_name, y_axis_list in custom_y_axis_values.items():
                if (not district_name in districts) or (not 100 <= y_axis_list[0] <= 5000) or (not 50 <= y_axis_list[0] <= 1000):
                    break
                    return False, 'Custom Y-Axis values outside of acceptable range'
        
        return super().checkParameterValues(parameters, context)
   
    def initAlgorithm(self, config=None):
        self.financial_yrs.clear()
        self.addParameter(QgsProcessingParameterFile(self.INDIR, 'Monthly Growth Source Directory', behavior=QgsProcessingParameterFile.Folder))        
        #self.addParameter(QgsProcessingParameterVectorLayer(self.DISTRICTS, 'Pastoral districts', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        ###Construct list of current + 4 previous financial years to add as options to enum dropdown
        cdt = datetime.datetime.now()
        current_yr = cdt.year
        current_month = cdt.month
        if current_month>6:
            financial_year = f'{current_yr}-{current_yr+1} FY'
        elif current_month<=6:
            financial_year = f'{current_yr-1}-{current_yr} FY'
        self.financial_yrs.append(financial_year)
        self.financial_yrs.append(f'{str(int(financial_year.split("-")[0])-1)}-{str(int(financial_year.split("-")[1][:4])-1)} FY')
        self.financial_yrs.append(f'{str(int(financial_year.split("-")[0])-2)}-{str(int(financial_year.split("-")[1][:4])-2)} FY')
        self.financial_yrs.append(f'{str(int(financial_year.split("-")[0])-3)}-{str(int(financial_year.split("-")[1][:4])-3)} FY')
        self.financial_yrs.append(f'{str(int(financial_year.split("-")[0])-4)}-{str(int(financial_year.split("-")[1][:4])-4)} FY')
        
        self.addParameter(QgsProcessingParameterEnum(self.FY, 'Financial Year', self.financial_yrs, defaultValue=self.financial_yrs[0]))
        
        custom_params = QgsProcessingParameterMatrix(self.CUSTOM_PARAMS, '')
        custom_params.setMetadata({'widget_wrapper': {'class': CustomParametersWidgetWrapper}})
        self.addParameter(custom_params)
        
        self.addParameter(QgsProcessingParameterBoolean(self.SMOOTH, 'Interpolate monthly growth values for smooth graph lines (requires scipy module)'))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_GRAPHS, 'Output District Graphs'))
 
    def processAlgorithm(self, parameters, context, model_feedback):
        results = {}
        outputs = {}
        
        growth_folder_path = self.parameterAsString(parameters, self.INDIR, context)
        
        custom_param_array = self.parameterAsMatrix(parameters, self.CUSTOM_PARAMS, context)
        district_layer = custom_param_array[0]
        district_name_field = custom_param_array[1]
        use_custom_y_axis_values = custom_param_array[2]
        custom_y_axis_values = custom_param_array[3]# A dictionary {'Darwin': [2500, 500]} etc
        
        #district_layer = self.parameterAsVectorLayer(parameters, self.DISTRICTS, context)
        
        fy_enum = self.parameterAsEnum(parameters, 'FY', context) # Returns index of selected option
        fy = self.financial_yrs[fy_enum] # Get string of selected option by index
        
        out_folder_path = self.parameterAsString(parameters, self.OUTPUT_GRAPHS, context)
        smooth_graphs = self.parameterAsBoolean(parameters, self.SMOOTH, context)
        
        months = ['January', 'February',  'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

        northern_district_medians = {'Darwin': 2010, 'Katherine': 2097, 'Victoria River': 1842, 'Sturt Plateau': 2031, 'Roper': 2215, 'Gulf': 2083}
        southern_district_medians = {'Barkly': 664, 'Tennant Creek': 288, 'Northern Alice Springs': 495, 'Plenty': 328, 'Southern Alice Springs': 232}
###################################################################################################
        fy_folders = []

        fy_folders.append((f"{int(fy.split(' ')[0].split('-')[0])-2}-{int(fy.split(' ')[0].split('-')[1])-2} FY"))
        fy_folders.append((f"{int(fy.split(' ')[0].split('-')[0])-1}-{int(fy.split(' ')[0].split('-')[1])-1} FY"))
        fy_folders.append(fy)

        all_districts = list(northern_district_medians.keys()) + list(southern_district_medians.keys())

        district_results = [list() for i in range(11)]
        ############################################################################################
        # Number of processing steps will be sum of all .img files in all 3 folders
        # Addition nested loop required to get count of all input files *is there a better way???
        steps = 0
        for fy_folder in fy_folders:
            fyear = fy_folder.split(' ')[0]
            dir_path = os.path.join(growth_folder_path, fy_folder)
            file_count = [file for file in os.scandir(dir_path) if file.name.split('.')[-1] == 'img']
            if len(file_count) == 1:
                steps += len(file_count)# Just zonal stats will be run (1 alg)
            else:
                steps += len(file_count)*2 # Cell stats (sum) and zonal stats will be run (2 algs)
        steps += 11 # number of districts (1 step for each district graph)
        self.msg_log.logMessage(f'Calculated Steps {steps}')
        feedback = QgsProcessingMultiStepFeedback(steps, model_feedback)
        step = 1
        ###########################################################################################
        #TODO: set (increment) step, feedback, child alg etc. for each processing call (DONE?)
        for fy_folder in fy_folders:
            fyear = fy_folder.split(' ')[0]
            raw_inputs = []
            dir_path = os.path.join(growth_folder_path, fy_folder)
            for file in os.scandir(dir_path):
                if file.name.split('.')[-1] == 'img':
                    raster_path = os.path.join(dir_path, file.name)
                    raw_inputs.append(raster_path)
            # os.scandir() does not return files in directory order...
            # we need to return a sorted (yyyymm) version of the input list e.g. [202107, 202108, 202109] etc.
            inputs = sorted(raw_inputs)
            for i in range(len(inputs)):
                ##########Get calendar year and month###################
                calendar_yr = inputs[i].split('/')[-1].split('.')[0][:4]
                mnth_digit = inputs[i].split('/')[-1].split('.')[0][-2:]
                mnth_name = months[int(mnth_digit)-1]
                ########################################################
                # add next input to stack on each iteration e.g. [1], [1,2], [1,2,3] etc
                rstack = inputs[:i+1]
                if len(rstack) == 1:
                    # just run zonal stats on single input
                    zonal_stats_params = {'INPUT':district_layer,
                                'INPUT_RASTER':rstack[0],
                                'RASTER_BAND':1,
                                'COLUMN_PREFIX':'_',
                                'STATISTICS':[2,3],
                                'OUTPUT':'TEMPORARY_OUTPUT'}
                    
                    feedback.setCurrentStep(step)
                    step+=1
                    outputs['stats'] = processing.run("native:zonalstatisticsfb", zonal_stats_params, context=context, feedback=feedback, is_child_algorithm=True)
                    results['stats'] = outputs['stats']['OUTPUT']

                elif len(rstack) > 1:
                    # run cell stats to sum pixels of rasters in rstack, then zonal stats for mean & median for each district
                    cell_stat_params = {'INPUT':rstack,
                            'STATISTIC':0,
                            'IGNORE_NODATA':True,
                            'REFERENCE_LAYER':rstack[0],
                            'OUTPUT_NODATA_VALUE':-9999,
                            'OUTPUT':'TEMPORARY_OUTPUT'}
                    
                    feedback.setCurrentStep(step)
                    step+=1
                    outputs['cell_sum'] = processing.run("native:cellstatistics", cell_stat_params)
                    results['cell_sum'] = outputs['cell_sum']['OUTPUT']
                    
                    zonal_stats_params = {'INPUT':district_layer,
                                'INPUT_RASTER':results['cell_sum'],
                                'RASTER_BAND':1,
                                'COLUMN_PREFIX':'_',
                                'STATISTICS':[2,3],
                                'OUTPUT':'TEMPORARY_OUTPUT'}

                    feedback.setCurrentStep(step)
                    step+=1
                    outputs['stats'] = processing.run("native:zonalstatisticsfb", zonal_stats_params, context=context, feedback=feedback, is_child_algorithm=True)
                    results['stats'] = outputs['stats']['OUTPUT']
                    
                for f in context.getMapLayer(results['stats']).getFeatures():
                    for i, district in enumerate(all_districts):
                        if f[district_name_field].title() == district or (district == 'Victoria River' and f[district_name_field] == 'V.R.D.'):
                            if district in northern_district_medians.keys():
                                long_term_median = northern_district_medians[district]
                            elif district in southern_district_medians.keys():
                                long_term_median = southern_district_medians[district]
                            # Write all column values as a row/feature attributes
                            district_results[i].append([fyear, calendar_yr, mnth_name, f[district_name_field].title(), f['_mean'], long_term_median, f['_median']])
        
        for district_result in district_results:
            district_name = district_result[0][3]
            
            if district_name in northern_district_medians.keys() or district_name == 'V.R.D.':
                region = 'Northern'
            else:
                region = 'Southern'
            
            long_term_district_median = district_result[0][5]

            f_years = sorted(list(set([row[0] for row in district_result])))
            
            yr_labels = [y.replace('-', '/') for y in f_years]

            f_yr1 = [row[-1] for row in district_result if row[0] == f_years[0]]

            f_yr2 = [row[-1] for row in district_result if row[0] == f_years[1]]
            
            f_yr3 = [row[-1] for row in district_result if row[0] == f_years[2]]
            
            if len(f_yr3) == 1:
                f_yr3.insert(0, 0)
            
            y_axis_info = []
            # If use_custom_y_axis_props is checked, get the upper-tick & step values
            # for the correct (current) district and set to y_axis_info then pass the
            # list e.g. [2000, 250] to the make_plot() func
            #use_custom_y_axis_values = custom_param_array[2]
            #custom_y_axis_values = custom_param_array[3]# A dictionary {'Darwin': [2500, 500]} etc
            if use_custom_y_axis_values and custom_y_axis_values:
                if district_name == 'V.R.D.':
                    y_axis_vals = custom_y_axis_values['Victoria River']
                else:
                    y_axis_vals = custom_y_axis_values[district_name]
                y_axis_info = y_axis_vals
            
            
            graph = self.make_plot(region, district_name, long_term_district_median, f_yr1, f_yr2, f_yr3, yr_labels, y_axis_info, smooth_graphs)
            graph.gcf().set_size_inches(10, 7)
            out_png = os.path.join(out_folder_path, f'{district_name}.png')
            graph.savefig(out_png, bbox_inches='tight')
            graph.clf() # Clear figure and all axes
            
            feedback.setCurrentStep(step)
            step+=1
            model_feedback.pushInfo(f'Creating pasture growth graph for {district_name} District')
        graph.close()# This should close the window after all graphs have been created
##################################################################################################
        return results
        
        
    def make_plot(self, region, district, median, values1=[], values2=[], values3=[], labels=[], y_axis_props=[], smooth=False):
        
        max_value = max([max(values1), max(values2), max(values3)])
        self.msg_log.logMessage(f'Maximum District Value {district} ({region}): {max_value}')
        
        fy_months = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        
        district_median = [median for i in range(12)]
        
        # Median is constant (doesn't need smoothing)
        plt.plot(fy_months, district_median, label='Median', color='grey', linewidth=5)

        if smooth:
            from scipy.interpolate import make_interp_spline
            # Interpolate data points for smooth lines
            idx_for_12_months = range(len(fy_months))
            xnew_for_12_months = np.linspace(min(idx_for_12_months), max(idx_for_12_months), 300)

            idx_for_part_yr = range(len(values3))
            xnew_for_part_yr = np.linspace(min(idx_for_part_yr), max(idx_for_part_yr), 300)

            spl_1 = make_interp_spline(idx_for_12_months, values1, k=3)
            smooth_1 = spl_1(xnew_for_12_months)

            spl_2 = make_interp_spline(idx_for_12_months, values2, k=3)
            smooth_2 = spl_2(xnew_for_12_months)
            
            # k value must be less than number of given points for interpolation
            spl_3 = make_interp_spline(idx_for_part_yr, values3, k=len(values3)-1 if len(values3)<4 else 3)
            smooth_3 = spl_3(xnew_for_part_yr)
            
            # Plot smoothed lines
            plt.plot(xnew_for_12_months, smooth_1, label=labels[0], color='blue', linewidth=5)
            plt.plot(xnew_for_12_months, smooth_2, label=labels[1], color='red', linewidth=5)
            plt.plot(xnew_for_part_yr, smooth_3, label=labels[2], color='lawngreen', linewidth=5)

        else:
            # plot lines without smoothing
            plt.plot(fy_months, values1, label=labels[0], color='blue', linewidth=5)
            plt.plot(fy_months, values2, label=labels[1], color='red', linewidth=5)
            plt.plot(fy_months[:len(values3)], values3, label=labels[2], color='lawngreen', linewidth=5)

        plt.legend(fontsize=18)
        plt.xticks(fontsize=18, rotation=90)
        
        if not y_axis_props:
            # y_axis_props argument is an empty list (Set custom Y-axis properties checkbox NOT checked)
            # We use default upper tick & step values
            if region == 'Northern':
                upper_tick = 2600
                step = 500
            elif region == 'Southern':
                upper_tick = 800
                step = 250
        elif y_axis_props:
            # (Set custom Y-axis properties checkbox IS checked)
            # We use the custom upper-tick & step values passed in the y_axis_props list
            # We also need to add 50 or 100 to the upper tick value to get the correct Y-axis
            step = y_axis_props[1]
            if step%100:
                # Check if divisible by 100 (e.g. 500 etc); Probably northern district
                upper_tick = y_axis_props[0]+100
            else:
                # Not divisible by 100 (e.g. 250 etc); Probably southern district
                upper_tick = y_axis_props[0]+50
                
        self.msg_log.logMessage(f'Y-Axis Props: {region} | {district} | {upper_tick} | {step}')
        plt.yticks(np.arange(0, upper_tick, step=step), fontsize=18)
        plt.gca().yaxis.grid(linestyle='dashed')
        return plt


class CustomParametersWidgetWrapper(WidgetWrapper):

    def createWidget(self):
        self.cpw = CustomDistrictGraphWidget()
        return self.cpw
        
    def value(self):
        self.dist_lyr = self.cpw.get_district_layer()
        self.name_fld = self.cpw.get_district_name_field()
        self.use_custom_y_props = self.cpw.get_use_custom_y_axes()
        self.custom_y_props = self.cpw.get_axis_properties()
        return [self.dist_lyr, self.name_fld, self.use_custom_y_props, self.custom_y_props]

######################CUSTOM WIDGET WRAPPER STUFF#################################

class CustomDistrictGraphWidget(QWidget):
    
    def __init__(self):
        super(CustomDistrictGraphWidget, self).__init__()
        self.district_lyr_lbl = QLabel('Pastoral District Layer', self)
        self.district_lyr_cb = QgsMapLayerComboBox(self)
        self.district_lyr_cb.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.fld_lbl = QLabel('District Name Field', self)
        self.name_fld_cb = QgsFieldComboBox(self)
        
        self.table_checkbox = QCheckBox('Set Custom Y-Axis Properties')
        
        self.tbl_lbl = QLabel('District Graph Y-Axis Properties', self)
        self.district_table = QTableWidget(self)
        self.district_table.setRowCount(1)
        self.district_table.setColumnCount(3)
        self.district_table.setHorizontalHeaderLabels(['District', 'Upper Tick', 'Step'])
        self.district_table.setEnabled(False)
        self.district_table.setMinimumHeight(375)
        
        self.reload_table_btn = QPushButton(QIcon(':images/themes/default/mActionRefresh.svg'), '', self)
        self.reload_table_btn.setFixedSize(QSize(40, 40))
        self.reload_table_btn.setIconSize(QSize(35, 35))
        self.reload_table_btn.setToolTip('Refresh table')
        self.reload_table_btn.setEnabled(False)
        self.reload_table_btn.clicked.connect(self.populate_table)
        
        self.set_by_region_btn = QPushButton(QIcon(":images/themes/default/mActionEditTable.svg"), '', self)
        self.set_by_region_btn.setFixedSize(QSize(40, 40))
        self.set_by_region_btn.setIconSize(QSize(35, 35))
        self.set_by_region_btn.setToolTip('Set Tick/Step by Region')
        self.set_by_region_btn.setEnabled(False)
        self.set_by_region_btn.clicked.connect(self.table_values_by_region)
        
        self.table_checkbox.toggled.connect(self.checkbox_toggled)
        #self.name_fld_cb.fieldChanged.connect(self.populate_table)
        self.district_lyr_cb.layerChanged.connect(self.lyr_changed)
        self.lyr_changed(self.district_lyr_cb.currentLayer())
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.district_lyr_lbl)
        layout.addWidget(self.district_lyr_cb)
        layout.addWidget(self.fld_lbl)
        layout.addWidget(self.name_fld_cb)
        layout.addWidget(self.table_checkbox)
        layout.addWidget(self.tbl_lbl)
        tbl_layout = QHBoxLayout(self)
        tbl_layout.addWidget(self.district_table)
        btn_layout = QVBoxLayout(self)
        btn_layout.addWidget(self.set_by_region_btn)
        btn_layout.addWidget(self.reload_table_btn)
        btn_layout.addStretch()
        tbl_layout.addLayout(btn_layout)
        layout.addLayout(tbl_layout)
        #layout.addWidget(self.district_table)
        self.setLayout(layout)
        
        #self.populate_table()
        
    def lyr_changed(self, lyr):
        self.name_fld_cb.setLayer(lyr)
        fld_names = [fld.name().upper() for fld in lyr.fields()]
        if 'NAME' in fld_names or 'DISTRICT' in fld_names:
            if 'NAME' in fld_names:
                self.name_fld_cb.setField(lyr.fields()[fld_names.index('NAME')].name())
            elif 'DISTRICT' in fld_names:
                self.name_fld_cb.setField(lyr.fields()[fld_names.index('DISTRICT')].name())
            #self.populate_table()
            
    def checkbox_toggled(self, checked):
        self.district_table.setEnabled(checked)
        if checked:
            self.populate_table()
            self.set_by_region_btn.setEnabled(True)
            self.reload_table_btn.setEnabled(True)
        else:
            self.district_table.clearContents()
            self.district_table.setRowCount(1)
            self.set_by_region_btn.setEnabled(False)
            self.reload_table_btn.setEnabled(False)
                        
    def table_values_by_region(self):
        self.dlg = SetByRegionDialog(self.district_table)
        self.dlg.show()
    
    def populate_table(self):
        self.district_table.setRowCount(11)
        item_map = {'Darwin':[2500, 500],
                    'Katherine':[2500, 500],
                    'Victoria River':[2500, 500],
                    'Sturt Plateau':[2500, 500],
                    'Roper':[2500, 500],
                    'Gulf':[2500, 500],
                    'Barkly':[750, 250],
                    'Tennant Creek':[750, 250],
                    'Northern Alice Springs':[750, 250],
                    'Plenty':[750, 250],
                    'Southern Alice Springs':[750, 250]}
        
        for row_idx, row_items in enumerate(item_map.items()):
            row_data = [row_items[0], str(row_items[1][0]), str(row_items[1][1])]
            for col_idx, row_item in enumerate(row_data):
                self.district_table.setItem(row_idx, col_idx, QTableWidgetItem(row_item))
        self.district_table.resizeColumnToContents(0)
    
    def get_district_layer(self):
        return self.district_lyr_cb.currentLayer()
    
    def get_district_name_field(self):
        return self.name_fld_cb.currentField()
        
    def get_use_custom_y_axes(self):
        return self.table_checkbox.isChecked()
        
    def get_axis_properties(self):
        y_props = {}
        if not self.get_use_custom_y_axes():
            return y_props
        for row_idx in range(self.district_table.rowCount()):
            if self.district_table.item(row_idx, 0):
                district_name = self.district_table.item(row_idx, 0).text()
                if self.district_table.item(row_idx, 1) and self.district_table.item(row_idx, 2):
                    axis_info = [int(self.district_table.item(row_idx, 1).text()), int(self.district_table.item(row_idx, 2).text())]
                    y_props[district_name] = axis_info
        return y_props

class SetByRegionDialog(QDialog):
    
    def __init__(self, parent=None):
        self.parent = parent
        super(SetByRegionDialog, self).__init__()
        self.nthn_lbl = QLabel('Northern Region', self)
        self.nthn_lbl.setStyleSheet('color: green;')
        self.nthn_lbl.setFont(QFont('Arial', 12))
        self.nthn_tick_lbl = QLabel('Upper Tick:')
        self.nthn_tick_lbl.setFont(QFont('Arial', 10))
        self.nthn_tick_spin_box = QSpinBox(self)
        self.nthn_tick_spin_box.setRange(500, 5000)
        self.nthn_tick_spin_box.setValue(2500)
        self.nthn_tick_spin_box.setSingleStep(100)
        
        self.nthn_step_lbl = QLabel('Step:')
        self.nthn_step_lbl.setFont(QFont('Arial', 10))
        self.nthn_step_spin_box = QSpinBox(self)
        self.nthn_step_spin_box.setRange(100, 1000)
        self.nthn_step_spin_box.setValue(500)
        self.nthn_step_spin_box.setSingleStep(100)
        
        self.sthn_lbl = QLabel('Southern Region', self)
        self.sthn_lbl.setFont(QFont('Arial', 12))
        self.sthn_lbl.setStyleSheet('color: brown;')
        self.sthn_tick_lbl = QLabel('Upper Tick:')
        self.sthn_tick_lbl.setFont(QFont('Arial', 10))
        self.sthn_tick_spin_box = QSpinBox(self)
        self.sthn_tick_spin_box.setRange(50, 5000)
        self.sthn_tick_spin_box.setValue(1250)
        self.sthn_tick_spin_box.setSingleStep(50)
        
        self.sthn_step_lbl = QLabel('Step:')
        self.sthn_step_lbl.setFont(QFont('Arial', 10))
        self.sthn_step_spin_box = QSpinBox(self)
        self.sthn_step_spin_box.setRange(50, 500)
        self.sthn_step_spin_box.setValue(250)
        self.sthn_step_spin_box.setSingleStep(50)
        
        self.ok_btn = QPushButton('OK', self)
        self.ok_btn.clicked.connect(self.set_by_region)
        self.cancel_btn = QPushButton('Close', self)
        self.cancel_btn.clicked.connect(lambda: self.close())
        
        self.layout = QGridLayout(self)
        self.layout.addWidget(self.nthn_lbl, 0, 0, 1, 2, Qt.AlignLeft)
        self.layout.addWidget(self.nthn_tick_lbl, 1, 0, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.nthn_tick_spin_box, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.nthn_step_lbl, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.nthn_step_spin_box, 1, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.sthn_lbl, 2, 0, 1, 2, Qt.AlignLeft)
        self.layout.addWidget(self.sthn_tick_lbl, 3, 0, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.sthn_tick_spin_box, 3, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.sthn_step_lbl, 3, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.sthn_step_spin_box, 3, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.ok_btn, 4, 2, 1, 1)
        self.layout.addWidget(self.cancel_btn, 4, 3, 1, 1)

    def set_by_region(self):
        if not self.parent or not isinstance(self.parent, QTableWidget):
            return
        northern_upper_tick = self.nthn_tick_spin_box.value()
        northern_step = self.nthn_step_spin_box.value()
        southern_upper_tick = self.sthn_tick_spin_box.value()
        southern_step = self.sthn_step_spin_box.value()
        # parent object is QTableWidget
        self.parent.setRowCount(11)
        item_map = {'Darwin':[northern_upper_tick, northern_step],
                    'Katherine':[northern_upper_tick, northern_step],
                    'Victoria River':[northern_upper_tick, northern_step],
                    'Sturt Plateau':[northern_upper_tick, northern_step],
                    'Roper':[northern_upper_tick, northern_step],
                    'Gulf':[northern_upper_tick, northern_step],
                    'Barkly':[southern_upper_tick,southern_step],
                    'Tennant Creek':[southern_upper_tick, southern_step],
                    'Northern Alice Springs':[southern_upper_tick, southern_step],
                    'Plenty':[southern_upper_tick, southern_step],
                    'Southern Alice Springs':[southern_upper_tick, southern_step]}
        
        for row_idx, row_items in enumerate(item_map.items()):
            row_data = [row_items[0], str(row_items[1][0]), str(row_items[1][1])]
            for col_idx, row_item in enumerate(row_data):
                self.parent.setItem(row_idx, col_idx, QTableWidgetItem(row_item))
        self.parent.resizeColumnToContents(0)
        