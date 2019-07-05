from collections import OrderedDict

import networkx as nx
import numpy as np
from networkx.algorithms import centrality, approximation, assortativity, vitality
from nltk.util import ngrams

from koe.sequence_utils import songs_to_syl_seqs
from root.exceptions import CustomAssertionError


def calc_start_end_stats(sequences, elements, node_dict):
    """
    :param elements:
    :param sequences: a list of elements
    :return:
    """
    distances_to_start = {x: [] for x in elements}
    distances_to_end = {x: [] for x in elements}

    for sequence in sequences:
        sequence_length = len(sequence)
        for idx, node_id in enumerate(sequence[1:-1]):
            distances_to_start[node_id].append(idx + 1)
            distances_to_end[node_id].append(sequence_length - 1)

    for node_id, distance_to_end in distances_to_end.items():
        node = node_dict[node_id]
        node.distance_to_end_average = np.mean(distance_to_end)
        node.distance_to_end_median = np.median(distance_to_end)
        node.distance_to_end_stdev = np.std(distance_to_end)

    for node_id, distance_to_start in distances_to_start.items():
        node = node_dict[node_id]
        node.distance_to_start_average = np.mean(distance_to_start)
        node.distance_to_start_median = np.median(distance_to_start)
        node.distance_to_start_stdev = np.std(distance_to_start)


def networkx_stats(graph, digraph, node_dict):
    lccs = nx.clustering(graph)
    for node_id, lcc in lccs.items():
        node = node_dict[node_id]
        node.lcc = lcc
        # shortest_paths = nx.shortest_path(digraph)
        # eccentricities = nx.eccentricity(graph)

        # elements = shortest_paths.keys()
        # nelements = len(elements)
        # path_matrix = np.ndarray((nelements, nelements), dtype=np.int32)

        # for element, shortest_path in shortest_paths.items():
        #     path_matrix[element, list(shortest_path.keys())] = list(shortest_path.values())


def deduce_transition_type(nodes):
    for node in nodes:
        if node.in_links_count == 0 or node.out_links_count == 0:
            node.transition_type = 'Margin'
        elif node.in_links_count == 1:
            if node.out_links_count == 1:
                node.transition_type = 'One-way'
            else:
                node.transition_type = 'Branch'
        else:
            if node.out_links_count == 1:
                node.transition_type = 'Bottleneck'
            else:
                node.transition_type = 'Hourglass'


def calc_average_link_distance(nodes, is_inlink=True, is_normalised=True):
    for node in nodes:
        average_distance = 0
        if is_inlink:
            links = node.in_links
            link_count = float(node.in_links_count)
        else:
            links = node.out_links
            link_count = float(node.out_links_count)

        for link in links:
            if is_normalised:
                average_distance += link.normalised_distance
            else:
                average_distance += link.distance
        if average_distance > 0:
            average_distance /= link_count
        if is_inlink:
            if is_normalised:
                node.average_in_link_normalised_distance = average_distance
            else:
                node.average_in_link_distance = average_distance

        else:
            if is_normalised:
                node.average_out_link_normalised_distance = average_distance
            else:
                node.average_out_link_distance = average_distance


def calc_distances(links):
    """
    Normalised distance is the distance from node X->Y relative to the distance from X to all other nodes
    For example, if there are 30 links from A->B, 10 links from A->C, 10 links from A->D,
                 then the distance A->B is 3 times smaller than that from A->C and A->D
    Formula: First calculate the weights of the links:
             A->B = 0.6, A->C = 0.2, A->D = 0.2
             Then offset them from 1:
             A->B = 0.4, A-.C = 0.8, A->D = 0.8
             Now normalise them by (number of connecting neighbours - 1), so that their distances add up to 1:
             A->B = 0.2, A-.C = 0.4, A->D = 0.4
    :param links:
    :return:
    """
    sum_distances = 0
    for link in links:
        link.distance = float(link.source.individual_link_count) / link.count
        sum_distances += link.distance

    for link in links:
        link.normalised_distance = link.distance / sum_distances


def count_individual_links(nodes):
    """
    Count the total number of individual links from or to a node.
    Notice that except for the START and END nodes, any real node will have exactly the same
    number of incoming and outgoing links.
    :param nodes:
    :return:
    """
    for node in nodes:
        individual_link_count = 0
        if node.in_links:
            for link in node.in_links:
                individual_link_count += link.count
        else:
            for link in node.out_links:
                individual_link_count += link.count
        node.individual_link_count = individual_link_count


class Node:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.out_links = []
        self.in_links = []
        self.out_links_count = 0
        self.in_links_count = 0
        self.individual_link_count = 0
        self.transition_type = None
        self.average_in_link_distance = 0
        self.lcc = 0

    def __repr__(self):
        return '#{} {}'.format(self.id, self.name)


class Link:
    def __init__(self, source, target):
        self.source = source
        self.target = target
        self.count = 0
        self.normalised_distance = 0

    def __repr__(self):
        return '{}-{}->{}'.format(self.source.name, self.count, self.target)


def extract_graph_properties(songs, enum2label):
    sequences = songs.values()
    elements = enum2label.keys()

    link_dict = {}
    node_dict = {}
    links = []

    def get_node(nodeid):
        if nodeid in node_dict:
            return node_dict[nodeid]
        else:
            node_name = enum2label[nodeid]
            node = Node(nodeid, node_name)
            node_dict[nodeid] = node
            return node

    def get_link(xid, yid):
        if xid in link_dict:
            ylinks = link_dict[xid]
        else:
            ylinks = {}
            link_dict[xid] = ylinks

        if yid in ylinks:
            xylink = ylinks[yid]
        else:
            xnode = get_node(x)
            ynode = get_node(y)
            xylink = Link(xnode, ynode)

            links.append(xylink)
            ylinks[yid] = xylink

            xnode.out_links.append(xylink)
            ynode.in_links.append(xylink)
            xnode.out_links_count += 1
            ynode.in_links_count += 1
        return xylink

    for sequence in sequences:
        grams = ngrams(sequence, 2)
        for x, y in grams:
            link = get_link(x, y)
            link.count += 1

    count_individual_links(node_dict.values())
    calc_distances(links)
    deduce_transition_type(node_dict.values())
    calc_average_link_distance(node_dict.values(), True, True)
    calc_average_link_distance(node_dict.values(), True, False)
    calc_average_link_distance(node_dict.values(), False, True)
    calc_average_link_distance(node_dict.values(), False, False)
    calc_start_end_stats(sequences, elements, node_dict)

    edges = []
    for link in links:
        edges.append((
            link.source.id, link.target.id, {
                'distance': link.normalised_distance,
                'weight': link.count
            }
        ))

    return edges, node_dict


def _get_small_world_measures(graph, meas, **kwargs):
    # Compute the mean clustering coefficient and average shortest path length
    # for an equivalent random graph
    nrand = kwargs['nrand']
    niter = kwargs['niter']
    C = meas['C']
    L = meas['L']

    randMetrics = {"Cr": [], "Cl": [], "L": []}
    for _ in range(nrand):
        Gr = nx.random_reference(graph, niter=niter)
        Gl = nx.lattice_reference(graph, niter=niter)
        randMetrics["Cl"].append(nx.transitivity(Gl))
        randMetrics["Cr"].append(nx.transitivity(Gr))
        randMetrics["L"].append(nx.average_shortest_path_length(Gr))

    Cl = np.mean(randMetrics["Cl"])
    Cr = np.mean(randMetrics["Cr"])
    Lr = np.mean(randMetrics["L"])

    omega = (Lr / L) - (C / Cl)
    sigma = (C / Cr) / (L / Lr)

    meas['Omega'] = omega
    meas['Sigma'] = sigma


stats_funcs = OrderedDict(mean=np.nanmean, median=np.nanmedian, std=np.nanstd, min=np.min, max=np.max)


def extract_and_store_stats(base, values, meas):
    for stat, func in stats_funcs.items():
        meas[base + '_' + stat] = func(values)


def make_func(name, func_desc, is_global=False):
    nxfunc = func_desc['func']
    weighted = func_desc['weighted']
    is_global = func_desc['is_global']
    directed = func_desc['directed']

    def func(graph, digraph, meas, **kwargs):
        try:
            if directed:
                if weighted:
                    node_values = nxfunc(digraph, weight='weight')
                else:
                    node_values = nxfunc(digraph)
            else:
                node_values = nxfunc(graph)
            if is_global:
                meas[name] = node_values
            else:
                values = list(node_values.values())
                extract_and_store_stats(name, values, meas)
        except Exception as e:
            raise Exception('Error running function {}: {}'.format(name, str(e)))

    return func


meas_dependencies = {
    'small_world_measures': ['clustering_coefficient', 'average_shortest_path_length'],
}


def make_stats_output(base):
    return [base + '_' + x for x in stats_funcs.keys()]


meas_funcs_and_outputs = {

    # Disable for now because it's very slow
    # 'small_world_measures': (_get_small_world_measures, ['Omega', 'Sigma']),
}

func_map = {
    'degree_centrality': dict(func=centrality.degree_centrality, weighted=False, directed=True, is_global=False),
    'eigen_centrality': dict(func=centrality.eigenvector_centrality_numpy, weighted=True, directed=True,
                             is_global=False),
    'closeness_centrality': dict(func=centrality.closeness_centrality, weighted=False, directed=True, is_global=False),
    'out_degree_centrality': dict(func=centrality.out_degree_centrality, weighted=False, directed=True,
                                  is_global=False),
    'in_degree_centrality': dict(func=centrality.in_degree_centrality, weighted=False, directed=True, is_global=False),
    'katz_centrality': dict(func=centrality.katz_centrality_numpy, weighted=True, directed=True, is_global=False),
    'current_flow_closeness_centrality': dict(func=centrality.current_flow_closeness_centrality, weighted=False,
                                              directed=False, is_global=False),
    'information_centrality': dict(func=centrality.information_centrality, weighted=False, directed=False,
                                   is_global=False),
    'betweenness_centrality': dict(func=centrality.betweenness_centrality, weighted=True, directed=True,
                                   is_global=False),
    'current_flow_betweenness_centrality': dict(func=centrality.current_flow_betweenness_centrality, weighted=False,
                                                directed=False, is_global=False),
    'approximate_current_flow_betweenness_centrality': dict(
        func=centrality.approximate_current_flow_betweenness_centrality, weighted=False, directed=False,
        is_global=False),
    'communicability_betweenness_centrality': dict(func=centrality.communicability_betweenness_centrality,
                                                   weighted=True, directed=False, is_global=False),
    'load_centrality': dict(func=centrality.load_centrality, weighted=True, directed=True, is_global=False),
    'harmonic_centrality': dict(func=centrality.harmonic_centrality, weighted=False, directed=True, is_global=False),
    'square_clustering': dict(func=nx.square_clustering, weighted=False, directed=True, is_global=False),
    'clustering': dict(func=nx.clustering, weighted=True, directed=True, is_global=False),
    'average_neighbor_degree': dict(func=assortativity.average_neighbor_degree, weighted=True, directed=True,
                                    is_global=False),
    'average_degree_connectivity': dict(func=assortativity.average_degree_connectivity, weighted=True, directed=True,
                                        is_global=False),

    # Must be strongly connected
    # 'eccentricity': dict(func=distance_measures.eccentricity, weighted=False, directed=False, is_global=False),
    'closeness_vitality': dict(func=vitality.closeness_vitality, weighted=True, directed=True, is_global=False),

    # Global function

    'transitivity': dict(func=nx.transitivity, weighted=False, directed=True, is_global=True),
    'average_clustering': dict(func=nx.average_clustering, weighted=False, directed=True, is_global=True),
    'approx_average_clustering': dict(func=approximation.average_clustering, weighted=False, directed=False,
                                      is_global=True),
    'average_shortest_path_length': dict(func=nx.average_shortest_path_length, weighted=False, directed=True,
                                         is_global=True),
    'global_reaching_centrality': dict(func=centrality.global_reaching_centrality, weighted=False, directed=True,
                                       is_global=True),
    'node_connectivity': dict(func=approximation.node_connectivity, weighted=False, directed=True, is_global=True),
    'degree_assortativity_coefficient': dict(func=assortativity.degree_assortativity_coefficient, weighted=False,
                                             directed=True, is_global=True),

    # Must be strongly connected
    # 'diameter': dict(func=distance_measures.diameter, weighted=False, directed=True, is_global=True),
    # 'radius': dict(func=distance_measures.radius, weighted=False, directed=True, is_global=True),
}

for func_name, func_desc in func_map.items():
    func = make_func(func_name, func_desc)
    if func_desc['is_global']:
        output = [func_name]
    else:
        output = make_stats_output(func_name)
    meas_funcs_and_outputs[func_name] = (func, output)


def resolve_meas(measurements_str):
    if measurements_str == 'all':
        measurements_str = ','.join(list(func_map.keys()))
    measurements_names = measurements_str.split(',')
    measurements_order = OrderedDict()
    measurements_outputs = []

    def resolve_one(name):
        if name not in meas_funcs_and_outputs:
            raise CustomAssertionError('Unknown measurement {}'.format(name))
        dependencies = meas_dependencies.get(name, [])
        output_names = meas_funcs_and_outputs[name][1]
        func = meas_funcs_and_outputs[name][0]
        if len(dependencies) == 0:
            if name not in measurements_order:
                measurements_order[name] = func
                measurements_outputs.extend(output_names)
        else:
            for dependency_name in dependencies:
                resolve_one(dependency_name)
            if name not in measurements_order:
                measurements_order[name] = func
                measurements_outputs.extend(output_names)

    for name in measurements_names:
        resolve_one(name)
    return list(measurements_order.values()), measurements_outputs


def extract_graph_feature(songs, sid_to_cluster, enum2label, measurements_order, **extra_args):
    song_sequences = songs_to_syl_seqs(songs, sid_to_cluster, enum2label, use_pseudo=False)

    edges, node_dict = extract_graph_properties(song_sequences, enum2label)
    nodes = sorted(list(node_dict.keys()))

    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)

    digraph = nx.DiGraph()
    digraph.add_nodes_from(nodes)
    digraph.add_edges_from(edges)

    measurements_values = {}
    for func in measurements_order:
        func(graph, digraph, measurements_values, **extra_args)

    return measurements_values
