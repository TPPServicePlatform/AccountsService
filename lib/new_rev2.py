import datetime
import os
import sys
from time import sleep
import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import networkx as nx # graphs
from queue import Queue
from multiprocessing import Pool
import logging as logger

from accounts_sql import Accounts
from imported_lib.ServicesService.services_lib import ServicesLib

MAX_THREADS = max(50, os.cpu_count())
UPDATE_FREQUENCY = 15 # days


#############################
class Metricas:
    def __init__(self, score, fiabilidad):
        self.score = score
        self.fiabilidad = fiabilidad
        
def generar_grafo_con_metricas(grafo_original):
    nuevo_grafo = nx.DiGraph()

    for usuario, producto, datos in grafo_original.edges(data=True):
        metricas = Metricas(datos['rating'], 1)
        nuevo_grafo.add_edge(usuario, producto, metricas=metricas)

    return nuevo_grafo

def actualizar_fairness(grafo, usuario):
    return sum(grafo.edges[arista]['metricas'].fiabilidad for arista in grafo.out_edges(usuario)) / grafo.out_degree(usuario)

def actualizar_valor(grafo, producto, fairness):
    return sum(grafo.edges[(usuario, producto)]['metricas'].score * fairness[usuario] for usuario in grafo.predecessors(producto)) / grafo.in_degree(producto)

def actualizar_fiabilidad(grafo, usuario, producto, gamma1, gamma2, fairness, valor):
    return 1 / (gamma1 + gamma2) * (gamma1 * fairness[usuario] + gamma2 * (1 - abs(grafo.edges[(usuario, producto)]['metricas'].score - valor[producto]) / 2))
    # grafo.edges[(usuario, producto)]['metricas'].fiabilidad = fiabilidad
    
#############################

def actualizar_fairness_wrapper(args):
    grafo, nodo = args
    return actualizar_fairness(grafo, nodo)

def actualizar_valor_wrapper(args):
    grafo, nodo, fairness = args
    return actualizar_valor(grafo, nodo, fairness)

def actualizar_fiabilidad_wrapper(grafo, usuario, producto, gamma1, gamma2, fairness, valor):
    return actualizar_fiabilidad(grafo, usuario, producto, gamma1, gamma2, fairness, valor)

def rev2(grafo_original, gamma1, gamma2, diff):
    
    grafo = generar_grafo_con_metricas(grafo_original)
    fairness = {nodo: 1 for nodo in grafo.nodes if grafo.out_degree(nodo) > 0}
    valor = {nodo: 1 for nodo in grafo.nodes if grafo.in_degree(nodo) > 0}
    
    i = 0
    max_diff_fairness = 2 * diff
    max_diff_confiabilidad = 2 * diff
    max_diff_valor = 2 * diff

    while max_diff_fairness > diff or max_diff_confiabilidad > diff or max_diff_valor > diff:
        i+=1
        print(f"Calculando la {i}° iteración...")
        vieja_fairness = fairness.copy()
        vieja_confiabilidad = {arista: datos['metricas'].fiabilidad for arista, datos in grafo.edges.items()}
        viejo_valor = valor.copy()

        usuarios = [nodo for nodo in grafo.nodes if grafo.out_degree(nodo) > 0]
        productos = [nodo for nodo in grafo.nodes if grafo.in_degree(nodo) > 0]

        with Pool(MAX_THREADS) as pool:
            fairness_vals = pool.map(actualizar_fairness_wrapper, [(grafo, nodo) for nodo in usuarios])
            valor_vals = pool.map(actualizar_valor_wrapper, [(grafo, nodo, fairness) for nodo in productos])
        fairness = {nodo: fairness_vals[i] for i, nodo in enumerate(usuarios)}
        valor = {nodo: valor_vals[i] for i, nodo in enumerate(productos)}

        with Pool(MAX_THREADS) as pool: 
            fiabilidad_vals = pool.starmap(actualizar_fiabilidad_wrapper, [(grafo, usuario, producto, gamma1, gamma2, fairness, valor) for usuario, producto in grafo.edges])
        for i, (usuario, producto) in enumerate(grafo.edges):
            grafo.edges[(usuario, producto)]['metricas'].fiabilidad = fiabilidad_vals[i]

        nueva_fairness = fairness
        nueva_confiabilidad = {arista: datos['metricas'].fiabilidad for arista, datos in grafo.edges.items()}
        nuevo_valor = valor
        
        max_diff_fairness = max(abs(vieja_fairness[nodo] - nueva_fairness[nodo]) for nodo in usuarios)
        max_diff_confiabilidad = max(abs(vieja_confiabilidad[arista] - nueva_confiabilidad[arista]) for arista in grafo.edges)
        max_diff_valor = max(abs(viejo_valor[nodo] - nuevo_valor[nodo]) for nodo in productos)
        print(f"{i}° iteración:")
        print("- max_diff_fairness: ", round(max_diff_fairness, 4))
        print("- max_diff_confiabilidad: ", round(max_diff_confiabilidad, 4))
        print("- max_diff_valor: ", round(max_diff_valor, 4), '\n')

    return grafo, fairness, valor

#############################

class Rev2Graph:
    def __init__(self, ratings_list):
        # ratings list format -> [(f"U{r['user_uuid']}", f"S{r['service_uuid']}", float(r['rating'])) for r in results]
        self.complete_graph = _generate_graph(_normalize_data(ratings_list))
        self.components = _divide_components(self.complete_graph)
        
    def calculate(self, gamma1=0.5, gamma2=0.5, diff=0.01):
        with Pool(MAX_THREADS) as pool:
            results = pool.map(lambda graph: rev2(graph, gamma1, gamma2, diff), self.components)
        fairness_results = {}
        for _, fairness, _ in results:
            fairness_results.update(fairness)
        return fairness_results
    
def rev2_calculator():
    services_lib = ServicesLib()
    accounts_manager = Accounts()
    logger.basicConfig(format='%(levelname)s: %(asctime)s - [REV2] %(message)s',
                   stream=sys.stdout, level=logger.INFO)
    next_update = datetime.datetime.now()
    while True:
        sleep_time = (next_update - datetime.datetime.now()).total_seconds()
        logger.info(f"Next update in {sleep_time} seconds")
        sleep(max(0, sleep_time))
        ratings_list = services_lib.get_recent_ratings(max_delta_days=360)
        if not ratings_list or len(ratings_list) == 0:
            # print("[REV2] No ratings found. Waiting for next update...")
            logger.info("No ratings found. Waiting for next update...")
            continue
        # print("[REV2] Calculating...")
        logger.info("Calculating...")
        rev2_graph = Rev2Graph(ratings_list)
        results = rev2_graph.calculate()
        accounts_manager.rev2_results_saver(results)
        next_update = datetime.datetime.now() + datetime.timedelta(days=UPDATE_FREQUENCY)
            
def _divide_components(graph):
    components = []
    visited = set()
    for node in graph.nodes:
        if node not in visited:
            component_graph = _get_component(graph, node, visited)
            components.append(component_graph)
    return components

def _get_component(graph, node, visited):
    component_graph = nx.Graph()
    queue = Queue()
    queue.put(node)
    visited.add(node)
    component_graph.add_node(node)
    while not queue.empty():
        current_node = queue.get()
        for neighbor in graph.neighbors(current_node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.put(neighbor)
                component_graph.add_node(neighbor)
                component_graph.add_edge(current_node, neighbor, weight=graph[current_node][neighbor]['weight'])
    return component_graph
    
            
def _generate_graph(ratings_list):
    users = set([rating[0] for rating in ratings_list])
    services = set([rating[1] for rating in ratings_list])
    
    bipartite_graph = nx.Graph()
    
    # add nodes
    bipartite_graph.add_nodes_from(users)
    bipartite_graph.add_nodes_from(services)
    
    # add edges
    for rating in ratings_list:
        bipartite_graph.add_edge(rating[0], rating[1], weight=rating[2])
    return bipartite_graph
            
def _normalize_data(ratings_list):
    max_rating = max([rating[2] for rating in ratings_list])
    min_rating = min([rating[2] for rating in ratings_list])
    normalizer = lambda x: 2*(x - min_rating) / (max_rating - min_rating) - 1
    return [(rating[0], rating[1], normalizer(rating[2])) for rating in ratings_list]