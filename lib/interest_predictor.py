from typing import List, Tuple
import networkx as nx
import operator
import random

FOLDER_INDEX = 0
SERVICE_INDEX = 1

class InterestPredictor:
    def __init__(self, saved_services: List[Tuple[str, str]], target_folder: str):
        self.bipartite_graph = self._create_bipartite_graph(saved_services)
        self.services = {r[SERVICE_INDEX]: saved_services.count(r) for r in saved_services}
        self.target_folder = target_folder
        self._ebunch = self._get_ebunch(self.bipartite_graph, self.target_folder)

    def _create_bipartite_graph(self, saved_services: List[Tuple[str, str]]) -> nx.Graph:
        bipartite_graph = nx.Graph()
        bipartite_graph.add_edges_from((r[FOLDER_INDEX], r[SERVICE_INDEX]) for r in saved_services)
        return bipartite_graph
    
    def _get_ebunch(self, graph: nx.Graph, target_folder: str) -> List[Tuple[str, str]]:
        return [(target_folder, service) for service in self.services if not graph.has_edge(target_folder, service)]
    
    def get_interest_prediction(self) -> List[str]:
        predictions = nx.common_neighbor_centrality(self.bipartite_graph, ebunch=self._ebunch)
        return {service: score for (_, service, score) in predictions}