from qgis.PyQt.QtCore import QCoreApplication, QVariant, QDateTime

from qgis.PyQt.QtGui import QIcon

from qgis.core import (QgsField,
                        QgsFields,
                        QgsFeature,
                        QgsFeatureSink,
                        QgsFeatureRequest,
                        QgsProcessing,
                        QgsProcessingAlgorithm,
                        QgsUnitTypes,
                        QgsProcessingParameterFeatureSource,
                        QgsProcessingParameterField,
                        QgsProcessingParameterDuration,
                        QgsProcessingParameterBoolean,
                        QgsProcessingParameterFeatureSink,
                        QgsDistanceArea,
                        QgsPoint,
                        QgsGeometry)

import datetime

import os

class InterpolateTemporalPoints(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELDS = 'FIELDS'
    INTERVAL = 'INTERVAL'
    ROUND_TIMESTAMPS = 'ROUND_TIMESTAMPS'
    ADD_AZIMUTH = 'ADD_AZIMUTH'
    OUTPUT = 'OUTPUT'
 
    def __init__(self):
        super().__init__()
 
    def name(self):
        return "interpolatetemporalpoints"
         
    def displayName(self):
        return "Interpolate temporal points"
 
    def group(self):
        return "GPS Collars"
 
    def groupId(self):
        return "gps_collars"
        
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "../icons/collar_icon.png"))
 
    def shortHelpString(self):
        return "Interpolate gaps in point data with a temporal attribute (e.g. GPS data)"
 
    def helpUrl(self):
        return "https://qgis.org"
         
    def createInstance(self):
        return type(self)()
   
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            "Input layer",
            [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELDS,
            "Fields to add to output layer",
            parentLayerParameterName=self.INPUT,
            allowMultiple=True))
        interval_param = QgsProcessingParameterDuration(
            self.INTERVAL,
            "Time interval",
            60000,# Default value must be given in milliseconds
            False,
            0)
        interval_param.setDefaultUnit(QgsUnitTypes.TemporalMinutes)
        self.addParameter(interval_param)
        self.addParameter(QgsProcessingParameterBoolean(
            self.ROUND_TIMESTAMPS,
            "Round all timestamps to interval (useful for smooth animations *not recommended for analysis)",
            False))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ADD_AZIMUTH,
            "Add Azimuth Field",
            True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            "Output layer",
            QgsProcessing.TypeVectorPoint))
 
    def processAlgorithm(self, parameters, context, feedback):
        ft_source = self.parameterAsSource(parameters, self.INPUT, context)
        source = ft_source.materialize(QgsFeatureRequest())
        feedback.pushInfo(repr([fld.typeName() for fld in source.fields()]))
        ########################################
        dt_flds = [fld.name() for fld in source.fields() if fld.typeName() == 'datetime']
        if not dt_flds:
            feedback.pushDebugInfo('Input layer has no DateTime field!')
            return {}
        dt_fld = dt_flds[0]
        ########################################
        output_field_names = self.parameterAsFields(parameters, self.FIELDS, context)
        output_fields = QgsFields()
        #######
        round_timestamps = self.parameterAsBool(parameters, self.ROUND_TIMESTAMPS, context)
        #######
        add_az = self.parameterAsBool(parameters, self.ADD_AZIMUTH, context)
        for fld in source.fields():
            if fld.name() in output_field_names:
                output_fields.append(fld)
        if add_az:
            output_fields.append(QgsField('Azimuth', QVariant.Int))
        interval_milliseconds = self.parameterAsDouble(parameters, self.INTERVAL, context)#Milliseconds
        interval_seconds = interval_milliseconds/1000#Convert to Seconds
        interval_minutes = interval_milliseconds/60000#Convert to Minutes
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               output_fields, source.wkbType(), source.sourceCrs())
        
        round_timestamps = self.parameterAsBool(parameters, self.ROUND_TIMESTAMPS, context)

        da = QgsDistanceArea()
        da.setSourceCrs(source.sourceCrs(), context.project().transformContext())
        da.setEllipsoid(source.sourceCrs().ellipsoidAcronym())

        out_feats = None
        
        output_field_names = [fld.name() for fld in output_fields]
        
        # We're not rounding timestamps
        if not round_timestamps:
            out_feats = []
            for f in source.getFeatures():
                next_ft = source.getFeature(f.id()+1)
                # check for final feature (will return some large negative integer)
                if next_ft.id()>0:
                    current_dt = f[dt_fld].toPyDateTime()
                    next_dt = next_ft[dt_fld].toPyDateTime()
                    t_delta = next_dt-current_dt# timedelta object
                    az = f.geometry().asPoint().azimuth(next_ft.geometry().asPoint())
                    #Time difference divided by user-desired interval (e.g. 2 mins)[total divisions]
                    #Then subtract one for number of fill-in features
                    no_of_feats_to_add = int((t_delta.seconds*1000)/interval_milliseconds)-1
                    #feedback.pushInfo(repr(no_of_feats_to_add))#Correct to this point
                    ###-----------------------------------------------------------------------
                    # first add current existing feature
                    existing_feat = QgsFeature(output_fields)
                    existing_feat.setGeometry(f.geometry())
                    atts = [f[fld.name()] for fld in output_fields if fld.name() != 'Azimuth']
                    if add_az:
                        atts.append(az)
                    existing_feat.setAttributes(atts)
                    out_feats.append(existing_feat)
                    # skip if no gap to fill
                    if no_of_feats_to_add < 1:
                        continue
                    # create a line geometry from current to next feature
                    line_to_interp = QgsGeometry.fromPolyline([QgsPoint(f.geometry().asPoint()), QgsPoint(next_ft.geometry().asPoint())])
                    interp_dist = line_to_interp.length()/(no_of_feats_to_add+1)
                    dist_meters = da.measureLength(line_to_interp)/(no_of_feats_to_add+1)
                    ###
                    interp_duration = (t_delta.seconds*1000)/(no_of_feats_to_add+1)
                    #feedback.pushInfo(repr(interp_duration))# Correct (in milliseconds)
                    ###
                    for i in range(no_of_feats_to_add):
                        dist = interp_dist*(i+1)
                        time_delta = datetime.timedelta(milliseconds=interp_duration*(i+1))
                        new_geom = line_to_interp.interpolate(dist)
                        new_dt = current_dt+time_delta
                        new_feat = QgsFeature(output_fields)
                        new_feat.setGeometry(new_geom)
                        #Modify atts list
                        dt_fld_index = output_field_names.index(dt_fld)
                        atts[dt_fld_index] = QDateTime(new_dt)
                        if 'Latitude' in output_field_names:
                            lat_fld_index = output_field_names.index('Latitude')
                            atts[lat_fld_index] = round(new_geom.asPoint().y(), 6)
                        if 'Longitude' in output_field_names:
                            lon_fld_index = output_field_names.index('Longitude')
                            atts[lon_fld_index] = round(new_geom.asPoint().x(), 6)
                        new_feat.setAttributes(atts)
                        out_feats.append(new_feat)
        
        # User wants to round timestamps for smooth animation
        else:
            out_feats = []
            ft_count = 1
            all_fts = [ft for ft in source.getFeatures()]
            first_ft = all_fts[0]
            first_dt_rounded = first_ft[dt_fld].toPyDateTime().replace(second=0, microsecond=0)
            start_dt = first_dt_rounded - datetime.timedelta(seconds=interval_seconds)

            for f in all_fts:
                next_ft = source.getFeature(f.id()+1)
                # check for final feature (will return some large negative integer)
                if next_ft.id()>0:
                    current_dt = f[dt_fld].toPyDateTime()
                    ###ROUND
                    current_dt = current_dt.replace(second=0, microsecond=0)
                    orig_next_dt = next_ft[dt_fld].toPyDateTime()
                    ###ROUND
                    next_dt = orig_next_dt.replace(second=0, microsecond=0)
                    t_delta = next_dt-current_dt# timedelta object
                    az = f.geometry().asPoint().azimuth(next_ft.geometry().asPoint())
                    #Time difference divided by user-desired interval (e.g. 2 mins)[total divisions]
                    #Then subtract one for number of fill-in features
                    no_of_feats_to_add = int((t_delta.seconds)/interval_seconds)-1
                    ###---
                    dt_td = datetime.timedelta(seconds=(interval_seconds*ft_count))
                    dt_attribute = start_dt + dt_td
                    #----
                    # Rounding down causes cumulative loss of time; so we chec to see if we have
                    # accumulated a gap which is larger than the user-defined interval. If so, we
                    # add an additional feature into the gap to make up the difference.
                    if orig_next_dt-(dt_attribute+datetime.timedelta(seconds=interval_seconds)) > datetime.timedelta(seconds=interval_seconds):
                        no_of_feats_to_add += 1
                    ###---
                    #print(no_of_feats_to_add)#Correct to this point
                    ###-----------------------------------------------------------------------
                    # first add current existing feature
                    existing_feat = QgsFeature(output_fields)
                    existing_feat.setGeometry(f.geometry())
                    atts = [f[fld.name()] for fld in output_fields if fld.name() != 'Azimuth']
                    dt_fld_index = output_field_names.index(dt_fld)
                    atts[dt_fld_index] = QDateTime(dt_attribute)
                    if add_az:
                        atts.append(az)
                    existing_feat.setAttributes(atts)
                    out_feats.append(existing_feat)
                    ft_count+=1
                    # skip if no gap to fill
                    if no_of_feats_to_add < 1:
                        continue
                    # create a line geometry from current to next feature
                    line_to_interp = QgsGeometry.fromPolyline([QgsPoint(f.geometry().asPoint()), QgsPoint(next_ft.geometry().asPoint())])
                    interp_dist = line_to_interp.length()/(no_of_feats_to_add+1)
                    dist_meters = da.measureLength(line_to_interp)/(no_of_feats_to_add+1)
                    ###
                    interp_duration = (t_delta.seconds*1000)/(no_of_feats_to_add+1)
                    #print(interp_duration)# Correct (in milliseconds)
                    ###
                    for i in range(no_of_feats_to_add):
                        dist = interp_dist*(i+1)
                        new_geom = line_to_interp.interpolate(dist)
                        #print(new_dt)
                        new_feat = QgsFeature(output_fields)
                        new_feat.setGeometry(new_geom)
                        dt_td = datetime.timedelta(seconds=(interval_seconds*ft_count))
                        dt_attribute = start_dt + dt_td
                        ##*****************--------------------------------
                        #Modify atts list
                        atts[dt_fld_index] = QDateTime(dt_attribute)
                        if 'Latitude' in output_field_names:
                            lat_fld_index = output_field_names.index('Latitude')
                            atts[lat_fld_index] = round(new_geom.asPoint().y(), 6)
                        if 'Longitude' in output_field_names:
                            lon_fld_index = output_field_names.index('Longitude')
                            atts[lon_fld_index] = round(new_geom.asPoint().x(), 6)
                        new_feat.setAttributes(atts)
                        out_feats.append(new_feat)
                        ##*****************---------------------------------
                        # increment variables
                        ft_count+=1
        ###******************************************************************###
        ###Update Distance attribute
        dist_fld_idx = output_field_names.index('Distance')
        for i, new_feat in enumerate(out_feats):
            if i > 0:
                ft_atts = [new_feat[fld.name()] for fld in output_fields]
                prev_ft = out_feats[i-1]
                prev_dist_line = QgsGeometry.fromPolyline([QgsPoint(new_feat.geometry().asPoint()), QgsPoint(prev_ft.geometry().asPoint())])
                distance_from_prev = da.measureLength(prev_dist_line)
                ft_atts[dist_fld_idx] = round(distance_from_prev, 2)
                new_feat.setAttributes(ft_atts)
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
        ##################################
        if context.willLoadLayerOnCompletion(dest_id):
            lyr_details = context.layerToLoadOnCompletionDetails(dest_id)
            lyr_details.name = 'Interpolated'
            lyr_details.forceName = True
        
        return {self.OUTPUT: dest_id}