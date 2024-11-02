from qgis.PyQt.QtCore import (Qt, QObject, QVariant)

from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLabel,
                                QHBoxLayout, QToolBar, QTableWidget,
                                QCheckBox, QPushButton, QMessageBox,
                                QTableWidgetItem, QAction, QSpinBox)

from qgis.PyQt.QtGui import (QIcon, QCursor, QColor)

from qgis.core import (QgsProject, QgsFieldProxyModel, QgsMapLayerProxyModel,
                        QgsVectorLayer, QgsField, QgsGeometry, QgsFeature,
                        QgsCoordinateTransform, QgsFeatureRequest, QgsProject,
                        QgsCoordinateReferenceSystem, QgsApplication,
                        QgsRectangle, QgsCoordinateTransform, QgsWkbTypes,
                        QgsRasterLayer, QgsStyle, QgsSymbol, QgsProperty,
                        QgsSymbolLayer, QgsRendererCategory, QgsSpatialIndex,
                        QgsCategorizedSymbolRenderer, QgsFields, NULL)
                        
from qgis.gui import (QgsMapLayerComboBox, QgsFieldComboBox, QgsMapCanvas,
                        QgsFileWidget, QgsMapToolPan, QgsMapTool,
                        QgsRubberBand)

import processing
import os

class CustomWateredAreasWidget(QWidget):
    
    def __init__(self, parent=None):
        super(CustomWateredAreasWidget, self).__init__()
        self.parent = parent
        # self.setGeometry(200, 100, 850, 550)
        self.setWindowModality(Qt.ApplicationModal)
        # define nullptr temporary layer variables to hold watered area features
        self.wa3km_lyr = None
        self.wa5km_lyr = None
        self.basemap_lyr = QgsRasterLayer('crs=EPSG:3857&format&type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0', '', 'wms')
        
        self.layout = QVBoxLayout(self)
        # Input layers widget
        self.input_layers_widget = QWidget(self)
        self.input_layers_layout = QFormLayout(self.input_layers_widget)
        # Paddock layer input widgets
        self.pdk_lbl = QLabel('Paddock layer:', self)
        self.pdk_layer_mlcb = QgsMapLayerComboBox(self)
        self.pdk_layer_mlcb.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.pdk_fld_lbl = QLabel('Field containing paddock names:', self)
        self.pdk_fld_cb = QgsFieldComboBox(self)
        self.pdk_fld_cb.setFilters(QgsFieldProxyModel.String)
        self.pdk_fld_cb.fieldChanged.connect(self.paddock_name_field_changed)
        
        # Waterpoint layer input widgets
        self.waterpoint_lbl = QLabel('Water point layer:', self)
        self.waterpoint_mlcb = QgsMapLayerComboBox(self)
        self.waterpoint_mlcb.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.wp_fld_lbl = QLabel('Field containing waterpoint names:', self)
        self.wp_fld_cb = QgsFieldComboBox(self)
        self.wp_fld_cb.setFilters(QgsFieldProxyModel.String)
        self.wp_fld_cb.fieldChanged.connect(self.waterpoint_name_field_changed)

        self.input_layers_layout.addRow(self.pdk_lbl, self.pdk_layer_mlcb)
        self.input_layers_layout.addRow(self.pdk_fld_lbl, self.pdk_fld_cb)
        self.input_layers_layout.addRow(self.waterpoint_lbl, self.waterpoint_mlcb)
        self.input_layers_layout.addRow(self.wp_fld_lbl, self.wp_fld_cb)
        
        ###Canvas widget
        self.canvas_widget = QWidget(self)
        self.canvas_widget_layout = QHBoxLayout(self.canvas_widget)
        self.canvas = QgsMapCanvas(self.canvas_widget)
        #########################################
        # TRY TO IMPROVE RENDERING WHEN BASEMAP IS LOADED
        self.canvas.setCachingEnabled(True)
        
        ########################################
        self.canvas.setMinimumWidth(800)
        self.canvas.setMinimumHeight(400)
        self.canvas.setDestinationCrs(QgsProject.instance().crs())
        self.canvas_tool_bar = QToolBar('Canvas toolbar', self.canvas_widget)
        self.action_pan = QAction(QIcon(":images/themes/default/mActionPan.svg"), '', self.canvas_tool_bar)
        self.action_pan.setToolTip('Pan Map Canvas')
        self.pan_tool = QgsMapToolPan(self.canvas)
        self.action_pan.triggered.connect(self.set_pan_tool)
        self.canvas_tool_bar.addAction(self.action_pan)
        self.action_reset = QAction(QIcon(":images/themes/default/mActionZoomFullExtent.svg"), '', self.canvas_tool_bar)
        self.action_reset.setToolTip('Zoom To Full Extent')
        #self.action_reset.triggered.connect(lambda: self.canvas.zoomToFullExtent())
        
        self.canvas_tool_bar.addAction(self.action_reset)
        ###### 8-4-24
        self.action_toggle_basemap = QAction(QIcon(":images/themes/default/propertyicons/map_tools.svg"), '', self.canvas_tool_bar)
        self.action_toggle_basemap.setToolTip('Turn on/off basemap')
        self.action_toggle_basemap.setCheckable(True)
        self.action_toggle_basemap.setChecked(False)
        #self.action_toggle_basemap.toggled.connect(self.set_canvas_layers)
        self.canvas_tool_bar.addAction(self.action_toggle_basemap)
        #####
        self.canvas_tool_bar.setOrientation(Qt.Vertical)
        self.canvas_widget_layout.addWidget(self.canvas)
        self.canvas_widget_layout.addWidget(self.canvas_tool_bar)
        ###Table widget
        self.tbl_widget = QWidget(self)
        self.tbl_widget.setMinimumHeight(80)
        self.tbl_widget.setMaximumHeight(150)
        self.tbl_widget_layout = QHBoxLayout(self.tbl_widget)
        self.tbl = QTableWidget(self)
        self.tbl_tool_bar = QToolBar('Table toolbar', self.tbl_widget)
        self.action_add = QAction(QIcon(":images/themes/default/symbologyAdd.svg"), '', self.tbl_tool_bar)
        self.action_add.setToolTip('Add Paddock Watered Areas')
        self.action_add.triggered.connect(self.select_paddock)
        self.tbl_tool_bar.addAction(self.action_add)
        self.action_remove = QAction(QIcon(":images/themes/default/symbologyRemove.svg"), '', self.tbl_tool_bar)
        self.action_remove.setToolTip('Remove Selected Rows')
        self.action_remove.triggered.connect(self.remove_table_row)
        self.tbl_tool_bar.addAction(self.action_remove)
        self.tbl_tool_bar.setOrientation(Qt.Vertical)
        self.tbl_widget_layout.addWidget(self.tbl)
        self.tbl_widget_layout.addWidget(self.tbl_tool_bar)
        
        ###Checkbox widget
        self.checkbox_widget = QWidget(self)
        self.checkbox_layout = QHBoxLayout(self.checkbox_widget)
        ###JULY-2024
        self.watered_bands_checkbox = QCheckBox('Create watered bands?', self.checkbox_widget)
        self.watered_bands_spinbox_lbl = QLabel('Band width (meters)', self.checkbox_widget)
        self.watered_bands_spinbox = QSpinBox(self.checkbox_widget)
        self.watered_bands_spinbox.setMaximum(10000)
        self.watered_bands_spinbox.setMinimum(10)
        self.watered_bands_spinbox.setValue(500)
        self.watered_bands_spinbox.setSingleStep(50)
        self.watered_bands_spinbox_lbl.setEnabled(False)
        self.watered_bands_spinbox.setEnabled(False)
        self.watered_bands_checkbox.stateChanged.connect(self.manage_spinbox)
        ###JULY-2024
        self.report_checkbox = QCheckBox('Create report spreadsheet?', self.checkbox_widget)
        self.report_checkbox.setEnabled(False)
        self.checkbox_conn = self.report_checkbox.stateChanged.connect(self.manage_checkboxes)
        self.load_checkbox = QCheckBox('Load outputs?', self.checkbox_widget)
        self.load_checkbox.setCheckState(Qt.Checked)
        self.load_checkbox.setEnabled(False)
        self.checkbox_layout.addStretch()
        self.checkbox_layout.addWidget(self.watered_bands_checkbox)
        self.checkbox_layout.addWidget(self.watered_bands_spinbox_lbl)
        self.checkbox_layout.addWidget(self.watered_bands_spinbox)
        self.checkbox_layout.addStretch()
        self.checkbox_layout.addWidget(self.report_checkbox)
        self.checkbox_layout.addStretch()
        self.checkbox_layout.addWidget(self.load_checkbox)
        self.checkbox_layout.addStretch()
                
        self.file_widget = QgsFileWidget(self)
        self.file_widget.lineEdit().setPlaceholderText('Temporary Folder')
        self.file_widget.setStorageMode(QgsFileWidget.GetDirectory)
        self.file_widget_conn = self.file_widget.lineEdit().valueChanged.connect(self.manage_checkboxes)
        
        ### Outputs widget
        self.outputs_widget = QWidget(self)
        self.outputs_layout = QHBoxLayout(self.outputs_widget)
        self.close_btn = QPushButton(QIcon(':images/themes/default/mIconClose.svg'), '' , self.outputs_widget)
        self.close_btn.setFixedSize(35, 35)
        self.close_btn.setToolTip('Close Window')
        self.close_btn.clicked.connect(lambda: self.close())
        self.export_btn = QPushButton(QIcon(':images/themes/default/mActionSharingExport.svg'), '' , self.outputs_widget)
        self.export_btn.setFixedSize(35, 35)
        self.export_btn.setToolTip('Export Watered Areas')
        self.export_btn.clicked.connect(self.export)
        self.outputs_layout.addStretch()
        self.outputs_layout.addWidget(self.close_btn)
        self.outputs_layout.addWidget(self.export_btn)
        self.outputs_layout.addStretch()
                
        self.layout.addWidget(self.input_layers_widget)
        self.layout.addWidget(self.canvas_widget)
        self.layout.addWidget(self.tbl_widget)
        self.layout.addWidget(self.checkbox_widget)
        self.layout.addWidget(self.file_widget)
        self.layout.addWidget(self.outputs_widget)
        
        self.wp_lyr = self.waterpoint_mlcb.currentLayer()
        self.wp_conn1 = self.waterpoint_mlcb.layerChanged.connect(self.wp_lyr_changed)
        
        self.pdk_lyr = self.pdk_layer_mlcb.currentLayer()
        self.pdk_conn1 = self.pdk_layer_mlcb.layerChanged.connect(self.pdk_lyr_changed)
        
        self.wp_fld_cb.setLayer(self.wp_lyr)
        self.pdk_fld_cb.setLayer(self.pdk_lyr)
        
        self.canvas_layers = [self.wp_lyr, self.pdk_lyr]
        if self.canvas_layers[0] or self.canvas_layers[1]:
            self.set_canvas_layers()
        #self.canvas.zoomToFullExtent()# Added here instead of zooming to full extent when clicking waterpoints
        self.zoom_canvas()
        self.action_reset.triggered.connect(self.zoom_canvas)
        self.reset_table()
        self.action_toggle_basemap.toggled.connect(self.set_canvas_layers)# 8-4-24
        
        self.select_tool = SelectTool(self.canvas, self.pdk_lyr, self.wp_lyr, parent=self)
        self.select_tool_conn = self.select_tool.deactivated.connect(self.set_pan_tool)
        
        self.set_pan_tool()
    
    #***************************************************************************25-01-2024
    def paddock_name_field_changed(self, field_name):
        if not self.tbl.rowCount():
            return
        if self.wa3km_lyr and self.wa5km_lyr:
            wa_3km_fld_idx = self.wa3km_lyr.fields().lookupField('Pdk_Name')
            wa_5km_fld_idx = self.wa5km_lyr.fields().lookupField('Pdk_Name')
            wa_3km_att_map = {}
            wa_5km_att_map = {}
        for row in range(self.tbl.rowCount()):
            item = self.tbl.item(row, 0)
            item_data = item.data(Qt.DisplayRole)
            pdk_id = int(item_data.split('(')[1].split(')')[0])
            old_pdk_name = item_data.split('(')[1]
            feat = self.pdk_lyr.getFeature(pdk_id)
            feat_attribute = feat[field_name]
            item.setData(Qt.DisplayRole, f'{feat_attribute}({pdk_id})')
            if self.wa3km_lyr and self.wa5km_lyr:
                for wa_3km_feat in [ft for ft in self.wa3km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id]:
                    wa_3km_att_map[wa_3km_feat.id()] = {wa_3km_fld_idx: feat_attribute}
                for wa_5km_feat in [ft for ft in self.wa5km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id]:
                    wa_5km_att_map[wa_5km_feat.id()] = {wa_5km_fld_idx: feat_attribute}
        if self.wa3km_lyr and self.wa5km_lyr:
            self.wa3km_lyr.dataProvider().changeAttributeValues(wa_3km_att_map)
            self.wa5km_lyr.dataProvider().changeAttributeValues(wa_5km_att_map)
        self.tbl.resizeColumnToContents(0)
        
    def waterpoint_name_field_changed(self, field_name):
        if not self.tbl.rowCount():
            return
        if self.wa3km_lyr and self.wa5km_lyr:
            wa_3km_fld_idx = self.wa3km_lyr.fields().lookupField('Water pts')
            wa_5km_fld_idx = self.wa5km_lyr.fields().lookupField('Water pts')
            wa_3km_att_map = {}
            wa_5km_att_map = {}
        for row in range(self.tbl.rowCount()):
            new_wpt_data = []
            item = self.tbl.item(row, 1)
            if not item:
                continue
            item_data = item.data(Qt.DisplayRole)
            pdk_item = self.tbl.item(row, 0)
            if not pdk_item:
                continue
            pdk_id = int(pdk_item.data(Qt.DisplayRole).split('(')[1].split(')')[0])
            wpt_info_split = item_data.split(';')# List like ['name1(3)', 'name2(5)', 'name(6)']
            for wpt_info in wpt_info_split:
                wpt_id = int(wpt_info.split('(')[1].split(')')[0])
                wpt_ft = self.wp_lyr.getFeature(wpt_id)
                wpt_name = wpt_ft[field_name]
                new_wpt_data.append(f'{wpt_name}({wpt_id})')
            new_data = '; '.join(new_wpt_data)
            item.setData(Qt.DisplayRole, new_data)
            if self.wa3km_lyr and self.wa5km_lyr:
                for wa_3km_feat in [ft for ft in self.wa3km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id]:
                    wa_3km_att_map[wa_3km_feat.id()] = {wa_3km_fld_idx: new_data}
                for wa_5km_feat in [ft for ft in self.wa5km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id]:
                    wa_5km_att_map[wa_5km_feat.id()] = {wa_5km_fld_idx: new_data}
        if self.wa3km_lyr and self.wa5km_lyr:
            self.wa3km_lyr.dataProvider().changeAttributeValues(wa_3km_att_map)
            self.wa5km_lyr.dataProvider().changeAttributeValues(wa_5km_att_map)
        self.tbl.resizeColumnToContents(1)
    #***************************************************************************
    def manage_spinbox(self, is_checked):
        self.watered_bands_spinbox.setEnabled(is_checked)
        self.watered_bands_spinbox_lbl.setEnabled(is_checked)
        
    def manage_checkboxes(self):
        if self.file_widget.lineEdit().value() == '':
            if self.report_checkbox.checkState() == Qt.Checked:
                self.report_checkbox.setCheckState(Qt.Unchecked)
            self.report_checkbox.setEnabled(False)
            if self.load_checkbox.checkState() == Qt.Unchecked:
                self.load_checkbox.setCheckState(Qt.Checked)
            self.load_checkbox.setEnabled(False)
        elif self.file_widget.lineEdit().value() != '':
            self.report_checkbox.setEnabled(True)
            self.load_checkbox.setEnabled(True)
        
    def set_pan_tool(self):
        self.canvas.unsetMapTool(self.canvas.mapTool())
        self.canvas.setMapTool(self.pan_tool)
            
    def wp_lyr_changed(self):
        self.wp_lyr = self.waterpoint_mlcb.currentLayer()
        self.set_canvas_layers()
        #self.canvas.zoomToFullExtent()# Added here instead of zooming to full extent when clicking waterpoints
        self.zoom_canvas()#8-4-24
        
        self.wp_fld_cb.setLayer(self.wp_lyr)
        self.canvas.setMapTool(self.pan_tool)
        QObject.disconnect(self.select_tool_conn)
        self.select_tool = SelectTool(self.canvas, self.pdk_lyr, self.wp_lyr, self)
        self.select_tool_conn = self.select_tool.deactivated.connect(self.set_pan_tool)
        self.reset_table()
                
    def pdk_lyr_changed(self):
        self.pdk_lyr = self.pdk_layer_mlcb.currentLayer()
        self.set_canvas_layers()
        #self.canvas.zoomToFullExtent()# Added here instead of zooming to full extent when clicking waterpoints
        self.zoom_canvas()#8-4-24
        
        self.pdk_fld_cb.setLayer(self.pdk_lyr)
        self.canvas.setMapTool(self.pan_tool)
        self.select_tool = SelectTool(self.canvas, self.pdk_lyr, self.wp_lyr, self)
        QObject.disconnect(self.select_tool_conn)
        self.select_tool = SelectTool(self.canvas, self.pdk_lyr, self.wp_lyr, self)
        self.select_tool_conn = self.select_tool.deactivated.connect(self.set_pan_tool)
        self.reset_table()
        
    def set_canvas_layers(self):
#        print('set_canvas_layers called')
        self.canvas_layers = []
        if self.action_toggle_basemap.isChecked():
            self.canvas_layers = [self.basemap_lyr]
            if not self.pdk_lyr and not self.wp_lyr:
                self.canvas.setLayers(self.canvas_layers)
                self.canvas.zoomToFullExtent()
                return
            else:
                self.canvas_layers = [self.wp_lyr, self.pdk_lyr, self.basemap_lyr]
        elif not self.action_toggle_basemap.isChecked():
            if not self.pdk_lyr and not self.wp_lyr:
                self.canvas.setLayers(self.canvas_layers)# Should be empty list
                return
            else:
                self.canvas_layers = [self.wp_lyr, self.pdk_lyr]
        #self.canvas_layers.insert(-1, self.basemap_lyr)
        if self.wa5km_lyr:
            self.canvas_layers.insert(1, self.wa5km_lyr)
        if self.wa3km_lyr:
            self.canvas_layers.insert(1, self.wa3km_lyr)
        self.canvas.setLayers(self.canvas_layers)
        # self.canvas.zoomToFullExtent()# Removed to avoid zooming to full extent when clicking waterpoints
    
    def zoom_canvas(self):
        if not self.pdk_lyr and not self.wp_lyr:
            return
        lyr_extents = []
        if self.pdk_lyr:
            lyr_extents.append((self.pdk_lyr.extent(), self.pdk_lyr.crs()))
        if self.wp_lyr:
            lyr_extents.append((self.wp_lyr.extent(), self.wp_lyr.crs()))
        if len(lyr_extents) == 2:
            #[QgsGeometry.fromRect(r) for r in lyr_extents]
            pdk_ext_geom = self.transformed_geom(QgsGeometry.fromRect(lyr_extents[0][0]), lyr_extents[0][1], self.canvas.mapSettings().destinationCrs())
            wp_ext_geom = self.transformed_geom(QgsGeometry.fromRect(lyr_extents[1][0]), lyr_extents[1][1], self.canvas.mapSettings().destinationCrs())
            combined_geom = QgsGeometry.collectGeometry([pdk_ext_geom, wp_ext_geom])
            rect = combined_geom.boundingBox()
        elif len(lyr_extents) == 1:
            ext_geom = self.transformed_geom(QgsGeometry.fromRect(lyr_extents[0][0]), lyr_extents[0][1], self.canvas.mapSettings().destinationCrs())
            rect = ext_geom.boundingBox()
        self.canvas.zoomToFeatureExtent(rect)
            
    def select_paddock(self):
        if self.pdk_layer_mlcb.currentLayer() == None or self.waterpoint_mlcb.currentLayer() == None:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Custom Watered Areas')
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText('No water point layer selected')
            msg_box.exec()
            return
        if self.canvas.mapTool() == self.select_tool:
            self.select_tool.counter = 0
        else:
            self.canvas.setMapTool(self.select_tool)
        
    def remove_table_row(self):
        selected_indexes = self.tbl.selectedIndexes()
        selected_rows = list(set([i.row() for i in selected_indexes]))
        # print(selected_rows)
        for row in selected_rows:
            pdk_data = self.tbl.item(row, 0).data(Qt.DisplayRole)
            pdk = pdk_data.split('(')[0]
            pdk_id = int(pdk_data.split('(')[1].split(')')[0])
            #print(pdk_id)
            if self.wa3km_lyr:
                self.wa3km_lyr.dataProvider().deleteFeatures([ft.id() for ft in self.wa3km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id])
                self.wa3km_lyr.updateExtents()
                self.wa3km_lyr.triggerRepaint()
                
            if self.wa5km_lyr:
                self.wa5km_lyr.dataProvider().deleteFeatures([ft.id() for ft in self.wa5km_lyr.getFeatures() if ft['Pdk_ID'] == pdk_id])
                self.wa5km_lyr.updateExtents()
                self.wa5km_lyr.triggerRepaint()
            
        self.canvas.refresh()
        for i in sorted(selected_rows, reverse=True):
            self.tbl.removeRow(i)
        self.set_pan_tool()
        
    def reset_table(self):
        self.tbl.clear()
        self.tbl.setRowCount(0)
        self.tbl.setColumnCount(2)
        self.tbl.setHorizontalHeaderLabels(['Paddock', 'Water points'])
        if self.wa3km_lyr:
            self.canvas_layers.remove(self.wa3km_lyr)
            self.wa3km_lyr = None
        if self.wa5km_lyr:
            self.canvas_layers.remove(self.wa5km_lyr)
            self.wa5km_lyr = None
        self.set_canvas_layers()
        
    def create_paddock_watered_areas(self):
        wp_crs = self.wp_lyr.sourceCrs()
        pdk_crs = self.pdk_lyr.sourceCrs()

        if not wp_crs.isGeographic():
            # Waterpoint layer is projected, we make the watered area crs the same.
            # We will need to transform the paddock geometries to this one for clipping.
            wa_crs = wp_crs
        elif wp_crs.isGeographic():
            if not pdk_crs.isGeographic():
                # Waterpoint layer is geographic, paddock layer is projected
                # We will make the watered area layer the same as the paddock layer
                # and transform the waterpoint geometries.
                wa_crs = pdk_crs
            elif pdk_crs.isGeographic():
                # Both input layers are geographic- make watered area layer epsg:9473 GDA2020 Australian Albers
                # We will need to transform both input geometries.
                wa_crs = QgsCoordinateReferenceSystem('EPSG:9473')

        # Create 3km WA temporary layer
        if not self.wa3km_lyr:
            self.wa3km_lyr = QgsVectorLayer(f'Polygon?crs={wa_crs.authid()}', '3km_WA', 'memory')
            self.wa3km_lyr.dataProvider().addAttributes([QgsField('Pdk_Name', QVariant.String),
                                                        QgsField('Pdk_ID', QVariant.Int),
                                                        QgsField('Water_pts', QVariant.String)])
            self.wa3km_lyr.updateFields()
            # Set 3km WA symbology
            r = self.wa3km_lyr.renderer().clone()
            sym = r.symbol().symbolLayer(0)
            sym.setFillColor(QColor(166,206,227,255))
            sym.setStrokeColor(QColor(31,120,180,255))
            sym.setStrokeWidth(0.35)
            self.wa3km_lyr.setRenderer(r)
            self.wa3km_lyr.triggerRepaint()
        
        # Create 5km WA temporary layer
        if not self.wa5km_lyr:
            self.wa5km_lyr = QgsVectorLayer(f'Polygon?crs={wa_crs.authid()}', '5km_WA', 'memory')
            self.wa5km_lyr.dataProvider().addAttributes([QgsField('Pdk_Name', QVariant.String),
                                                        QgsField('Pdk_ID', QVariant.Int),
                                                        QgsField('Water_pts', QVariant.String)])
            self.wa5km_lyr.updateFields()
            # Set 5km WA symbology
            r = self.wa5km_lyr.renderer().clone()
            sym = r.symbol().symbolLayer(0)
            sym.setFillColor(QColor(178,223,138,255))
            sym.setStrokeColor(QColor(51,160,44,255))
            sym.setStrokeWidth(0.35)
            self.wa5km_lyr.setRenderer(r)
            self.wa5km_lyr.triggerRepaint()
        
        self.wa3km_lyr.dataProvider().deleteFeatures([ft.id() for ft in self.wa3km_lyr.getFeatures()])
        self.wa5km_lyr.dataProvider().deleteFeatures([ft.id() for ft in self.wa5km_lyr.getFeatures()])
        
        for row in range(self.tbl.rowCount()):
            # Get data from first cell of each row
            pdk_info = self.tbl.item(row, 0).data(Qt.DisplayRole)
            pdk_name = pdk_info.split('(')[0]
            pdk_id = int(pdk_info.split('(')[1].split(')')[0])
            pdk_ft = self.pdk_lyr.getFeature(pdk_id)
            pdk_geom = self.transformed_geom(pdk_ft.geometry(), pdk_crs, wa_crs)
            # get data from second cell of each row,
            wp_info = self.tbl.item(row, 1).data(Qt.DisplayRole)
            # extract ids as integers
            wp_ids = self.parse_waterpoints(wp_info)
            # get list of water point features
            wp_fts = [self.wp_lyr.getFeature(id) for id in wp_ids]
            # get list of waterpoint geometries
            wp_geoms = [self.transformed_geom(ft.geometry(), wp_crs, wa_crs) for ft in wp_fts]
            # collect
            all_wp_geom = QgsGeometry.collectGeometry(wp_geoms)
            # buffer 3km
            buff_geom_3km = all_wp_geom.buffer(3000.0, 25)
            # buffer 5km
            buff_geom_5km = all_wp_geom.buffer(5000.0, 25)
            # and clip with transformed paddock geometry.
            pdk_3km_wa = buff_geom_3km.intersection(pdk_geom)
            # and clip with transformed paddock geometry.
            pdk_5km_wa = buff_geom_5km.intersection(pdk_geom)
            
            # Then create features, add geometry from clipped buffers and add attributes
            # 3km
            feat_3km = QgsFeature(self.wa3km_lyr.fields())
            feat_3km.setGeometry(pdk_3km_wa)
            feat_3km.setAttributes([pdk_name, pdk_id, str(wp_info)])
            # and add feature to watered area layer.
            self.wa3km_lyr.dataProvider().addFeatures([feat_3km])
            self.wa3km_lyr.updateExtents()
            self.wa3km_lyr.triggerRepaint()
            # 5km
            feat_5km = QgsFeature(self.wa5km_lyr.fields())
            feat_5km.setGeometry(pdk_5km_wa)
            feat_5km.setAttributes([pdk_name, pdk_id, str(wp_info)])
            # and add feature to watered area layer.
            self.wa5km_lyr.dataProvider().addFeatures([feat_5km])
            self.wa5km_lyr.updateExtents()
            self.wa5km_lyr.triggerRepaint()
                        
        self.canvas.refresh()
        self.set_canvas_layers()
                        
    def transformed_geom(self, g, orig_crs, target_crs):
        geom_copy = QgsGeometry().fromWkt(g.asWkt())
        if orig_crs != target_crs:
            xform = QgsCoordinateTransform(orig_crs, target_crs, QgsProject.instance())
            geom_copy.transform(xform)
        return geom_copy
            
    def parse_waterpoints(self, data_string):
        '''extracts waterpoint ids from string contents of table item'''
        wp_ids = []
        wp_items = data_string.split(';')
        for wp in wp_items:
            wp_id = wp.split('(')[1].split(')')[0]
            wp_ids.append(int(wp_id))
        return wp_ids
        
    def export(self):
        if (not self.wa3km_lyr and not self.wa5km_lyr) or (self.wa3km_lyr.featureCount() == 0 and self.wa5km_lyr.featureCount() == 0):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Custom Watered Areas')
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText('No watered areas to export!')
            msg_box.exec()
            return
        elif self.wa3km_lyr and self.wa5km_lyr:
            # Create memory based copy of minimal WA layers
            wa_3km_output = self.wa3km_lyr.materialize(QgsFeatureRequest())
            wa_5km_output = self.wa5km_lyr.materialize(QgsFeatureRequest())
            # Add additional area fields for exporting
            wa_3km_output.dataProvider().addAttributes([QgsField('Area_m2', QVariant.Double, len=10, prec=3),
                                                        QgsField('Area_ha', QVariant.Double, len=10, prec=3),
                                                        QgsField('Area_km2', QVariant.Double, len=10, prec=5)])
            wa_3km_output.updateFields()
            wa_5km_output.dataProvider().addAttributes([QgsField('Area_m2', QVariant.Double, len=10, prec=3),
                                                        QgsField('Area_ha', QVariant.Double, len=10, prec=3),
                                                        QgsField('Area_km2', QVariant.Double, len=10, prec=5)])
            wa_5km_output.updateFields()
            # Calculate and fill area fields for each feature in both output layers
            wa_3km_flds = wa_3km_output.fields()
            wa_3km_att_map = {ft.id(): {wa_3km_flds.lookupField('Area_m2'): ft.geometry().area(), wa_3km_flds.lookupField('Area_ha'): ft.geometry().area()/10000, wa_3km_flds.lookupField('Area_km2'): ft.geometry().area()/1000000} for ft in wa_3km_output.getFeatures()}
            wa_3km_output.dataProvider().changeAttributeValues(wa_3km_att_map)
            
            wa_5km_flds = wa_5km_output.fields()
            wa_5km_att_map = {ft.id(): {wa_5km_flds.lookupField('Area_m2'): ft.geometry().area(), wa_5km_flds.lookupField('Area_ha'): ft.geometry().area()/10000, wa_5km_flds.lookupField('Area_km2'): ft.geometry().area()/1000000} for ft in wa_5km_output.getFeatures()}
            wa_5km_output.dataProvider().changeAttributeValues(wa_5km_att_map)
                        
            if self.file_widget.lineEdit().value() == '':
                # We are working with tempory outputs
                # We want to set renderer and load layers to project
                # Create report spreadsheet option is not available
                wa_3km_output.setRenderer(self.wa3km_lyr.renderer().clone())
                wa_5km_output.setRenderer(self.wa5km_lyr.renderer().clone())
                #####################DTW LAYER######################
                if self.watered_bands_checkbox.isChecked():
                    dtw_lyr = self.create_dtw_bands()
                    dtw_renderer = self.dtw_bands_renderer(dtw_lyr)
                    #print(dtw_renderer)
                    dtw_lyr.setRenderer(dtw_renderer)
                    QgsProject.instance().addMapLayers([wa_3km_output, wa_5km_output, dtw_lyr])
                ###################################################
                else:
                    QgsProject.instance().addMapLayers([wa_3km_output, wa_5km_output])
                
            elif self.file_widget.lineEdit().value():
                # We are working with file outputs
                layers_to_load = {}
                #output_paths = []
                output_dir = self.file_widget.filePath()
                if not os.path.exists(output_dir):
                    msg_box = QMessageBox(self)
                    msg_box.setText('Save path is not valid!')
                    msg_box.exec()
                    return
                    
                if self.report_checkbox.checkState() == Qt.Unchecked:
                    ret = QMessageBox.question(self, 'Custom watered areas', 'Did you want to save a report spreadsheet?')
                    if ret == QMessageBox.Yes:
                        self.report_checkbox.setCheckState(Qt.Checked)
                    
                wa_3km_output_path = os.path.join(output_dir, '3km_WA.gpkg')
                wa_5km_output_path = os.path.join(output_dir, '5km_WA.gpkg')
                if self.watered_bands_checkbox.isChecked():
                    dtw_output = self.create_dtw_bands()
                    dtw_bands_output_path = os.path.join(output_dir, 'DTW_Bands.gpkg')
                    output_layers = [wa_3km_output, wa_5km_output, dtw_output]
                    output_paths = [wa_3km_output_path, wa_5km_output_path, dtw_bands_output_path]
                    lyr_names = ['3km_WA', '5km_WA', 'dtw_bands']
                else:
                    output_layers = [wa_3km_output, wa_5km_output]
                    output_paths = [wa_3km_output_path, wa_5km_output_path]
                    lyr_names = ['3km_WA', '5km_WA']
                
                for i, path in enumerate(output_paths):
                    #output_paths.append(path)
                    save_params = {'INPUT': output_layers[i],
                                    'OUTPUT':path}
                    processing.run('native:savefeatures', save_params)
                    if self.load_checkbox.checkState() == Qt.Checked:
                        # path will be source uri for creating a QgsVectorLayer, lyr_names[i] is layer name
                        # these parameters are passed to the load_output_layer() method
                        layers_to_load[path] = lyr_names[i]
                            
                if self.report_checkbox.checkState() == Qt.Checked:
                    report_spreadsheet_path = os.path.join(output_dir, 'Watered_areas.xlsx')
                    output_paths.append(report_spreadsheet_path)
                    save_2_xlsx_params = {'LAYERS': output_layers,
                                        'USE_ALIAS':False,
                                        'FORMATTED_VALUES':False,
                                        'OUTPUT':report_spreadsheet_path,
                                        'OVERWRITE':True}
                                        
                    processing.run("native:exporttospreadsheet", save_2_xlsx_params)
                    # There is no reason to load the output spreadsheet- it will be identical to vector layers attribute tables
                
                unsuccessful = [p for p in output_paths if not os.path.exists(p)]
                if unsuccessful:
                    msg_box = QMessageBox(self)
                    msg_box.setText(f'The following layers were not correctly generated:\
                                    {repr(unsuccessful)}')
                    msg_box.exec()
                else:
                    msg_box = QMessageBox(self)
                    msg_box.setText(f'Watered areas sucessfully exported!')
                    msg_box.exec()
                
                if layers_to_load:
                    # Sort dict by layer name in reverse so 3km_WA will be above 5km_WA in layer tree
                    for (fpath, lname) in sorted(layers_to_load.items(), key=lambda i:i[1], reverse=True):
                        if os.path.exists(fpath):
                            self.load_output_layer(fpath, lname)
                
####################################DTW_BANDS##################################
    def create_dtw_bands(self):
        band_width = self.watered_bands_spinbox.value()
        dtw_band_lyr = QgsVectorLayer(f'Polygon?crs={self.wa3km_lyr.crs().authid()}', 'DTW_Bands', 'memory')
        dtw_band_flds = QgsFields()
        flds_to_add = [QgsField('Pdk Name', QVariant.String),
                        QgsField('PdkArea Ha', QVariant.Double, len=10, prec=2),
                        QgsField('DTW Band', QVariant.String),
                        QgsField('Outer dist', QVariant.Int),
                        QgsField('Area Ha', QVariant.Double, len=10, prec=2),
                        QgsField('Percent', QVariant.Double, len=10, prec=7),
                        QgsField('Max DTW', QVariant.Int)]
        for fld in flds_to_add:
            dtw_band_flds.append(fld)
        dtw_band_lyr.dataProvider().addAttributes(dtw_band_flds)
        dtw_band_lyr.updateFields()
        
        pdk_max_dtws = {}

        unnamed_pdk_count = 0
        
        feats = []
        
        for ft in self.wa3km_lyr.getFeatures():
            pdk_id = ft['Pdk_ID']
            pdk_name = ft['Pdk_Name']
            if pdk_name == NULL or pdk_name == '':
                pdk_name = f'Unnamed Paddock {unnamed_pdk_count+1}'
                unnamed_pdk_count+=1
            pdk = self.pdk_lyr.getFeature(pdk_id)
            pdk_area = round(pdk.geometry().area()/10000, 2)# Hectares
            wpt_ids = self.parse_waterpoints(ft['Water_pts'])
            waterpoint_geoms = [wp.geometry() for wp in self.wp_lyr.getFeatures(wpt_ids)]
#----------------------------
            if waterpoint_geoms:
                buffer_distance = band_width
                band_count = 0
                band_intersects = True
                # dissolved buffer of all paddock waterpoints
                # this will be the first 'band' (just a buffer around waterpoint)
                first_buffer = QgsGeometry.unaryUnion([geom.buffer(buffer_distance, 25) for geom in waterpoint_geoms])
                # print(f'Band count: {band_count}')
                if band_count == 0:
                    if first_buffer.intersects(pdk.geometry()):
                        clipped_to_pdk = first_buffer.intersection(pdk.geometry())
                        area_ha = round(clipped_to_pdk.area()/10000, 2)
                        pcnt = round((clipped_to_pdk.area()/pdk.geometry().area())*100, 7)
                        feat = QgsFeature(dtw_band_flds)
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
                        feat = QgsFeature(dtw_band_flds)
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
            success = dtw_band_lyr.dataProvider().addFeature(ft)
            
        dtw_band_lyr.updateExtents()
        return dtw_band_lyr

    def dtw_bands_renderer(self, layer):
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
        return renderer
####################################END_DTW_BANDS##################################

    def load_output_layer(self, lyr_path, lyr_name):# From layers to load dict
        v_layer = QgsVectorLayer(lyr_path, lyr_name, 'ogr')
        if not v_layer.isValid():
            msg_box = QMessageBox(self)
            msg_box.setText(f'Could not load {lyr_name};\
            Layer not valid!')
            msg_box.exec()
            return
        if '3km' in lyr_name:
            v_layer.setRenderer(self.wa3km_lyr.renderer().clone())
        elif '5km' in lyr_name:
            v_layer.setRenderer(self.wa5km_lyr.renderer().clone())
        else:
            renderer = self.dtw_bands_renderer(v_layer)
            v_layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(v_layer, False)
        QgsProject.instance().layerTreeRoot().insertLayer(0, v_layer)
                
    def closeEvent(self, e):
        if self.wa3km_lyr:
            self.wa3km_lyr = None
        if self.wa5km_lyr:
            self.wa5km_lyr = None
        QObject.disconnect(self.wp_conn1)
        QObject.disconnect(self.pdk_conn1)
        QObject.disconnect(self.select_tool_conn)
        QObject.disconnect(self.checkbox_conn)
        QObject.disconnect(self.file_widget_conn)


class SelectTool(QgsMapTool):
    def __init__(self, canvas, pdk_layer, wp_layer, parent=None):
        self.canvas = canvas
        self.project = QgsProject.instance()
        self.pdk_layer = pdk_layer
        self.wp_layer = wp_layer
        self.parent = parent
        QgsMapTool.__init__(self, self.canvas)
        self.counter = 0
        
        self.rubber_band = None
        self.tl = None# Top Left corner of rectangle
    
    ########################################
    # Manipulate map tool cursor to assist with selecting paddocks and waterpoint
    def canvasMoveEvent(self, e):
        if self.counter == 0:
            # Selecting paddock
            cursor_pos = self.toLayerCoordinates(self.pdk_layer, e.mapPoint())
            if [ft for ft in self.pdk_layer.getFeatures() if ft.geometry().contains(cursor_pos)]:
                self.setCursor(QCursor(Qt.PointingHandCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
        elif self.counter > 0:
            # Selecting water points
            if self.rubber_band:
                # We are dragging a rectangle
                br = self.toMapCoordinates(e.pos())
                rect = QgsRectangle(self.tl, br)
                self.rubber_band.setToGeometry(QgsGeometry().fromRect(rect))
            else:
                cursor_pos = self.toLayerCoordinates(self.wp_layer, e.mapPoint())
                buffer = 100
                if self.wp_layer.sourceCrs().isGeographic():
                    buffer = 0.001
                if [ft for ft in self.wp_layer.getFeatures() if ft.geometry().buffer(buffer, 25).contains(cursor_pos)]:
                    self.setCursor(QCursor(Qt.CrossCursor))
                else:
                    #self.setCursor(QCursor(Qt.ArrowCursor))
                    self.setCursor(QgsApplication.getThemeCursor(QgsApplication.Cursor.Select))
    ############################################################################
        
    def canvasPressEvent(self, e):
        #Edit April 2024
        if self.counter == 0:
            # we are selecting a paddock so we make sure user clicked inside a paddock feature
            if not [ft for ft in self.pdk_layer.getFeatures() if ft.geometry().contains(self.toLayerCoordinates(self.pdk_layer, e.mapPoint()))]:
                msg_box = QMessageBox()
                msg_box.setText('Please click inside a paddock feature')
                msg_box.exec()
                return
        self.tl = self.toMapCoordinates(e.pos())
        if e.button() == Qt.LeftButton:
            modifiers = e.modifiers()
            ###########SELECTING MULTIPLE WATER POINT BY DRAGGING RECTANGLE#####
            if modifiers & Qt.ControlModifier:
                self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                self.rubber_band.setStrokeColor(QColor(255, 0, 0, 150))
                self.rubber_band.setWidth(1)
            ##################SELECTING SINGLE WATER POINT######################
            else:
                self.counter+=1
                if self.counter == 1:
                    # we are selecting a paddock
                    click_point = self.toLayerCoordinates(self.pdk_layer, e.mapPoint())#QgsPointXY
                    paddock_feat = [ft for ft in self.pdk_layer.getFeatures() if ft.geometry().contains(click_point)][0]
                    self.add_paddock_to_table(paddock_feat)
                elif self.counter > 1:
                    # we are selecting waterpoints
                    click_point = self.toLayerCoordinates(self.wp_layer, e.mapPoint())
                    buffer = 100
                    if self.wp_layer.sourceCrs().isGeographic():
                        buffer = 0.001
                    waterpoint_feats = [ft for ft in self.wp_layer.getFeatures() if ft.geometry().buffer(buffer, 25).contains(click_point)]
                    if waterpoint_feats:
                        #waterpoint_feat = waterpoint_feats[0]
                        wpt_idx = QgsSpatialIndex()
                        wpt_idx.addFeatures(waterpoint_feats)
                        nearest_wp_id = wpt_idx.nearestNeighbor(click_point)[0]
                        waterpoint_feat = self.wp_layer.getFeature(nearest_wp_id)
                        self.add_waterpoints_to_table(waterpoint_feat)
        elif e.button() == Qt.RightButton:
            self.canvas.unsetMapTool(self)
            self.deactivate()
                
    def canvasReleaseEvent(self, e):
        if self.rubber_band:
            rb_geom = self.transformed_geom(self.rubber_band.asGeometry())
            wp_feats = [ft for ft in self.wp_layer.getFeatures() if ft.geometry().intersects(rb_geom)]
            for feat in wp_feats:
                self.add_waterpoints_to_table(feat)
            self.rubber_band.reset()
            self.rubber_band = None
            self.tl = None
    
    def add_paddock_to_table(self, feat):
        #TODO: Safeguard against key error if self.parent.pdk_fld_cb.currentField() is None
        row_count = self.parent.tbl.rowCount()
        self.parent.tbl.setRowCount(row_count + 1)
        idx = row_count
        i = QTableWidgetItem(f'{feat[self.parent.pdk_fld_cb.currentField()]}({feat.id()})')
        self.parent.tbl.setItem(idx, 0, i)
        self.parent.tbl.resizeColumnsToContents()
        
    def add_waterpoints_to_table(self, feat):
        #TODO: Safeguard against key error if self.parent.wp_fld_cb.currentField() is None
        row_count = self.parent.tbl.rowCount()
        row_idx = row_count-1
        item = self.parent.tbl.item(row_idx, 1)
        if not item:
            item = QTableWidgetItem(f'{feat[self.parent.wp_fld_cb.currentField()]}({feat.id()})')
            self.parent.tbl.setItem(row_idx, 1, item)
        else:
            current_data = item.data(Qt.DisplayRole)
            if current_data:
                current_data+=f'; {feat[self.parent.wp_fld_cb.currentField()]}({feat.id()})'
                item.setData(Qt.DisplayRole, current_data)
        self.parent.tbl.resizeColumnsToContents()
        self.parent.create_paddock_watered_areas()

    def deactivate(self):
        self.counter = 0
        if self.rubber_band:
            self.rubber_band.reset()
            self.rubber_band = None
        self.deactivated.emit()
        
    def transformed_geom(self, g):
        '''Convenience method to transform rectangle rubber band from
        canvas CRS to waterpoint layer CRS to retrieve waterpoints'''
        geom = QgsGeometry.fromWkt(g.asWkt())
        xform = QgsCoordinateTransform(self.project.crs(), self.wp_layer.crs(), self.project)
        geom.transform(xform)
        return geom
