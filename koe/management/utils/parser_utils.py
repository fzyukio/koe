from root.exceptions import CustomAssertionError


def read_cluster_range(cluster_range_str, clusters_sizes):
    start, end = cluster_range_str.split(':')
    try:
        start_int = int(start)
        end_int = int(end)

        assert start_int == float(start)
        assert end_int == float(end)

        if start_int == 0:
            start_int = 0
        if end_int == -1:
            end_int = len(clusters_sizes) - 1

        assert 0 <= start_int <= end_int
        return start_int, end_int

    except Exception:
        raise CustomAssertionError('Invalid value {} for --cluster-range'.format(cluster_range_str))
