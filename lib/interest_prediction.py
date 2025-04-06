from typing import List, Tuple
import networkx as nx
import operator
import random

CLIENT_INDEX = 0
SERVICE_INDEX = 1

class InterestPredictor:
    def __init__(self, reviews: List[Tuple[str, str]], folder_name: str):
        self.bipartite_graph = self._create_bipartite_graph(reviews)
        self.services = {r[SERVICE_INDEX]: reviews.count(r) for r in reviews}
        self.folder_name = folder_name
        # self.existing_services = {service for (folder, service) in reviews if folder == folder_name}
        self._ebunch = self._get_ebunch(self.bipartite_graph, self.folder_name)
        self.data_graph = self._connect_folders(reviews)

    def _create_bipartite_graph(self, reviews: List[Tuple[str, str]]) -> nx.Graph:
        bipartite_graph = nx.Graph()
        bipartite_graph.add_edges_from((r[CLIENT_INDEX], r[SERVICE_INDEX]) for r in reviews)
        return bipartite_graph
    
    def _get_ebunch(self, graph: nx.Graph, folder_name: str) -> List[Tuple[str, str]]:
        return [(folder_name, service) for service in self.services if not graph.has_edge(folder_name, service) and service in self.bipartite_graph]
    
    def _connect_folders(self, reviews: List[Tuple[str, str]]) -> nx.Graph:
        data_graph = self.bipartite_graph.copy()
        all_folders = set(r[CLIENT_INDEX] for r in reviews)
        for folder in all_folders:
            for service in self.bipartite_graph.neighbors(folder):
                for other_folder in self.bipartite_graph.neighbors(service):
                    if folder == other_folder:
                        continue
                    if not data_graph.has_edge(folder, other_folder):
                        data_graph.add_edge(folder, other_folder)
        return data_graph
                        
    def get_interest_prediction(self) -> List[str]:
        # get all nodes
        all_nodes = self.data_graph.nodes()
        print("nodes: ", all_nodes)
        predictions = nx.common_neighbor_centrality(self.data_graph, ebunch=self._ebunch)
        return {service: score for (folder, service, score) in predictions}

    
# def _get_mock_data() -> List[Tuple[str, str]]:
#     return [
#         ('folder1', 'service1'),
#         ('folder1', 'service2'),
#         ('folder1', 'service3'),
#         ('folder2', 'service1'),
#         ('folder2', 'service2'),
#         ('folder3', 'service4'),
#         ('folder3', 'service5'),
#         ('folder4', 'service1'),
#         ('folder4', 'service3'),
#         ('folder5', 'service1'),
#         ('folder5', 'service2'),
#         ('folder5', 'service6'),
#     ]

# def main():
#     reviews = _get_mock_data()
#     folder_name = 'folder2'
#     predictor = InterestPredictor(reviews, folder_name)
#     predictions = predictor.get_interest_prediction()
#     print(predictions)

# if __name__ == '__main__':
#     main()