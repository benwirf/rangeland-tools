# -*- coding: utf-8 -*-

"""
/***************************************************************************
 RANGELAND TOOLS
                                 A QGIS hybrid processing/gui plugin

    A collection of scripts for quarterly feed outlook report
    
        begin                : September 2022
        copyright            : (C) 2023 by Ben Wirf
        email                : ben.wirf@gmail.com
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Ben Wirf'
__date__ = '2023-05-05'
__copyright__ = '(C) 2023 by Ben Wirf'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import sys
import inspect

from qgis.PyQt.QtWidgets import (QMenu, QAction)

from qgis.PyQt.QtGui import QIcon


from qgis.core import (QgsProcessingAlgorithm, QgsApplication)
from .rangeland_tools_provider import RangelandToolsProvider
from .custom_watered_areas.custom_watered_areas import CustomWateredAreasWidget

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

iconPath = os.path.dirname(__file__)

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class RangelandToolsPlugin(object):

    def __init__(self, iface):
        self.iface = iface
        self.provider = RangelandToolsProvider()


    def initGui(self):
        QgsApplication.processingRegistry().addProvider(self.provider)
        self.vector_menu = self.iface.vectorMenu()
        self.rangeland_tools_menu = QMenu('Rangeland Tools', self.vector_menu)
        self.cwa_icon = QIcon(os.path.join(iconPath, 'icons/cwa_icon.png'))
        self.custom_wa_action = QAction(self.cwa_icon, 'Custom Watered Areas')
        self.custom_wa_action.triggered.connect(self.showCustomWateredAreasWidget)
        self.rangeland_tools_menu.addAction(self.custom_wa_action)
        self.vector_menu.addMenu(self.rangeland_tools_menu)
        # self.dlg = CustomWateredAreasWidget(self.iface.mainWindow())
        
        
    def showCustomWateredAreasWidget(self):
        self.dlg = CustomWateredAreasWidget(self.iface.mainWindow())
        self.dlg.show()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        self.vector_menu.removeAction(self.rangeland_tools_menu.menuAction())
        del self.custom_wa_action
        del self.rangeland_tools_menu
        
        