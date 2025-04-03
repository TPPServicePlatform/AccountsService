from typing import List, Tuple
import networkx as nx
import operator
import random

CLIENT_INDEX = 0
SERVICE_INDEX = 1

class InterestPredictor:
    def __init__(self, reviews: List[Tuple[str, str]], user_id: str):
        self.bipartite_graph = self._create_bipartite_graph(reviews)
        self.services = {r[SERVICE_INDEX]: reviews.count(r) for r in reviews}
        self.user_id = user_id
        # self.existing_services = {service for (user, service) in reviews if user == user_id}
        self._ebunch = self._get_ebunch(self.bipartite_graph, self.user_id)
        self.data_graph = self._connect_users(reviews)

    def _create_bipartite_graph(self, reviews: List[Tuple[str, str]]) -> nx.Graph:
        bipartite_graph = nx.Graph()
        bipartite_graph.add_edges_from((r[CLIENT_INDEX], r[SERVICE_INDEX]) for r in reviews)
        return bipartite_graph
    
    def _get_ebunch(self, graph: nx.Graph, user_id: str) -> List[Tuple[str, str]]:
        return [(user_id, service) for service in self.services if not graph.has_edge(user_id, service) and service in self.bipartite_graph]
    
    def _connect_users(self, reviews: List[Tuple[str, str]]) -> nx.Graph:
        data_graph = self.bipartite_graph.copy()
        all_users = set(r[CLIENT_INDEX] for r in reviews)
        for user in all_users:
            for service in self.bipartite_graph.neighbors(user):
                for other_user in self.bipartite_graph.neighbors(service):
                    if user == other_user:
                        continue
                    if not data_graph.has_edge(user, other_user):
                        data_graph.add_edge(user, other_user)
        return data_graph
                        
    def get_interest_prediction(self) -> List[str]:
        predictions = nx.common_neighbor_centrality(self.data_graph, ebunch=self._ebunch)
        return {service: score for (user, service, score) in predictions}

    
# def _get_mock_data() -> List[Tuple[str, str]]:
#     return [
#         ('user1', 'service1'),
#         ('user1', 'service2'),
#         ('user1', 'service3'),
#         ('user2', 'service1'),
#         ('user2', 'service2'),
#         ('user3', 'service4'),
#         ('user3', 'service5'),
#         ('user4', 'service1'),
#         ('user4', 'service3'),
#         ('user5', 'service1'),
#         ('user5', 'service2'),
#         ('user5', 'service6'),
#     ]

# def main():
#     reviews = _get_mock_data()
#     user_id = 'user2'
#     predictor = InterestPredictor(reviews, user_id)
#     predictions = predictor.get_interest_prediction()
#     print(predictions)

# if __name__ == '__main__':
#     main()