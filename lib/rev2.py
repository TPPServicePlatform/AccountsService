import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
import networkx as nx # graphs
import multiprocessing

STARTING_RELIABILITY = 1.0
GAMMA1 = 0.5
GAMMA2 = 0.5
MAX_DIFF = 0.005
FAIRNESS_INDEX = 1

class Metrics:
    def __init__(self, score, reliability):
        self.score = float(score)
        self.reliability = float(reliability)
    
    def __str__(self):
        return f"(Score: {self.score}, Reliability: {self.reliability})"
    
class Rev2Graph:
    def __init__(self, edge_list): # list of tuples (user, service_id, score)
        self.main_graph, undirected_graph = self._create_main_graph(self._normalize_ratings(edge_list))
        self.analyzable_components = self._components(undirected_graph)
        print("Analyzable components")
        for i in range(len(self.analyzable_components)):
            print(f"Component {i+1}:")
            for node in self.analyzable_components[i].nodes:
                print(f"Node name: {node}")
                for neighbor in self.analyzable_components[i].neighbors(node):
                    print(f"Neighbor name: {neighbor} | Metrics: {self.analyzable_components[i][node][neighbor]['metrics']}")
            print()
    
    def _normalize_ratings(self, edge_list):
        """
        This function normalizes the ratings of the edges in the graph to be between -1 and 1.
        """
        min_rating = min(edge[2] for edge in edge_list)
        max_rating = max(edge[2] for edge in edge_list)
        normalizer_func = lambda rating: 2*(rating - min_rating) / (max_rating - min_rating) - 1
        
        return [(user, service_id, normalizer_func(rating)) for user, service_id, rating in edge_list]

    def _create_main_graph(self, edge_list):
        main_graph = nx.DiGraph() # directed graph
        undirected_graph = nx.Graph()
        for (user, service_id, review_score) in edge_list:
            main_graph.add_edge(user, service_id, metrics=Metrics(review_score, STARTING_RELIABILITY))
            undirected_graph.add_edge(user, service_id)
        return main_graph, undirected_graph
    
    def _components(self, undirected_graph):
        connected_components = list(nx.connected_components(undirected_graph))
        analyzable_components = []
        for component in connected_components:
            if len(component) > 1:
                analyzable_components.append(self._extract_graph(component))
        return analyzable_components

    def _extract_graph(self, component):
        new_di_graph = nx.DiGraph()
        for node in component:
            new_di_graph.add_node(node)
        for node in component:
            for neighbor in self.main_graph.neighbors(node):
                new_di_graph.add_edge(node, neighbor, metrics=self.main_graph[node][neighbor]['metrics'])
        return new_di_graph
    
    def _updated_fairness(self, graph, user):
        return sum(graph.edges[edge]['metrics'].reliability for edge in graph.out_edges(user)) / graph.out_degree(user)
    
    def _updated_value_score(self, graph, product, fairness_dict):
        return sum(graph.edges[(user, product)]['metrics'].score * fairness_dict[user] for user in graph.predecessors(product)) / graph.in_degree(product) 
    
    def _updated_reliability(self, graph, user, product, fairness_dict, value_score_dict):
        return (1 / (GAMMA1 + GAMMA2)) * (GAMMA1 * fairness_dict[user] + GAMMA2 * (1 - abs(graph.edges[(user, product)]['metrics'].score - value_score_dict[product]) / 2))

    def _process_node(self, node, graph, fairness_dict, value_score_dict):
        fairness_value = fairness_dict[node]
        valor_value = value_score_dict[node]
        if graph.out_degree(node) > 0:  # This node is a user
            fairness_value = self._updated_fairness(graph, node)
        if graph.in_degree(node) > 0:  # This node is a product
            valor_value = self._updated_value_score(graph, node, fairness_dict)
        return node, fairness_value, valor_value

    def _process_edge(self, user, product, graph, fairness_dict, value_score_dict):
        return self._updated_reliability(graph, user, product, fairness_dict, value_score_dict), user, product
    
    def _rev2_for_component(self, graph):
        current_process = multiprocessing.current_process()
        if current_process.daemon:
            current_process.daemon = False

        graph = graph.copy()
        fairness_dict = {node: 1 for node in graph.nodes}
        value_score_dict = {node: 1 for node in graph.nodes}

        i = 0
        max_diff_fairness = max_diff_confiabilidad = max_diff_valor = 2 * MAX_DIFF

        while max_diff_fairness > MAX_DIFF or max_diff_confiabilidad > MAX_DIFF or max_diff_valor > MAX_DIFF:
            i += 1
            old_fairness_dict = fairness_dict.copy()
            old_reliability_dict = {edge: data['metrics'].reliability for edge, data in graph.edges.items()}
            old_value_score_dict = value_score_dict.copy()

            with multiprocessing.Pool() as pool:
                results = pool.starmap(self._process_node, [(node, graph, fairness_dict, value_score_dict) for node in graph.nodes])
                for node, new_fairness, new_value_score in results:
                    fairness_dict[node] = new_fairness
                    value_score_dict[node] = new_value_score

            with multiprocessing.Pool() as pool:
                reliabilities = pool.starmap(self._process_edge, [(user, product, graph, fairness_dict, value_score_dict) for user, product in graph.edges])
                for reliability, user, product in reliabilities:
                    graph.edges[(user, product)]['metrics'].reliability = reliability

            new_fairness_dict = fairness_dict
            new_reliability_dict = {edge: data['metrics'].reliability for edge, data in graph.edges.items()}
            new_value_score_dict = value_score_dict

            max_diff_fairness = max(abs(old_fairness_dict[node] - new_fairness_dict[node]) for node in graph.nodes)
            max_diff_confiabilidad = max(abs(old_reliability_dict[edge] - new_reliability_dict[edge]) for edge in graph.edges)
            max_diff_valor = max(abs(old_value_score_dict[node] - new_value_score_dict[node]) for node in graph.nodes)

            # print(f"{i}° iteración:")
            # print("- max_diff_fairness: ", round(max_diff_fairness, 4))
            # print("- max_dif_confiabilidad: ", round(max_diff_confiabilidad, 4))
            # print("- max_dif_valor: ", round(max_diff_valor, 4), '\n')

        return graph, fairness_dict, value_score_dict
    
    def get_results(self):
        results = {}
        with multiprocessing.Pool() as pool:
            components_results = pool.map(self._rev2_for_component, self.analyzable_components)
            for component_result in components_results:
                results.update(component_result[FAIRNESS_INDEX])
        return results



