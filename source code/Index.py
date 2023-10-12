from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from neo4j import GraphDatabase
import mysql.connector
from pymongo import MongoClient
import copy
from datetime import datetime
import pandas as pd
import numpy as np

# Load the UI file
Ui_CreateWindow, QMainWindow = uic.loadUiType("newOlapCube.ui")
Ui_MainWindow, _ = uic.loadUiType("welcome.ui")
Ui_HistoryWindow, _ = uic.loadUiType("history.ui")

class GraphAdjacency:
    def __init__(self):
        self.adjacency_list = {}

    def add_vertex(self, vertex):
        if vertex not in self.adjacency_list:
            self.adjacency_list[vertex] = []

    def add_edge(self, vertex1, vertex2):
        if vertex2 not in self.adjacency_list[vertex1] :
            self.adjacency_list[vertex1].append(vertex2)
        self.add_vertex(vertex2)

    def get_adjacent_vertices(self, vertex):
        if vertex in self.adjacency_list:
            return self.adjacency_list[vertex]
        else:
            return []

    def display(self):
        for vertex in self.adjacency_list:
            print(vertex, "->", self.adjacency_list[vertex])

    def clear_graph_adjacency(self):
        self.adjacency_list.clear()  

    def delete_vertex(self,vertex):
        del self.adjacency_list[vertex]
        for value in self.adjacency_list.values():
            if vertex in value:
                value.remove(vertex)

class ForeignKey:
    def __init__(self,column,references,references_column) :
        self.column=column
        self.references=references
        self.references_column=references_column


class Table: # For Document and Relational
    def __init__(self,table_name,primary_key=None,attribute=None):
        self.table_name=table_name
        self.primary_key=primary_key
        self.selected_attributes=[] if attribute is None else [attribute]
        self.foreign_keys=[] # for the purpose of creating fks at the moment of creating table  
        
        ''' we add foreign key to it , we create 
        this attribute just to separate it from foreign keys
        becuase they don't realy exist in tables 
        '''
        self.bridge_foreign_keys=[] 
                                

    def add_attribute(self,attribute):
        self.selected_attributes.append(attribute)

    def add_foreign_key(self,foreign_key:ForeignKey):
        self.foreign_keys.append(foreign_key)

    def add_bridge_foreign_key(self,bridge_foreign_key:ForeignKey):
        self.bridge_foreign_keys.append(bridge_foreign_key)

class TargetPrimaryKey:
    def __init__(self,relation_name,table_name,primary_key):
        self.relation_name=relation_name
        self.table_name=table_name
        self.primary_key=primary_key

class GraphTable(Table): # when the source is a graph
    def __init__(self, table_name, primary_key=None, attribute=None):
        super().__init__(table_name, primary_key, attribute)
        self.target_primary_keys=[]

    def add_target_primary_key(self,target_primary_key:TargetPrimaryKey):
        self.target_primary_keys.append(target_primary_key)

class RelationshipTable(Table): # when the fact is a relationship
    def __init__(self,relation_name) :
        super().__init__('')
        self.relation_name=relation_name
        self.measure_name=''
        self.source_table_name=''
        self.target_table_primary_key=''   # because we need only one when the relationship is Gph_Edge

    def add_source_table(self,source_table_name) :
        self.source_table_name=source_table_name
    
    def add_target_table_pk(self,target_table_pk):
        self.target_table_primary_key=target_table_pk

    def add_measure(self,measure_name):
        self.measure_name=measure_name

class Entity:
    def __init__(self,description,role_name=None):
        self.description=description
        self.role_names=[] if role_name is None else [role_name]
        self.sources={}

    def add_source(self,node_type,data : Table):
        self.sources[node_type]=data

    def get_first_node_type(self):
        first_key = next(iter(self.sources))
        return first_key
    
    def get_table_name_for_node_type(self, node_type):
        if node_type in self.sources:
            return self.sources[node_type].table_name
        else:
            return None
    
    def add_role(self,role): 
        self.role_names.append(role)

    def get_measures(self):
        for source in self.sources.values() : 
            if type(source) is RelationshipTable:
                return [source.measure_name]
            else:
                return self.get_selected_attributes()   

    def get_selected_attributes(self):
        attributes=[]
        for source in self.sources.values() :
            if self.description=='bridge_table':
                return source.foreign_keys[0].column
            else:
                attributes.extend(source.selected_attributes) 
        return attributes

class Graph:
    
    def __init__(self):
        self.tables = {}
    
    def add_table(self,key,value : Entity):
        self.tables[key]=value

    def get_first_key_value(self):
        first_key = next(iter(self.tables))
        return first_key,self.tables[first_key]
    
    def get_first_key(self):
        first_key = next(iter(self.tables))
        return first_key
    
    def clear_graph(self):
        self.tables.clear()
    
graph=Graph()
graph_adjacency=GraphAdjacency()

class Delegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.parent().parent().parent().parent().isValid() and not index.parent().parent().parent().parent().parent().isValid():
            widget = option.widget
            style = widget.style() if widget else QApplication.style()
            opt = QStyleOptionButton()
            opt.rect = option.rect
            opt.text = index.data()
            opt.state |= QStyle.State_On if index.data(Qt.CheckStateRole) else QStyle.State_Off
            style.drawControl(QStyle.CE_RadioButton, opt, painter, widget)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

class MyWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pushButton_2.clicked.connect(self.open)
        self.pushButton.clicked.connect(self.open_history_window)
        self.history_window = None
        self.initUI()
    
    def initUI(self):
        icon = QIcon("olapcube.png") 
        self.setWindowIcon(icon)

    def open(self):
        window = CreateWindow()
        window.show()

    def open_history_window(self):
        if self.history_window is None:
            self.history_window = HistoryWindow()
        self.history_window.show()

class HistoryWindow(QMainWindow,Ui_HistoryWindow):

    conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='hamza',
    database = 'graphs',
    )
    cursor = conn.cursor()

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.initUI()

        self.searchLineEdit.textChanged.connect(self.search_table)
        
        query='select graph_name , structure from data_history'

        self.cursor.execute(query)
        result=self.cursor.fetchall() # a list of tuples 

        for tup in result :
            self.add_graph(tup[0],tup[1],tup[0])
        
    def add_graph(self, graph_name, structure, script_id):
        row_count = self.tableWidget.rowCount()
        self.tableWidget.setRowCount(row_count + 1)

        self.tableWidget.setItem(row_count, 0,QTableWidgetItem(graph_name))
        self.tableWidget.setItem(row_count, 1, QTableWidgetItem(structure))

        download_button = QPushButton("")
        icon = QIcon("icon.jpg")
        download_button.setIcon(icon)
        download_button.setStyleSheet("QPushButton { background-color: transparent; border: none; }")

        download_button.clicked.connect(lambda: self.download_script(script_id))
        self.tableWidget.setCellWidget(row_count, 2, download_button)

    def download_script(self,script_id):
  
        query=f'select script from data_history where graph_name="{script_id}"'
        self.cursor.execute(query)
        result=self.cursor.fetchall()
        script_content = result[0][0]

        # Prompt the user to choose a file location
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Download Script", "", "SQL Files (*.sql)", options=options)

        if file_path:
            # Save the script content to the chosen file location
            with open(file_path, "w" ,encoding='utf-8') as file:
                file.write(script_content)
            print("Script downloaded successfully.")
        else:
            print("Script not saved.")
        
    def search_table(self, search_text):
        
        for row in range(self.tableWidget.rowCount()):           
            
            item = self.tableWidget.item(row, 0)

            if item.text().lower().startswith(search_text.lower()):
                self.tableWidget.setRowHidden(row, False)
            else:
                self.tableWidget.setRowHidden(row, True)


    
    def initUI(self):
        icon = QIcon("olapcube.png") 
        self.setWindowIcon(icon)
   
class CreateWindow(QMainWindow, Ui_CreateWindow):

    businessName=''
    graph_number=''

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.treeWidget_fact.setItemDelegate(Delegate())
        self.initUI()
        self.nextButton.clicked.connect(self.show_next_widget)
        self.backButton.clicked.connect(self.show_back_widget)
        self.cancelButton.clicked.connect(self.cancel)
        self.graphButton.clicked.connect(self.generate_graph)
        self.olapCubeButton.clicked.connect(self.generate_olapCube)
        self.treeWidget_fact.itemClicked.connect(lambda: self.handle_item_selection_changed(self.treeWidget_fact))
        self.treeWidget_measures.itemClicked.connect(lambda : self.handle_item_selection_changed(self.treeWidget_measures))
        self.treeWidget_dimensions.itemClicked.connect(lambda : self.handle_item_selection_changed(self.treeWidget_dimensions))
        self.treeWidget_hierarchies.itemClicked.connect(lambda : self.handle_item_selection_changed(self.treeWidget_hierarchies))
        
    def set_current_step (self,treeWidget, index):
        for i in range(treeWidget.topLevelItemCount()):
            item = treeWidget.topLevelItem(i)
            if i == index:
                item.setForeground(0,  QColor(0, 119, 204))
            else:
                item.setForeground(0, Qt.black)

    def initUI(self):

        icon = QIcon("olapcube.png")  
        self.setWindowIcon(icon)
        for i in range(self.stackedWidget.count()):
            
            item = QTreeWidgetItem(["Step {} : {}".format(i+1, self.stackedWidget.widget(i).objectName())])
            self.treeWidget.addTopLevelItem(item)
        
        self.current_widget_index = 0
        self.set_current_step(self.treeWidget,self.current_widget_index)

        query = '''Match(dataLake:DL)-[:ComposedOf]->(dataStore)-[:ComposedOf]->(facts)-[business_name:Has_MD_Prp]-> (mdPrp:MD_Prp)
                    Where mdPrp.name="Business_Name"
                    Return dataLake.name,head(labels(dataStore)) AS dataStore,dataStore.name,
                    head(labels(facts)) AS factType,facts.name,business_name.value'''
        result = execute_query(query)
        items_by_name = {}
        
        for record in result:
            data_lake,data_store_type,data_store_name,fact_type,fact_name,business_name = record.values()
    
            if data_lake not in items_by_name:
                data_lake_item = self.createTopLevelItem(data_lake,self.treeWidget_fact)
                items_by_name[data_lake] = {'item': data_lake_item, 'children': {}}

            if data_store_type not in items_by_name[data_lake]['children']:
                data_store_type_item =self.createChildItem(data_store_type,data_lake_item)
                items_by_name[data_lake]['children'][data_store_type] = {'item': data_store_type_item, 'children': {}}

            if data_store_name not in items_by_name[data_lake]['children'][data_store_type]['children']:
                data_store_name_item = self.createChildItem(data_store_name,data_store_type_item)
                items_by_name[data_lake]['children'][data_store_type]['children'][data_store_name] = {'item': data_store_name_item, 'children': {}}
                
            if fact_type not in items_by_name[data_lake]['children'][data_store_type]['children'][data_store_name]['children']:
                fact_type_item = self.createChildItem(fact_type,data_store_name_item)
                items_by_name[data_lake]['children'][data_store_type]['children'][data_store_name]['children'][fact_type] = {'item': fact_type_item, 'children': {}}
            fact_name_item = self.createCheckebleItem(fact_type_item)
            fact_name_item.setText(0,fact_name +' : ' +business_name) 
                        
    def handle_item_selection_changed(self,treeWidget):
        item = QTreeWidgetItem()
        item=treeWidget.currentItem()
        
        check_state = item.checkState(0)
        if not item.flags() & Qt.ItemIsSelectable:
            return
        else:
            if check_state == Qt.Checked:
                item.setCheckState( 0,Qt.Unchecked)   
            elif check_state == Qt.Unchecked:
                item.setCheckState( 0,Qt.Checked)
                self.unchecked_items_fact(item)
                
            self.factErreur_label.setText("")
            self.measuresErreur_label.setText("")
            self.dimensionsErreur_label.setText("")
        #special case for dimension tree widget
        if self.current_widget_index==2 or self.current_widget_index==3:
              
            if check_state == Qt.Unchecked  and item.parent().parent() is not None and item.parent().parent().flags() & Qt.ItemIsSelectable:  
                item.parent().parent().setCheckState( 0,Qt.Checked)

            if  check_state == Qt.Checked:
                for i in range(item.childCount()):
                    for j in range(item.child(i).childCount()):
                        if item.child(i).child(j).flags() & Qt.ItemIsSelectable:
                            item.child(i).child(j).setCheckState( 0,Qt.Unchecked)
        
    def unchecked_items_fact(self,checkeditem):
        for i in range(self.treeWidget_fact.topLevelItemCount()):
            item = self.treeWidget_fact.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                for k in range(child.childCount()):
                    child2 = child.child(k)
                    for l in range(child2.childCount()):
                        child3 = child2.child(l)
                        for m in range(child3.childCount()):
                            if  child3.child(m)!=checkeditem:
                                child3.child(m).setCheckState(0, Qt.Unchecked)

    def getParentPath(self,item):
        def getParent(item,outstring):
            if item.parent() is None:
                return outstring
            outstring= item.parent().text(0) + "/" + outstring
            return getParent(item.parent(),outstring)
        output=getParent(item,item.text(0))
        return output



    def show_next_widget(self):
           
        if self.current_widget_index==0 :
            if self.isFactValid() :
                self.current_widget_index += 1
                self.backButton.setEnabled(True)
                self.stackedWidget.setCurrentIndex(self.current_widget_index)
                self.set_current_step(self.treeWidget,self.current_widget_index)
                self.show_mesures()  
            else : #tab erreur (you should select)
                self.factErreur_label.setText("you have to choose a fact to continue")

        elif self.current_widget_index==1 : 
            result=self.isMeasuresValid()
            if result[0] :
                self.current_widget_index += 1
                self.stackedWidget.setCurrentIndex(self.current_widget_index)
                self.set_current_step(self.treeWidget,self.current_widget_index)
                self.show_dimensions()
            else: #tab erreur, two have the same bn (from suggested)
                self.measuresErreur_label.setText(result[1])

        elif self.current_widget_index==2 : 
            if self.isDimensionsValid() :
                self.current_widget_index += 1
                self.stackedWidget.setCurrentIndex(self.current_widget_index)
                self.set_current_step(self.treeWidget,self.current_widget_index)
                self.show_hierarchies()
            else: #tab erreur, two have the same bn (from suggested)
                self.dimensionsErreur_label.setText("you have to to select at least one dimension to continue")

        elif self.current_widget_index==3 and self.isHierarchiesValid() :
            self.current_widget_index += 1
            self.stackedWidget.setCurrentIndex(self.current_widget_index)
            self.set_current_step(self.treeWidget,self.current_widget_index)
            self.nextButton.setEnabled(False)
            self.backButton.setEnabled(False)

    def show_back_widget(self):
    # in measures / clear chosen fact
        if self.current_widget_index==1 : 
            graph.clear_graph()
            graph_adjacency.clear_graph_adjacency()
            self.backButton.setEnabled(False)
            self.treeWidget_measures.clear()
    # in dimensions / clear measures of chosen fact and facts of suggested measures    
        elif self.current_widget_index==2 : 
            self.treeWidget_dimensions.clear()
            keys_to_delete = []
            first_node_type=graph.tables[self.businessName].get_first_node_type()
            first_source=graph.tables[self.businessName].sources[first_node_type]
            if first_node_type in ['Gph_Edge','Doc_Relationship','Rel_Relatioship']:
                first_source.source_table_name=''
                first_source.measure_name=''
            else:
                first_source.selected_attributes.clear()
                for key  in graph.tables[self.businessName].sources.keys():
                    if key != first_node_type:
                        keys_to_delete.append(key)
                for key in keys_to_delete:
                    del graph.tables[self.businessName].sources[key]

    # in hierarchies / clear dimensions 
        elif self.current_widget_index==3 : 
     
            self.treeWidget_hierarchies.clear()
        # first we delete all dimensions    
            keys_to_delete = []
            for key , value in graph.tables.items():
                if value.description in ['dimension_table','bridge_table','level_table']:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                    del graph.tables[key]
                    graph_adjacency.delete_vertex(key)
        # delete FKs and TPKs
            first_node_type=graph.tables[self.businessName].get_first_node_type()
            first_source=graph.tables[self.businessName].sources[first_node_type]
            if first_node_type in ['Gph_Edge','Doc_Relationship','Rel_Relatioship']:
                first_source.foreign_keys.clear()
                first_source.target_table_primary_key=''
                graph.tables[self.businessName].sources[first_node_type].selected_attributes.clear()
            
            else:
                keys_to_delete.clear()
                for key , value in graph.tables[self.businessName].sources.items():
                    graph.tables[self.businessName].sources[key].foreign_keys.clear()
                    if type(value) is GraphTable:
                        graph.tables[self.businessName].sources[key].target_primary_keys.clear()
                    
                    if key != first_node_type and len(graph.tables[self.businessName].sources[key].selected_attributes) == 0 :
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    del graph.tables[self.businessName].sources[key]
             
            
        self.current_widget_index -= 1
        self.stackedWidget.setCurrentIndex(self.current_widget_index)
        self.set_current_step(self.treeWidget,self.current_widget_index)
    
    def cancel(self):
        graph.clear_graph()
        graph_adjacency.clear_graph_adjacency()
        self.nextButton.setEnabled(True)
        self.current_widget_index = 0
        self.stackedWidget.setCurrentIndex(self.current_widget_index)
        self.set_current_step(self.treeWidget,self.current_widget_index)        
        self.treeWidget_measures.clear()
        self.treeWidget_dimensions.clear()
        self.treeWidget_hierarchies.clear()
        # self.factErreur_label.setText("")
        self.measuresErreur_label.setText("")
        self.dimensionsErreur_label.setText("")



    def createCheckebleItem(self,parent_item):
        item = QTreeWidgetItem(parent_item)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setCheckState( 0,Qt.Unchecked)
        parent_item.addChild(item)
        return item
    
    def createChildItem(self,item_name,parent_item):
        childItem=QTreeWidgetItem([item_name])
        parent_item.addChild(childItem)
        childItem.setFlags(childItem.flags()  & ~Qt.ItemIsSelectable  )
        return childItem
    
    def createTopLevelItem (self,item_name,tree_widget):
        item=QTreeWidgetItem([item_name])
        item.setFlags(item.flags()  & ~Qt.ItemIsSelectable  )
        tree_widget.addTopLevelItem(item)
        return item

    def create_table(self,table_name,primary_key,node_type,role_name,description,business_name):
        
        if node_type=='Gph_Vtx':
            table=GraphTable(table_name,primary_key)
        else:
            table=Table(table_name,primary_key)
        if role_name != '':
            entity=Entity(description,role_name)
        else:
            entity=Entity(description)
        entity.add_source(node_type,table)
        graph.add_table(business_name,entity)

        return table



    def isFactValid(self):
        # we first look for the selected fact and when we find it 
        # we add it to our grph (table OR relationship)
        for i in range(self.treeWidget_fact.topLevelItemCount()):
            item = self.treeWidget_fact.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                for k in range(child.childCount()):
                    child2 = child.child(k)
                    for l in range(child2.childCount()):
                        child3 = child2.child(l)
                        for m in range(child3.childCount()):
                            if  child3.child(m).checkState(0)== Qt.Checked:

                                node_type=child3.child(m).parent().text(0)
                                if node_type in ['Gph_Edge' ,'Rel_Relatioship','Doc_Relationship']:
                                    relation_name,self.businessName=child3.child(m).text(0).split(' : ')
                                    relationship_table=RelationshipTable(relation_name)
                                    entity=Entity('relationship_fact_table')
                                    entity.add_source(node_type,relationship_table)
                                    graph.add_table(self.businessName,entity)
                                    
                                else:
                                    table_name,self.businessName=child3.child(m).text(0).split(' : ')
                                    query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(node_type,table_name)
                                    result=execute_query(query)
                                    primary_key=result.values()[0][0]
                                    
                                    self.create_table(table_name,primary_key,node_type,'','fact_table',self.businessName)
                                
                                graph_adjacency.add_vertex(self.businessName)
                                return True
        return False
    
    def isMeasuresValid(self):
        isValid=False        
        for i in range(self.treeWidget_measures.topLevelItemCount()):
            item = self.treeWidget_measures.topLevelItem(i)
            
            for j in range(item.childCount()):
                measure_item=item.child(j)
                if  measure_item.checkState(0)== Qt.Checked: 
                    isValid=True
                    measurePath=self.getParentPath(measure_item)
                    measureParent=measurePath.split('/')[0]

                    if measureParent=="Count:": #get source table  
                        source_table=measure_item.text(0).split(' by ')[0]
                        node_type=graph.get_first_key_value()[1].get_first_node_type()
                        graph.get_first_key_value()[1].sources[node_type].add_source_table(source_table)
                        measure_name='count '+measure_item.text(0)
                        graph.get_first_key_value()[1].sources[node_type].add_measure(measure_name)

                    else:                      
                        node_type,table_name=tuple(measure_item.toolTip(0).split(' / '))
                        measure_value=measure_item.text(0)

                        if node_type in graph.tables[self.businessName].sources.keys(): #add measure value
                            graph.tables[self.businessName].sources[node_type].add_attribute(measure_value)
                        else: #create another table and add measure value
                            query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(node_type,table_name)
                            result=execute_query(query)
                            primary_key=result.values()[0][0]
                            if node_type=='Gph_Vtx':
                                new_simple_table=GraphTable(table_name,primary_key,measure_value)
                            else:
                                new_simple_table=Table(table_name,primary_key,measure_value)
                            graph.tables[self.businessName].add_source(node_type,new_simple_table)
                                       
        if isValid: 
            return (True,'')
        else: 
            return (False,"you have to to select at least one measure to continue")
    
    def isDimensionsValid(self):
        isValid=False

        for i in range(self.treeWidget_dimensions.topLevelItemCount()):
            item = self.treeWidget_dimensions.topLevelItem(i)    
            for j in range(item.childCount()):
                dimension_item=item.child(j)
                if  dimension_item.checkState(0)== Qt.Checked:
                    isValid= True 
                    dimensionPath=self.getParentPath(dimension_item)
                    dimensionParent=dimensionPath.split('/')[0]
                    node_type,table_name=tuple(dimension_item.toolTip(0).split(' / '))
                
                    if dimensionParent=="Time dimensions": 
                        attribute=dimension_item.text(0).split(' (')[0]
                        

                        if 'Date' not in graph.tables:
                            
                            role_name=attribute
                            table=self.create_table(table_name,'',node_type,role_name,'dimension_table','Date')
                            table.add_attribute(attribute)
                         
                            graph_adjacency.add_edge(self.businessName,'Date')
                        
                        else: 
                            graph.tables['Date'].add_role(attribute)
                            if node_type not in graph.tables['Date'].sources :
                                if node_type=='Gph_Vtx':
                                    table=GraphTable(table_name,attribute=attribute)
                                else:
                                    table=Table(table_name,attribute=attribute)
                                graph.tables['Date'].add_source(node_type,table)
                            else:
                                graph.tables['Date'].sources[node_type].add_attribute(attribute)

                        #fk should be in fact_table and we need the primary key with it
                        foreign_key=ForeignKey(attribute,'Date','Id')
                        if node_type in graph.tables[self.businessName].sources:
                            # graph.tables[self.businessName].sources[node_type].add_attribute(attribute)
                            graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)
                        else:#create another source in fact
                            query='''match(n:{})-[:Has_Primary_key]->(pk)
                                    match(n)-[bn:Has_MD_Prp]->({{name:"Business_Name"}})
                                    where bn.value='{}'
                                    return n.name,pk.name'''.format(node_type,self.businessName)
                            result=execute_query(query)
                            table_name,primary_key=result.values()[0]
                            
                            if node_type=='Gph_Vtx':
                                new_source_table=GraphTable(table_name,primary_key)
                            else:
                                new_source_table=Table(table_name,primary_key)

                            graph.tables[self.businessName].add_source(node_type,new_source_table)
                            graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)

                    else:  #normal dimension
                        role_name,business_name=dimension_item.text(0).split(' - ')
                        source_or_target=role_name.split(' : ')[0]
                        
                        dimension_business_name=business_name # to use it in queries in case i add _D to business name
                        if business_name == self.businessName:
                            business_name=business_name+'_D'

                        #1/Relationships
                        if node_type in ['Rel_Relatioship','Doc_Relationship','Gph_Edge']:
                            
                            dimension_type= 'Gph_Vtx' if node_type=='Gph_Edge' else 'Rel_Tab' if node_type=='Rel_Relatioship' else 'Doc_col' 
                            query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(dimension_type,table_name)
                            result=execute_query(query)
                            primary_key=result.values()[0][0]

                            if source_or_target == 'source':                                
                                
                                graph.tables[self.businessName].sources[node_type].add_attribute(primary_key)
                                
                                foreign_key=ForeignKey(table_name+primary_key,business_name,'Id')
                                graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)

                            else:

                                if node_type=='Gph_Edge':
                                    target_table_primary_key=primary_key
                                    graph.tables[self.businessName].sources[node_type].add_target_table_pk(target_table_primary_key)
                                    foreign_key=ForeignKey(table_name+target_table_primary_key,business_name,'Id')
                                    graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)
                                
                                else:
                                    relation_name=graph.tables[self.businessName].sources[node_type].relation_name
                                    query='''match(n:{} {{name:'{}'}}) -[:source]-> (fk)
                                                return fk.name'''.format(node_type,relation_name)
                                    result=execute_query(query)
                                    fk=result.values()[0][0] #fk to target (need it for Doc and Rel)
                                    graph.tables[self.businessName].sources[node_type].add_attribute(fk)
                                    foreign_key=ForeignKey(fk,business_name,'Id')
                                    graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)
                            if business_name not in graph.tables:
                                table=self.create_table(table_name,primary_key,dimension_type,role_name,'dimension_table',business_name)
                            else:
                                graph.tables[business_name].add_role(role_name)
                            graph_adjacency.add_edge(self.businessName,business_name)                        
                    
                    #1/ Suggested and original dimensions
                        else:    
                            relation_name=role_name.split(' : ')[1]                       
                            query='''Match ({{name:'{}'}}) -[rel:{}]- ()
                                    return  rel.maxOccur'''.format(relation_name,source_or_target)
                            result=execute_query(query)
                            maxOccur=result.values()[0][0]

                            query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(node_type,table_name)
                            result=execute_query(query)
                            primary_key=result.values()[0][0]
                            
                            if maxOccur=='n':

                                bridge_table_name=('Bridge_'+self.businessName+'_'+business_name).replace(' ','_')
                                bridge_table=self.create_table(table_name,'',node_type,role_name,'bridge_table',bridge_table_name)
                                graph_adjacency.add_edge(self.businessName,bridge_table_name)
                            #add foreign key (to bridge table) in fact table
                                fk_name=(self.businessName+'_'+business_name+'_Id').replace(' ','')
                                foreign_key=ForeignKey(fk_name,bridge_table_name,'GroupId')

                            #we have to test if node type exist
                                if node_type in graph.tables[self.businessName].sources:
                                    graph.tables[self.businessName].sources[node_type].add_bridge_foreign_key(foreign_key)
                                else:
                                    query='''match(n:{})-[:Has_Primary_key]->(pk)
                                                match(n)-[bn:Has_MD_Prp]->({{name:"Business_Name"}})
                                                where bn.value='{}'
                                                return n.name,pk.name'''.format(node_type,self.businessName)
                                    result=execute_query(query)
                                    new_source_table_name,new_source_primary_key=result.values()[0]
                                    
                                    if node_type=='Gph_Vtx':
                                        new_source_table=GraphTable(new_source_table_name,new_source_primary_key)   
                                        graph.tables[self.businessName].add_source(node_type,new_source_table)           
                                        # graph.tables[self.businessName].sources[node_type].add_target_primary_key(target_pk)

                                    else:
                                        new_source_table=Table(new_source_table_name,new_source_primary_key)
                                        graph.tables[self.businessName].add_source(node_type,new_source_table)

                                    
                                    graph.tables[self.businessName].sources[node_type].add_bridge_foreign_key(foreign_key)
                            
                            #create dimension_table
                                table=self.create_table(table_name,primary_key,node_type,'','dimension_table',business_name)
                                graph_adjacency.add_edge(bridge_table_name,business_name)
                            #adding foreign key in bridge table to table
                                foreign_key=ForeignKey(table_name+primary_key,business_name,'Id')
                                bridge_table.add_foreign_key(foreign_key)

                                if node_type=='Gph_Vtx':

                                    query='''match(n:{})-[:Has_Primary_key]->(pk)
                                                match(n)-[bn:Has_MD_Prp]->({{name:"Business_Name"}})
                                                where bn.value='{}'
                                                return n.name,pk.name'''.format(node_type,self.businessName)
                                    result=execute_query(query)
                                    target_table_name,target_primary_key=result.values()[0]
                                    target_pk=TargetPrimaryKey(relation_name,target_table_name,target_primary_key)
                                    
                                    bridge_table.add_target_primary_key(target_pk)
                                    bridge_table.add_attribute(primary_key)
                                
                                else:

                                    relation='source' if source_or_target=='target' else 'target'
                                    query='''match ({{name:'{}'}})-[:{}]-(col)
                                            return col.name'''.format(relation_name,relation)
                                    result=execute_query(query)
                                    fk=result.values()[0][0]
                                    
                                    bridge_table.add_attribute(fk)            
                                    bridge_table.add_attribute(primary_key)
                            
                            else:
                                if business_name in graph.tables:
                                    graph.tables[business_name].add_role(role_name)
                                else:
                                    table=self.create_table(table_name,primary_key,node_type,role_name,'dimension_table',business_name)
                                
                                graph_adjacency.add_edge(self.businessName,business_name)

                                if node_type in graph.tables[self.businessName].sources:

                                    if node_type=='Gph_Vtx':
                                        fk_name=(business_name+'_Id').replace(' ','')  
                                        foreign_key=ForeignKey(fk_name,business_name,'Id')
                                        target_pk=TargetPrimaryKey(relation_name,table_name,primary_key)
                                        graph.tables[self.businessName].sources[node_type].add_target_primary_key(target_pk)
                                    
                                    else:
                                        query='''match({{name:'{}'}})-[:{}]-(col)
                                                return col.name'''.format(relation_name,source_or_target)
                                        result=execute_query(query)
                                        fk=result.values()[0][0]
                                        foreign_key=ForeignKey(fk,business_name,'Id')

                                    graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)
                                
                                else:
                                    query='''match(n:{})-[:Has_Primary_key]->(pk)
                                                match(n)-[bn:Has_MD_Prp]->({{name:"Business_Name"}})
                                                where bn.value='{}'
                                                return n.name,pk.name'''.format(node_type,self.businessName)
                                    result=execute_query(query)
                                    table_name,primary_key=result.values()[0]
                                    
                                    if node_type=='Gph_Vtx':
                                        new_source_table=GraphTable(table_name,primary_key)              
                                        graph.tables[self.businessName].sources[node_type].add_target_primary_key(target_pk)

                                    else:
                                        new_source_table=Table(table_name,primary_key)
                                    
                                    graph.tables[self.businessName].add_source(node_type,new_source_table)
                                    graph.tables[self.businessName].sources[node_type].add_foreign_key(foreign_key)

                        #Properties # he should select properties or we will return error here               
                        if dimension_item.childCount() > 0 :
                
                            for k in range(dimension_item.childCount()):                 
                                for l in range(dimension_item.child(k).childCount()):
                                    propertie_item=dimension_item.child(k).child(l)
                                    if propertie_item.checkState(0)==Qt.Checked:
                                        if dimension_item.child(k).text(0)=="Properties":
                                            table.add_attribute(propertie_item.text(0))
                                        else:# verify if it exist or create one (source)
                                            node_type,table_name=propertie_item.toolTip(0).split(' / ')
                                            if node_type not in graph.tables[business_name].sources:
                                                query='''match(n:{})-[:Has_Primary_key]->(pk)
                                                        match(n)-[bn:Has_MD_Prp]->({{name:"Business_Name"}})
                                                        where bn.value='{}'
                                                        return n.name,pk.name'''.format(node_type,dimension_business_name)
                                                result=execute_query(query)
                                                table_name,primary_key=result.values()[0]
                                                if node_type=='Gph_Vtx':
                                                     new_simple_table=GraphTable(table_name,primary_key,propertie_item.text(0))
                                                else:                                                
                                                    new_simple_table=Table(table_name,primary_key,propertie_item.text(0))
                                                
                                                graph.tables[business_name].add_source(node_type,new_simple_table)
                                            else:
                                                graph.tables[business_name].sources[node_type].add_attribute(propertie_item.text(0))
        
        return isValid
    
    def isHierarchiesValid(self):
        
        def find_children(item,level):
            parent_table_name,parent_business_name=item.text(0).split(' : ')
            for j in range(1,item.childCount()):
                child_item=item.child(j)
                if  child_item.checkState(0)== Qt.Checked :  
                    
                    table_name,business_name=child_item.text(0).split(' : ')
                    if business_name not in graph.tables:
                        
                        query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(node_type,table_name)
                        result=execute_query(query)
                        primary_key=result.values()[0][0]
                        
                        if node_type =='Gph_Vtx':
                            table=self.create_table(table_name,primary_key,node_type,'','level_table',business_name)
                            
                            foreign_key=ForeignKey(primary_key,business_name,'Id')
                            level.add_foreign_key(foreign_key) 
                            
                            query='''match(:{} {{name:'{}'}})-[:target|source]-(role)-[:target|source]-(:{} {{name:'{}'}})
                                        return role.name'''.format(node_type,parent_table_name,node_type,table_name)
                            result=execute_query(query)
                            role_name=result.values()[0][0]

                            target_pk=TargetPrimaryKey(role_name,table_name,primary_key)
                            level.add_target_primary_key(target_pk)

                        else:
                            table=self.create_table(table_name,primary_key,node_type,'','level_table',business_name)
                            
                            query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-()-[:target|source]-()-[:target|source]-(col)
                                return col.name'''.format(node_type,table_name)
                            result=execute_query(query)
                            fk=result.values()[0][0]
    
                            foreign_key=ForeignKey(fk,business_name,'Id')
                            if foreign_key not in level.foreign_keys:
                                level.add_foreign_key(foreign_key)
                    else:
                        #adgency graph
                        if node_type not in graph.tables[business_name].sources:
                            
                            if node_type =='Gph_Vtx':
                                table=GraphTable(table_name,primary_key)
                                graph.tables[business_name].add_source(node_type,table)
                            else:
                                table=Table(table_name,primary_key)
                                graph.tables[business_name].add_source(node_type,table)
                        else:
                            #we retrive the table to add attributes to it
                            table=graph.tables[business_name].sources[node_type]
                    
                    graph_adjacency.add_edge(parent_business_name,business_name)
                              
                    properties_item = child_item.child(0)                   
                    for k in range(properties_item.childCount()):
                        if properties_item.child(k).checkState(0) == Qt.Checked:
                            attribute=properties_item.child(k).text(0)
                            if attribute not in table.selected_attributes:
                                table.add_attribute(attribute)     
               
                    find_children(child_item,table)
                else:
                    return

        for i in range(self.treeWidget_hierarchies.topLevelItemCount()):
            item = self.treeWidget_hierarchies.topLevelItem(i)
            parent_table_name=item.text(0)
            node_type,dimension_bn = item.toolTip(0).split('/')
            if dimension_bn == self.businessName:
                dimension_bn=dimension_bn+'_D'

            for j in range(item.childCount()):
                child_item = item.child(j)
                # level 1 is checked
                if child_item.checkState(0) == Qt.Checked:

                    table_name,business_name=child_item.text(0).split(' : ')
                    query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-> (pk)
                                                return pk.name'''.format(node_type,table_name)
                    result=execute_query(query)
                    primary_key=result.values()[0][0]
           
                    if business_name not in graph.tables:
                        table=self.create_table(table_name,primary_key,node_type,'','level_table',business_name)
                                          
                    else:     
                        if node_type not in graph.tables[business_name].sources:
                            
                            if node_type =='Gph_Vtx':
                                table=GraphTable(table_name,primary_key)
                                graph.tables[business_name].add_source(node_type,table)
                            
                            else:
                                table=Table(table_name,primary_key)
                                graph.tables[business_name].add_source(node_type,table)

                        else:
                            #we retrive the table to add attributes to it
                            table=graph.tables[business_name].sources[node_type]
                   
                    graph_adjacency.add_edge(dimension_bn,business_name)

                #adding foreign key and target_pk for Gph_Vtx
                    if node_type=='Gph_Vtx':
                        fk_name=(business_name+'_id').replace(' ','')
                        foreign_key=ForeignKey(fk_name,business_name,'Id')
                        graph.tables[dimension_bn].sources[node_type].add_foreign_key(foreign_key) 
                        
                        query='''match(:{} {{name:'{}'}})-[:target|source]-(role)-[:target|source]-(:{} {{name:'{}'}})
                                    return role.name'''.format(node_type,parent_table_name,node_type,table_name)
                        result=execute_query(query)
                        role_name=result.values()[0][0]

                        target_pk=TargetPrimaryKey(role_name,table_name,primary_key)
                        graph.tables[dimension_bn].sources[node_type].add_target_primary_key(target_pk)

                    else:

                        query='''match(n:{} {{name:'{}'}})-[:Has_Primary_key]-()-[:target|source]-()-[:target|source]-(col)-[]-({{ name:'{}'}})
                                return col.name'''.format(node_type,table_name,parent_table_name)

                        result=execute_query(query)
                        fk=result.values()[0][0]
                        foreign_key=ForeignKey(fk,business_name,'Id')
                        graph.tables[dimension_bn].sources[node_type].add_foreign_key(foreign_key)    

                    properties_item = child_item.child(0)
                    for k in range(properties_item.childCount()):
                        if properties_item.child(k).checkState(0) == Qt.Checked:
                            attribute=properties_item.child(k).text(0)
                            if attribute not in table.selected_attributes:
                                table.add_attribute(attribute)
                    
                    find_children(child_item,table)  
        return True
    


    def show_mesures(self):
        
        key,value=graph.get_first_key_value()
        fact_type=value.get_first_node_type()

        if fact_type in ['Gph_Vtx','Rel_Tab','Doc_col'] :
            fact_name=value.sources[fact_type].table_name
        #1/ origine measures
            query='''MATCH (n:{})-[:ComposedOf]->(columns) 
                        Match (columns) -[dataType:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                        MATCH (columns)-[column_bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        WHERE n.name='{}' AND NOT (n)-[:Has_Primary_key]->(columns) And not (columns)<-[:source]-() And not dataType.value in ['Date','String']
                        RETURN columns.name,dataType.value,column_bn.value'''.format(fact_type,fact_name)
            measures_business_name_list=list()
            result=execute_query(query)
            origine_measures_item = self.createTopLevelItem('Measures from the selected fact',self.treeWidget_measures)
            for record in result:
                name = record.values()[0]
                data_type = record.values()[1]
                measures_business_name_list.append(record.values()[2])
                measure = self.createCheckebleItem(origine_measures_item)
                measure.setText(0,name +' : ' + data_type)
                measure.setToolTip(0,fact_type+' / '+fact_name)
            #2/ (Suggested)
            query='''MATCH (n)-[bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        MATCH (n)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                        MATCH (n)-[:ComposedOf]->(cols)
                        MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                        MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        WHERE bn.value="{}" AND NOT head(labels(n))="{}" AND NOT (n)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND NOT cbn.value in {} And not dt.value in ['Date','String']
                        RETURN head(labels(n)),n.name, cols.name,cbn.value, dt.value'''.format(self.businessName,fact_type,measures_business_name_list)

            result=execute_query(query)
            records = result.values()  # fetch the records returned by the query
            num_records = len(records)
            col_bn_list=list()
            if num_records > 0 :
                suggested_measures_item = self.createTopLevelItem('Suggested measures',self.treeWidget_measures)
                for record in records:
                
                    node_type,node_name,col_name,col_bn,data_type=record
                    if col_bn not in col_bn_list:
                        col_bn_list.append(col_bn)
                        measure = self.createCheckebleItem(suggested_measures_item)
                        measure.setText(0,col_name+' : ' + data_type)
                        measure.setToolTip(0,node_type+' / '+node_name)
                    
        elif fact_type in ['Rel_Relatioship','Doc_Relationship']:
            fact_name=value.sources[fact_type].relation_name
            query='''MATCH (n:{})-[rel:source|target]->(columns)-[:ComposedOf]-(tables)
                    WHERE n.name='{}'
                    RETURN type(rel), columns.name, tables.name'''.format(fact_type,fact_name)

            result=execute_query(query)
            count_measures_item = self.createTopLevelItem('Count:',self.treeWidget_measures)

            for record in result:
                rel_type=record.values()[0]
                column_name = record.values()[1]
                table_name = record.values()[2]
                if rel_type=="source":
                    source=table_name
                else :
                    target=table_name
            measure =self.createCheckebleItem(count_measures_item)
            measure.setText(0,source +' by ' + target)
            
        else: #Gph_Edge
            fact_name=value.sources[fact_type].relation_name
            # count() // this query retrieve even gph_prp that don't have Data_type but this is temporary i will change it later (all will have data type)
            query='''MATCH (n:{})-[rel:source|target|ComposedOf]->(nodes)
                        WHERE n.name='{}'
                        OPTIONAL MATCH (nodes)-[mdPrp:Has_MD_Prp]-(:MD_Prp{{name:'Data_Type'}})
                        RETURN type(rel), nodes.name,mdPrp.value'''.format(fact_type,fact_name)
            result=execute_query(query)
            for record in result:
                rel_type=record.values()[0]
                node_name = record.values()[1]
                if rel_type=="source":
                    source=node_name
                elif rel_type=="target" :
                    target=node_name
                   
            count_measures_item = self.createTopLevelItem('Count:',self.treeWidget_measures)
            measure = self.createCheckebleItem(count_measures_item)
            measure.setText(0,source +' by ' + target)
                           
    def show_dimensions(self):

        additional_properties_query='''MATCH (n)-[bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        MATCH (n)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                        MATCH (n)-[:ComposedOf]->(cols)
                        MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                        MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        WHERE bn.value="{}" AND NOT head(labels(n))="{}" AND NOT (n)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND NOT cbn.value in {} And dt.value <> 'Date'
                        RETURN head(labels(n)),n.name, cols.name, dt.value'''
        #//origine ones :
        origine_dimensions_item = self.createTopLevelItem('Dimensions from the selected facts',self.treeWidget_dimensions)
        role_bn_list=list()
        fact_type_list=list()
        col_bn_list=list()
        for key in graph.tables[self.businessName].sources.keys():
            fact_type_list.append(key)
            fact_type=key
            if type(graph.tables[self.businessName].sources[key]) is RelationshipTable:
                fact_name=graph.tables[self.businessName].sources[key].relation_name
            else:
                fact_name=graph.tables[self.businessName].sources[key].table_name

            query_template = '''MATCH (start:{} {{name: '{}'}}) {}<-[rel:target|source]-(role)-[:target|source]->{} (dimension)
                    MATCH (start)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                    MATCH (dimension)-[dbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                    MATCH (role)-[rbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                    WHERE NOT rbn.value IN {}
                    Match (dimension) -[:ComposedOf]->(cols)
                    MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                    MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                    where NOT (dimension)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND dt.value <> 'Date'
                    RETURN type(rel),head(labels(start)),start.name,role.name,rbn.value, dimension.name, dbn.value,cols.name,cbn.value,dt.value'''

            query_template2='''MATCH (start:{} {{name: '{}'}}) -[rel:target|source]->{} (dimension)
                        MATCH (start)-[sbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        MATCH (start)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                        MATCH (dimension)-[dbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        Match (dimension) -[:ComposedOf]->(cols)
                        MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                        where NOT (dimension)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND dt.value <> 'Date'
                        RETURN type(rel),head(labels(start)),start.name, start.name+' to '+dimension.name as Role, sbn.value+' to '+dbn.value as RBN, dimension.name, dbn.value,cols.name,cbn.value,dt.value'''

            if fact_type in ['Rel_Tab','Doc_col']:
                query = query_template.format(fact_type, fact_name, '-[:ComposedOf]->()', '()<-[:ComposedOf]-', role_bn_list)
            elif fact_type == 'Gph_Vtx':
                query = query_template.format(fact_type, fact_name, '', '', role_bn_list)
            elif fact_type in ['Rel_Relatioship','Doc_Relationship']:
                query = query_template2.format(fact_type, fact_name, '()<-[:ComposedOf]-')
            else : 
                query = query_template2.format(fact_type, fact_name,'')

            result = execute_query(query) 
            role_list=list()
            records=result.values()
            for i,record in enumerate(records):               
                rel_type,node_type,node_name,role_name,role_bn,dimension_name,dbn,column_name,cbn,col_data_type=record
                dimension_kind=rel_type+' : '+role_name
                if dimension_kind not in role_list: 
        
                    col_bn_list.clear()                                       
                    role_list.append(dimension_kind)
                    role_bn_list.append(role_bn)
                    col_bn_list.append(cbn)  

                    dimension_item = self.createCheckebleItem(origine_dimensions_item)
                    dimension_item.setText(0,rel_type+' : ' +role_name +' - '+dbn)
                    dimension_item.setToolTip(0, node_type+' / '+dimension_name) 

                    properties_item= self.createChildItem('Properties',dimension_item)
                                                                                       
                else : 
                    col_bn_list.append(cbn)

                propertieItem = self.createCheckebleItem(properties_item)
                propertieItem.setText(0,column_name +' : ' +col_data_type)
                propertieItem.setToolTip(0, node_type+' / '+dimension_name)
                if i<len (records)-1:
                    next_role_name=records[i+1][3]
                    next_rel_type=records[i+1][0]
                elif i==len(records)-1 : 
                    next_role_name=''
                    next_rel_type=''
                #Additional Properties:
                if next_rel_type+' : '+next_role_name != dimension_kind or next_role_name=='' :
                    dimension_type=fact_type if fact_type in ['Gph_Vtx','Rel_Tab','Doc_col'] else 'Gph_Vtx' if fact_type=='Gph_Edge' else 'Rel_Tab' if fact_type=='Rel_Relatioship' else 'Doc_col' if fact_type=='Doc_Relationship' else None                
                    
                    result=execute_query(additional_properties_query.format(dbn,dimension_type,col_bn_list))
                    records2 = result.values() 
                    num_records = len(records2)

                    if num_records > 0 :   
                        additional_properties_item= self.createChildItem('Additional properties',dimension_item)                        
                        for record in records2:
                            node_type,node_name,col_name,data_type=record
                            addPropertieItem = self.createCheckebleItem(additional_properties_item)
                            addPropertieItem.setText(0,col_name +' : ' + data_type)
                            addPropertieItem.setToolTip(0, node_type+' / '+node_name)                 
    
        # that have the same business_name :
        if fact_type_list[0] in ['Gph_Vtx','Rel_Tab','Doc_col']:
            dimension_filter_dict=dict()
            suggested_fact_type_list={'Gph_Vtx','Rel_Tab','Doc_col'}-set(fact_type_list)
            suggested_dimensions_item = self.createTopLevelItem('Suggested dimensions',self.treeWidget_dimensions)
            for fact in suggested_fact_type_list:
                if fact =='Gph_Vtx':
                    query='''MATCH (start:{})-[bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})      
                            where bn.value='{}' 
                            Match (start)<-[rel:target|source]-(role) -[:source|target]->(dimension)  
                            MATCH (role)-[rbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                            where Not rbn.value In {}   
                            MATCH (dimension)-[dbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                            Match (dimension) -[:ComposedOf]->(cols)
                            MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                            MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                            where NOT (dimension)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND dt.value <> 'Date'
                            RETURN type(rel),head(labels(start)),start.name,role.name,rbn.value,dimension.name,dbn.value,cols.name,cbn.value, dt.value 
                            Order By type(rel), role.name'''.format(fact,self.businessName,role_bn_list)
                else:
                    query='''MATCH (start:{})-[bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})      
                            where bn.value='{}' 
                            Match (start)-[:ComposedOf]->()<-[rel:target|source]-(role)-[:source|target]->()<-[:ComposedOf]-(dimension)  
                            MATCH (role)-[rbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                            where Not rbn.value In {}   
                            MATCH (dimension)-[dbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                            Match (dimension) -[:ComposedOf]->(cols)
                            MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                            MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                            where NOT (dimension)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND dt.value <> 'Date'
                            RETURN type(rel),head(labels(start)),start.name,role.name,rbn.value,dimension.name,dbn.value,cols.name,cbn.value, dt.value 
                            Order By type(rel),role.name'''.format(fact,self.businessName,role_bn_list)
            
                result = execute_query(query) 
                records = result.values()  
                num_records = len(records)
                if num_records > 0 :
                                       
                    for i,record in enumerate(records):
                        rel_type,node_type,node_name,role_name,role_bn,dimension_name,dbn,col_name,cbn,data_type=record 
                        aa=rel_type+role_bn
                        
                        if aa not in dimension_filter_dict :                            
                            dimension_filter_dict[aa]=node_type
                            col_bn_list.clear() 
                            col_bn_list.append(cbn)
                            dimension_item = self.createCheckebleItem(suggested_dimensions_item)
                            dimension_item.setText(0, rel_type + ' : ' + role_name+ ' - '+dbn)
                            dimension_item.setToolTip(0,node_type+' / '+dimension_name) 
                            properties_item= self.createChildItem('Properties',dimension_item)
                    
                        elif node_type != dimension_filter_dict[aa]:
                            continue
                        else:
                            col_bn_list.append(cbn)

                        propertieItem = self.createCheckebleItem(properties_item)
                        propertieItem.setText(0,col_name +' : ' +data_type)
                
                        if i<len (records)-1:
                            next_role_bn=records[i+1][4]
                            next_rel_type=records[i+1][0]
                        elif i==len(records)-1 : 
                            next_role_bn=''
                        #Additional Properties:
                        if next_rel_type+next_role_bn != aa or next_role_bn=='' :

                            dimension_type=node_type if node_type in ['Gph_Vtx','Rel_Tab','Doc_col'] else 'Gph_Vtx' if node_type=='Gph_Edge' else 'Rel_Tab' if node_type=='Rel_Relatioship' else 'Doc_col' if node_type=='Doc_Relationship' else None                
                            result=execute_query(additional_properties_query.format(dbn,dimension_type,col_bn_list))
                            records2 = result.values() 
                            num_records = len(records2)

                            if num_records > 0 :   
                                additional_properties_item= self.createChildItem('Additional properties',dimension_item)                        
                                for record in records2:
                                    node_type,node_name,col_name,data_type=record
                                    addPropertieItem = self.createCheckebleItem(additional_properties_item)
                                    addPropertieItem.setText(0,col_name +' : ' + data_type)
                                    addPropertieItem.setToolTip(0, node_type+' / '+node_name)  
        
        # Time dimension (special case) / look for the property that have "Date" data-type 
        query='''MATCH (start)-[bn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                    where bn.value='{}'
                    MATCH (start)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                    MAtch (start)-[:ComposedOf]->(cols)-[mdp:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}}) 
                    where mdp.value='Date'
                    MAtch (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}}) 
                    return dl.name,head(labels(ds)),ds.name,head(labels(start)),start.name,cols.name,cbn.value'''.format(self.businessName)
        result = execute_query(query) 
        records = result.values()  # fetch the records returned by the query
        num_records = len(records)
        if num_records > 0 :
            time_dimensions_item = self.createTopLevelItem('Time dimensions',self.treeWidget_dimensions)
            for record in records:
                dl_name,ds_type,ds_name,node_type,node_name,column_name,cbn=record 
                dimension_item = self.createCheckebleItem(time_dimensions_item)
                dimension_item.setText(0, column_name +' ( '+ cbn+' )')
                dimension_item.setToolTip(0, node_type+' / '+node_name)

    def show_hierarchies(self):
        
        levels_bn_list=list()

        def find_hierarchies_level(dimension_type,level_name,levels_bn_list,item):

            query_template='''MATCH (start:{} {{name: '{}'}}) {}<-[rel:target|source]-()-[:source|target]->{} (level)
                        where rel.maxOccur <>'n'
                        MATCH (start)<-[:ComposedOf]-(ds)<-[:ComposedOf]-(dl)
                        MATCH (level)-[lbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        WHERE NOT lbn.value IN {}
                        MATCH (level)-[:ComposedOf]->(cols)
                        MATCH (cols)-[dt:Has_MD_Prp]->(:MD_Prp {{name:"Data_Type"}})
                        MATCH (cols)-[cbn:Has_MD_Prp]->(:MD_Prp {{name:"Business_Name"}})
                        where NOT (level)-[:Has_Primary_key]->(cols) AND NOT (cols)<-[:source]-() AND dt.value <> 'Date'
                        RETURN  level.name, lbn.value,cols.name,cbn.value,dt.value
                        Order BY level.name'''
            
            if dimension_type in ['Gph_Vtx']:
                query=query_template.format(dimension_type,level_name,'','',levels_bn_list+[self.businessName])
            else:    
                query=query_template.format(dimension_type,level_name, '-[:ComposedOf]->()', '()<-[:ComposedOf]-',levels_bn_list+[self.businessName])

            levels_filter_list=list()

            result = execute_query(query)
            records = result.values()  
            num_records = len(records)
            if num_records==0:
                levels_bn_list.pop()
                return
            else :
                for record in records:  
                    level_name,lbn,col_name,col_bn,col_dt=record
                    if level_name not in levels_filter_list: 
                        levels_filter_list.append(level_name)                        
                        level_item = self.createCheckebleItem(item)
                        level_item.setText(0,level_name +" : "+ lbn)
                        # level_item.setToolTip(0,dimension_type)
                        levels_bn_list.append(lbn)
                        properties_item= self.createChildItem('Properties',level_item)
                        find_hierarchies_level(dimension_type,level_name,levels_bn_list,level_item)
                        
                    else:
                        pass
                    propertieItem = self.createCheckebleItem(properties_item)
                    propertieItem.setText(0,col_name +' : '+col_dt )

        for key , value in graph.tables.items():
            if value.description == 'dimension_table' and key != 'Date': 
                dbn=key 
                dimension_type=value.get_first_node_type()
                dimension_name=value.sources[dimension_type].table_name
                levels_bn_list.clear()
                levels_bn_list.append(dbn)
                dimension_item= self.createTopLevelItem(dimension_name,self.treeWidget_hierarchies)
                dimension_item.setToolTip(0,dimension_type+'/'+dbn)
                find_hierarchies_level(dimension_type,dimension_name,levels_bn_list,dimension_item)



    def generate_graph(self):
        
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hamza"))
        def execute_query(query):
            with driver.session() as session:
                return session.run(query)

        query='''Match (n:Fact)
                RETURN MAX(n.graphNumber)'''
        result=execute_query(query).values()  

        if result[0][0] is None:
            self.graph_number=1
        else:
            self.graph_number=result[0][0]+1
        
        measure_list=graph.tables[self.businessName].get_measures()

        query='''CREATE (:Fact {{name: "{}",measures:{},graphNumber:{}}})'''.format(self.businessName,measure_list,self.graph_number)
        execute_query(query)
            
        for dimension_name in graph_adjacency.get_adjacent_vertices(self.businessName):
            entity=graph.tables[dimension_name]

            if dimension_name == 'Date':
                attributes=['Id : Number','day : String']
            elif entity.description == 'bridge_table':
                attributes=['IdGroup : Number']+[entity.get_selected_attributes()+' : Number']
            else:
                attributes=['Id : Number']+entity.get_selected_attributes()

            for role in entity.role_names:

                query='''Match (f:Fact {{graphNumber:{}  }})
                    MERGE (l:Level {{name: '{}', properties :{}, graphNumber:{}  }})
                    MERGE (f)-[r:Has_Dimension {{role: "{}"}}]->(l)'''.format(self.graph_number,dimension_name,attributes,self.graph_number,role)                    
                execute_query(query)

            def create_levels_node(child_name,parent_name):

                entity=graph.tables[child_name]
                attributes=['Id : Number']+entity.get_selected_attributes()
                query='''Match (l1:Level {{name:'{}',graphNumber:{} }})
                        MERGE (l2:Level {{name: "{}",properties:{},graphNumber:{} }})
                        MERGE (l1)-[r:Has_Level]->(l2)'''.format(parent_name,self.graph_number,child_name,attributes ,self.graph_number)
                execute_query(query)
                
                for level_name in graph_adjacency.get_adjacent_vertices(child_name):
                    create_levels_node(level_name,child_name)

            for level_name in graph_adjacency.get_adjacent_vertices(dimension_name):

                create_levels_node(level_name,dimension_name)


    def generate_olapCube(self):
        
        graph_adjacency_copy=copy.deepcopy(graph_adjacency)

        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "1234"))
        def execute_query(query):
            with driver.session() as session:
                return session.run(query)
        
        client = MongoClient('mongodb://localhost:27017')
        db = client.StackExchange

        source_database_name='stackexchange'   

        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='hamza',
        )
        cursor = conn.cursor()

        # first we create the database
        database_name = "Graph_"+str(self.graph_number)
        create_database_query = f"CREATE DATABASE {database_name}"
        cursor.execute(create_database_query)
        conn.commit()
        cursor.close()
        conn.close()

        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='hamza',
            database=database_name
        )
        cursor = conn.cursor()

    # insert the name and structure of our graph     
        insert_query = "INSERT INTO graphs.data_history VALUES (%s,%s,%s)"

        structure="Fact : "+self.businessName+'\n'
        measure_list=graph.tables[self.businessName].get_measures()
        structure = structure+"Measures : [" + ', '.join(measure_list) + "] \n \n"
        
        for key , value in graph_adjacency.adjacency_list.items():
            structure=structure+key+' : ['+ ', '.join(value)  +'] \n' 

        cursor.execute(insert_query, (database_name,structure,''))
        conn.commit()  


        def find_leaf_nodes(graph):
            leaf_nodes = []
            for node in graph.adjacency_list:
                if not graph.adjacency_list[node]:
                    leaf_nodes.append(node)
            return leaf_nodes

        
        def create_table(node_name):

            def create_date_table(node_name):
  
                query = f"CREATE TABLE {node_name} (Id VARCHAR(255),"
                query += f"day TEXT, PRIMARY KEY (Id) ); "
                return query
    
            def create_bridge_table(node_name):
                
                table_name=node_name
                first_node_type=graph.tables[node_name].get_first_node_type()
                foreign_key=graph.tables[node_name].sources[first_node_type].foreign_keys[0]

                query = f"CREATE TABLE {table_name} (GroupId INT,"
                query += f"{foreign_key.column} INT, "
                query += f"PRIMARY KEY (GroupId,{foreign_key.column}),"
                query += f"FOREIGN KEY ({foreign_key.column}) REFERENCES {foreign_key.references.replace(' ','_')}({foreign_key.references_column}));"
                return query

            def create_fact_table(node_name):
                
                table_name=node_name.replace(' ','_')
                attributes = []
                foreign_keys = []
                composite_primary_key=''
                group_by_columns=[]

                for node_type,data in graph.tables[node_name].sources.items():
                    attributes.extend(data.selected_attributes)
                    
                    foreign_keys.extend(data.foreign_keys)
                    for foreign_key in data.foreign_keys:
                        if foreign_key.references=='Date':
                            attributes.append(foreign_key.column+' : VARCHAR(255)')
                        else:
                            attributes.append(foreign_key.column+' : Number')

                    foreign_keys.extend(data.bridge_foreign_keys)
                    for bridge_foreign_key in data.bridge_foreign_keys:
                        attributes.append(bridge_foreign_key.column+' : Number')
                    
                query = f"CREATE TABLE {table_name} ("
                for attribute in attributes:
                    attr_name, attr_type = attribute.split(' : ')
                    attr_type = attr_type.replace('Number', 'Int').replace('String', 'Text')
                    query += f"{attr_name} {attr_type}, "

                for foreign_key in foreign_keys:
                    foreign_key_column = foreign_key.column
                    references_table = foreign_key.references.replace(' ','_')
                    references_column = foreign_key.references_column

                    query += f"FOREIGN KEY ({foreign_key_column}) REFERENCES {references_table}({references_column}), "
                    composite_primary_key+=f"{foreign_key_column}, "
                    group_by_columns.append(foreign_key_column)
                
                composite_primary_key = composite_primary_key.rstrip(', ')
                query += f" PRIMARY KEY ({composite_primary_key}) "           
                query += ");"
                               
                columns=[attr.split(' : ')[0]  for attr in attributes]
        
                return (query,columns,group_by_columns)

            def create_relationship_fact_table(node_name):
                
                table_name=node_name.replace(' ','_')
                node_type=graph.tables[node_name].get_first_node_type()
                measure_name=graph.tables[node_name].sources[node_type].measure_name 
                measure_name=measure_name.replace(' ','_')
                composite_primary_key=''
                
                query = f"CREATE TABLE {table_name} ({measure_name} INT," 

                for foreign_key in graph.tables[node_name].sources[node_type].foreign_keys:
                    foreign_key_column = foreign_key.column
                    references_table = foreign_key.references.replace(' ','_')
                    references_column = foreign_key.references_column

                    query += f"{foreign_key_column} INT, "
                    query += f"FOREIGN KEY ({foreign_key_column}) REFERENCES {references_table}({references_column}), "
                    composite_primary_key+=f"{foreign_key_column}, "
                
                composite_primary_key = composite_primary_key.rstrip(', ')
                query += f" PRIMARY KEY ({composite_primary_key}) "           
                query += ");"
                return query

            def create_simple_table(node_name):
                
                table_name = node_name.replace(' ', '_')  # Modify the category name if needed
                attributes = []
                foreign_keys = []

                for node_type,data in graph.tables[node_name].sources.items():
                    attributes.extend(data.selected_attributes)
                    foreign_keys.extend(data.foreign_keys)
                    
                    for foreign_key in data.foreign_keys:
                        attributes.append(foreign_key.column+' : Number')
                    
                query = f"CREATE TABLE {table_name} (Id INT,"

                for attribute in attributes:
                    attr_name, attr_type = attribute.split(' : ')
                    # attr_name = attr_name.strip()
                    # attr_type = attr_type.strip()
                    attr_type = attr_type.replace('Number', 'Int').replace('String', 'Text')
                    query += f"{attr_name} {attr_type}, "

                query += f"PRIMARY KEY (Id),"

                for foreign_key in foreign_keys:
                    foreign_key_column = foreign_key.column
                    references_table = foreign_key.references.replace(' ','_')
                    references_column = foreign_key.references_column
                    query += f"FOREIGN KEY ({foreign_key_column}) REFERENCES {references_table}({references_column}), "
                    
                query = query.rstrip(', ')
                query += ");"
                return query


            if graph.tables[node_name].description=='bridge_table':
                result=create_bridge_table(node_name)
            elif graph.tables[node_name].description=='fact_table':
                result=create_fact_table(node_name)
            elif  graph.tables[node_name].description=='relationship_fact_table':
                result=create_relationship_fact_table(node_name)
            elif node_name=='Date':
                result=create_date_table(node_name)
            else:
                result=create_simple_table(node_name)

            return result
        
        
        '''node_name is the business name and source type is the source of each table (rel_tab , doc_col...)'''  
       
        def retrive_data(node_name,source_type=None):

            columns=[] 

            if graph.tables[node_name].description == 'relationship_fact_table' :  
                
                
                source_table_name=graph.tables[node_name].sources[source_type].source_table_name
                for attribute in graph.tables[node_name].sources[source_type].selected_attributes:
                    columns.append(attribute)

                if source_type=='Rel_Relatioship':
                    
                    query='select count(*) ,'+", ".join(columns)+' from '+source_database_name+'.'+source_table_name + ' group by '+','.join(columns)
                    cursor.execute(query)
                    result=cursor.fetchall()
                
                elif source_type=='Doc_Relationship':
                    collection = db[source_table_name]
                    pipeline = [
                        {
                            '$group': {
                                '_id': {
                                  
                                },
                                'count': {'$sum': 1}
                            }
                        }
                    ]
                    projection = pipeline[0]['$group']['_id']
                    for column in columns:
                        projection[column] = '$'+column

                    doc_result = list(collection.aggregate(pipeline))
                    
                    # convert result to a list of tuples
                    result= [tuple(doc['_id'].get(column,'') for column in columns) for doc in doc_result]

                    

  
                else:
                   # the group by happenautomatically
                    relation_name=graph.tables[node_name].sources[source_type].relation_name
                    target_pk=graph.tables[node_name].sources[source_type].target_table_primary_key
                    
                    if target_pk =='':
                        query=f'''MATCH (s:{source_table_name})-[r:{relation_name}]-(t) 
                            RETURN COUNT(r) , s.{columns[0]} '''
                    elif len(columns) == 0 :
                        query=f'''MATCH (s:{source_table_name})-[r:{relation_name}]-(t) 
                            RETURN COUNT(r) , t.{target_pk} '''
                    else:
                        query=f'''MATCH (s:{source_table_name})-[r:{relation_name}]-(t) 
                            RETURN COUNT(r) , s.{columns[0]} , t.{target_pk}'''
                        
                    gph_result=execute_query(query) 
                    gph_result=gph_result.values()

                    result= [tuple(lst) for lst in gph_result]

            elif node_name=='Date' :
                
                converted_result=set()
                for source_type ,data in graph.tables[node_name].sources.items():
                    
                    table_name=data.table_name
                    
                    for attribute in data.selected_attributes:
                        columns.append(attribute)
                    
                    def convert_date_string(date_string):
                        formats_to_try = ['%d/%m/%y %H:%M', '%Y-%m-%d %H:%M:%S']

                        if date_string != None :
                            for date_format in formats_to_try:
                                try:
                                    datetime_obj = datetime.strptime(date_string, date_format)
                                    # id=datetime_obj.strftime('%d%m%Y')
                                    formatted_date = datetime_obj.strftime('%d %B %Y')
                                    return (date_string,formatted_date)
                                except ValueError:
                                    pass

                            return None  # Return None if none of the formats match

                    
                    if source_type == 'Rel_Tab':
                        query = "SELECT " + ", ".join(columns) + " FROM "+source_database_name+'.'+ table_name
                        cursor.execute(query)
                        result=cursor.fetchall()

                        rel_converted_result = set([convert_date_string(r[i]) for r in result for i in range (len(columns))])
                        converted_result=converted_result.union(rel_converted_result)

                    elif source_type =='Doc_col':
                        
                        collection = db[source_table_name]
                        projection = {'_id': 0}
                        for column in columns:
                            projection[column] = 1
                        # result = list(collection.find({}, projection))
                        result = list(collection.find({}, projection))

                        doc_converted_result=[]
                        for document in result:
                            date = document['Date']
                            doc_converted_result.append((str(date),date.strftime('%d %B %Y')))
                        
                        converted_result=converted_result.union(set(doc_converted_result))

                    
                    else:
                      
                        query="match (n:"+table_name+") return n."+ ",n.".join(columns)
                        result=execute_query(query) 
                        result=result.values() 

                        gph_converted_result = set([convert_date_string(r[i]) for r in result for i in range (len(columns))])
                        converted_result=converted_result.union(gph_converted_result)
                                          
                    result=list(converted_result)
                
            elif graph.tables[node_name].description == 'bridge_table' :
                
                table_name=graph.tables[node_name].sources[source_type].table_name
                for attribute in graph.tables[node_name].sources[source_type].selected_attributes:
                    columns.append(attribute)

                if source_type == 'Rel_Tab':
                        query = "SELECT " + ", ".join(columns) + " FROM "+source_database_name+'.'+ table_name
                        cursor.execute(query)
                        result=cursor.fetchall()

                elif source_type =='Doc_col':
                    
                    collection = db[table_name]
                    projection = {'_id': 0}
                    for column in columns:
                        projection[column] = 1
                    doc_result = list(collection.find({}, projection))
                    
                    result= [tuple(doc.get(column,'') for column in columns) for doc in doc_result]
                
                else:

                    target_pk=graph.tables[node_name].sources[source_type].target_primary_keys[0]
                    query = f"match (n:{table_name})-[:{target_pk.relation_name}]-({target_pk.table_name}) "
                    query+= f"return {target_pk.table_name}.{target_pk.primary_key} , "
                    query+="n."+ ",n.".join(columns)
                        
                    gph_result=execute_query(query) 
                    gph_result=gph_result.values()  

                    result= [tuple(lst) for lst in gph_result]

            else :
                
                table_name=graph.tables[node_name].sources[source_type].table_name
                columns.append(graph.tables[node_name].sources[source_type].primary_key)
                for attribute in graph.tables[node_name].sources[source_type].selected_attributes:
                    columns.append(attribute.split(' : ')[0])
                               
                if source_type =='Rel_Tab':
                      
                    for foreign_key in graph.tables[node_name].sources[source_type].foreign_keys:
                        columns.append(foreign_key.column)
                    
                    # we should select from the bridge table and do the join with the rest
                                   
                    query = "SELECT " + ", ".join(columns) + " FROM "+source_database_name+'.'+ table_name

                    cursor.execute(query)
                    result=cursor.fetchall()

                    for bridge_foreign_key in graph.tables[node_name].sources[source_type].bridge_foreign_keys:
                        query='select GroupId from '+bridge_foreign_key.references
                        cursor.execute(query)
                        bridge_result=cursor.fetchall()

                        hash_table = {item[0]: item for item in result}
                        result = [hash_table[item[0]] + tuple([item[0]]) for item in bridge_result if item[0] in hash_table]
                
                elif source_type =='Doc_col':
                    
                    collection = db[table_name]
                    
                    for foreign_key in graph.tables[node_name].sources[source_type].foreign_keys:
                        columns.append(foreign_key.column)
                        
                    projection = {'_id': 0}
                    for column in columns:
                        projection[column] = 1

                    doc_result = list(collection.find({}, projection))
                    
                    result= [tuple(doc.get(column,'') for column in columns) for doc in doc_result]
    
                # replace " and ' in strings
                    result = [tuple(col.replace('"', ' ') if isinstance(col, str) else col for col in tup) for tup in result]

                    result = [tuple(col.replace("'", " ") if isinstance(col, str) else col for col in tup) for tup in result]
   
                
                    for bridge_foreign_key in graph.tables[node_name].sources[source_type].bridge_foreign_keys:
                        query='select GroupId from '+bridge_foreign_key.references
                        cursor.execute(query)
                        bridge_result=cursor.fetchall()

                        hash_table = {item[0]: item for item in result}
                        result = [hash_table[item[0]] + tuple([item[0]]) for item in bridge_result if item[0] in hash_table]
                                                           
                else:
                    
                    match_query="match (n:"+table_name+")"
                    return_query= "return n."+ ",n.".join(columns)

                    for target_pk in graph.tables[node_name].sources[source_type].target_primary_keys:
                        match_query+= f"match (n)-[:{target_pk.relation_name}]-({target_pk.table_name})"
                        return_query+= f",{target_pk.table_name}.{target_pk.primary_key}"
                    
                    query=match_query + return_query 
 
                    result=execute_query(query)
                    gph_result=result.values()
                    result= [tuple(lst) for lst in gph_result]

                    for bridge_foreign_key in graph.tables[node_name].sources[source_type].bridge_foreign_keys:
                        query='select GroupId from '+bridge_foreign_key.references
                        cursor.execute(query)
                        bridge_result=cursor.fetchall()

                        hash_table = {item[0]: item for item in result}
                        result = [hash_table[item[0]] + tuple([item[0]]) for item in bridge_result if item[0] in hash_table]
            
            return result

        script_time=0
        cube_time=0

        def create_insert_tables():

            leaf_nodes = find_leaf_nodes(graph_adjacency_copy)
            
            if len(leaf_nodes)==0 :
                return

            for leaf_node in leaf_nodes:
                
                script_content=''

                if graph.tables[leaf_node].description == 'fact_table':
                    query,attributes,composite_primary_key=create_table(leaf_node)  
                else:
                    query=create_table(leaf_node)
                

                script_content=script_content+(query+'\n')
               
                print(query)
    # we should do  a transformation to query to change duplicate columns            
                cursor.execute(query)
                conn.commit()

                table_name=leaf_node.replace(' ','_')
                
                if leaf_node=='Date':
                    
                    data=retrive_data(leaf_node) # are a list of tuples (just insert them)
    
                elif len(graph.tables[leaf_node].sources) == 1 : # bhadi bark rana dirna le cas ta3 bridge_table , relationship_fact_table
                    
                    first_node_type=graph.tables[leaf_node].get_first_node_type()
                    
                    data=retrive_data(leaf_node,first_node_type)

                    if graph.tables[leaf_node].description == 'fact_table':
                        
                        data= [tuple_[1:] for tuple_ in data]

                        df = pd.DataFrame(data, columns=attributes)
                        grouped_data = df.groupby(composite_primary_key).sum().reset_index()
                        grouped_data = grouped_data[attributes]

                        data = [tuple(row) for row in grouped_data.to_numpy()]
                   
                elif len(graph.tables[leaf_node].sources) == 2 :

                    node_type_1,node_type_2=graph.tables[leaf_node].sources.keys()
                    
                    data1=retrive_data(leaf_node,node_type_1)
                    data2=retrive_data(leaf_node,node_type_2)

                    hash_table = {item[0]: item for item in data1}
                    data = [hash_table[item[0]] + item[1:] for item in data2 if item[0] in hash_table]
                    
                    if graph.tables[leaf_node].description == 'fact_table':
                        
                        data= [tuple_[1:] for tuple_ in data]

                        df = pd.DataFrame(data, columns=attributes)
                        grouped_data = df.groupby(composite_primary_key).sum().reset_index()
                        grouped_data = grouped_data[attributes]
                        data = [tuple(row) for row in grouped_data.to_numpy()]
                            
                else:
                    node_type_1,node_type_2,node_type_3=graph.tables[leaf_node].sources.keys()
                    data1=retrive_data(leaf_node,node_type_1)
                    data2=retrive_data(leaf_node,node_type_2)
                    data3=retrive_data(leaf_node,node_type_3)

                    hash_table = {item[0]: item for item in data1}
                    data = [hash_table[item[0]] + item[1:] for item in data2 if item[0] in hash_table]
                    hash_table = {item[0]: item for item in data}
                    data = [hash_table[item[0]] + item[1:] for item in data3 if item[0] in hash_table]

                    if graph.tables[leaf_node].description == 'fact_table':
                        
                        data= [tuple_[1:] for tuple_ in data]
                        #we should do the grouping here
                        df = pd.DataFrame(data, columns=attributes)
                        grouped_data = df.groupby(composite_primary_key).sum().reset_index()
                        grouped_data = grouped_data[attributes]
                        data = [tuple(row) for row in grouped_data.to_numpy()]

                print(table_name,len(data))
            
            # create script and insert data in tables 
                batch_size = 25000  
                
            #insert script into graphs database    
                total_records=len(data) 
                
                script_content=script_content +f"INSERT INTO {table_name} VALUES \n"
                for i, tup in enumerate(data, start=1):
                    values = "("
                    for j, item in enumerate(tup):
                        if j > 0:
                            values += ","
                        values += f"'{item}'"
                    values += ")"
                    
                    script_content=script_content +values

                    if i % batch_size == 0 or i == total_records:
                        script_content=script_content +";\n"

                        query=f'''UPDATE graphs.data_history
                            SET script = concat (script ,"{script_content}")
                            Where graph_name = "{database_name}";
                            '''
                        cursor.execute(query)
                        conn.commit() 

                        script_content=''
                        if i != total_records:
                            script_content=script_content +f"INSERT INTO {table_name} VALUES\n"
                    else:
                        script_content=script_content +",\n"

                query=f'''UPDATE graphs.data_history
                        SET script = concat (script ,"{script_content}")
                        Where graph_name = "{database_name}";
                        '''
                cursor.execute(query)
                conn.commit()

            # insert olap cube data

                insert_query = f"INSERT INTO {table_name} VALUES ({', '.join(['%s'] * len(data[0]))})"
                for i in range(0, len(data), batch_size):
                        print('insert....')
                        batch = data[i:i+batch_size]
                        batch = [tuple(int(value) if isinstance(value, np.int64) else value for value in row) for row in batch]
                        cursor.executemany(insert_query, batch)
                        conn.commit()

                graph_adjacency_copy.delete_vertex(leaf_node)
            
            create_insert_tables()

        create_insert_tables()
           
        cursor.close()
        conn.close()

        print('finish')



driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "meriem"))

def execute_query(query):
    with driver.session() as session:
        result = session.run(query)
        return result

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MyWindow()
    window.show()
    app.exec_()